import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _load_opus():
    """Load libopus from the Nix store or fall back to default names."""
    if discord.opus.is_loaded():
        return
    candidates = [
        "/nix/store/0py9xncsn0s6vqxhvqblvhs2cqbb30s8-libopus-1.5.2/lib/libopus.so.0",
        "libopus.so.0",
        "libopus.so",
        "opus",
    ]
    for path in candidates:
        try:
            discord.opus.load_opus(path)
            logger.info(f"Loaded opus from: {path}")
            return
        except Exception:
            continue
    logger.warning("Could not load libopus — voice audio will not work.")


_load_opus()

YTDL_OPTIONS = {
    "format": "bestaudio[ext=m4a]/bestaudio/best",
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": True,  # let playlist/search extraction skip broken entries instead of raising
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch5",  # pull a few candidates so we can skip blocked/broken ones
    "source_address": "0.0.0.0",
    "extractor_args": {
        # "web" (yt-dlp's default client) is the one YouTube's bot-check/PO-token
        # gate hits hardest. tv/android/web_safari clients route around it without
        # needing cookies for the vast majority of public videos.
        "youtube": {
            "player_client": ["tv", "android", "web_safari"],
        }
    },
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


class TrackNotFoundError(Exception):
    """Raised when no playable track could be found/loaded for a query."""


@dataclass
class Song:
    url: str
    title: str
    duration: int  # seconds
    webpage_url: str
    requester: str

    @property
    def duration_str(self) -> str:
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


@dataclass
class GuildState:
    queue: list = field(default_factory=list)
    current: Song | None = None
    voice_client: discord.VoiceClient | None = None


def _extract_stream_url(data: dict) -> str | None:
    """Pull a playable direct URL out of a yt-dlp info dict, handling the
    various shapes extract_info can return depending on format selection."""
    if data.get("url"):
        return data["url"]
    for fmt in reversed(data.get("requested_formats") or []):
        if fmt.get("url"):
            return fmt["url"]
    for fmt in reversed(data.get("formats") or []):
        if fmt.get("acodec") not in (None, "none") and fmt.get("url"):
            return fmt["url"]
    return None


def _extract_info_sync(query: str) -> dict:
    return ytdl.extract_info(query, download=False)


async def fetch_song(query: str, requester: str) -> Song:
    """Run yt-dlp in a thread pool to avoid blocking the event loop.

    Raises TrackNotFoundError with a clear reason if nothing playable
    could be resolved (as opposed to swallowing every failure the same way).
    """
    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(None, _extract_info_sync, query)
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp DownloadError for query '{query}': {e}")
        raise TrackNotFoundError(str(e)) from e

    if data is None:
        raise TrackNotFoundError("yt-dlp returned no data.")

    # Direct URL/query resolves to a single info dict; searches resolve to
    # {'entries': [...]}. With ignoreerrors=True, individual bad entries
    # (private/deleted/geo-blocked videos) come back as None — skip those.
    candidates = data["entries"] if "entries" in data else [data]
    candidates = [c for c in candidates if c]

    if not candidates:
        raise TrackNotFoundError("No results found for that query.")

    last_error = None
    for candidate in candidates:
        stream_url = _extract_stream_url(candidate)
        if not stream_url:
            last_error = "no playable audio stream in result"
            continue
        return Song(
            url=stream_url,
            title=candidate.get("title", "Unknown"),
            duration=candidate.get("duration", 0) or 0,
            webpage_url=candidate.get("webpage_url", candidate.get("url", "")),
            requester=requester,
        )

    raise TrackNotFoundError(last_error or "Could not resolve a playable stream.")


class Music(commands.Cog):
    """Music playback commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._states: dict[int, GuildState] = {}

    def get_state(self, guild_id: int) -> GuildState:
        if guild_id not in self._states:
            self._states[guild_id] = GuildState()
        return self._states[guild_id]

    async def _after_play(self, guild_id: int, error):
        if error:
            logger.error(f"Player error in guild {guild_id}: {error}")
        state = self.get_state(guild_id)
        if state.queue:
            next_song = state.queue.pop(0)
            state.current = next_song
            await self._start_playback(state, next_song, guild_id)
        else:
            state.current = None

    async def _start_playback(self, state: GuildState, song: Song, guild_id: int):
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(song.url, **FFMPEG_OPTIONS), volume=0.5
        )
        state.voice_client.play(
            source,
            after=lambda e: asyncio.run_coroutine_threadsafe(
                self._after_play(guild_id, e), self.bot.loop
            ),
        )

    # ── /play ────────────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Play a song from YouTube (URL or search query)")
    @app_commands.describe(query="YouTube URL or search terms")
    @app_commands.guild_only()
    async def play(self, interaction: discord.Interaction, query: str):
        # Must be in a voice channel
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "❌ You must be in a voice channel to use this command.", ephemeral=True
            )
        voice_channel = interaction.user.voice.channel
        state = self.get_state(interaction.guild_id)

        await interaction.response.defer()

        # Join or move to the user's channel
        try:
            if state.voice_client and state.voice_client.is_connected():
                if state.voice_client.channel != voice_channel:
                    await state.voice_client.move_to(voice_channel)
            else:
                state.voice_client = await voice_channel.connect()
        except discord.ClientException as e:
            return await interaction.followup.send(f"❌ Could not connect to voice channel: {e}", ephemeral=True)

        # Fetch song info
        try:
            song = await fetch_song(query, str(interaction.user))
        except TrackNotFoundError as e:
            logger.warning(f"Track not found for query '{query}': {e}")
            return await interaction.followup.send(
                f"❌ Could not find or load that track: {e}", ephemeral=True
            )
        except Exception as e:
            logger.error(f"Unexpected error fetching track for query '{query}': {e}")
            return await interaction.followup.send(
                "❌ Something went wrong loading that track. Please try again.", ephemeral=True
            )

        # Play or queue
        if state.voice_client.is_playing() or state.voice_client.is_paused():
            state.queue.append(song)
            embed = discord.Embed(title="📋 Added to Queue", color=discord.Color.blurple())
            embed.add_field(name="Track", value=f"[{song.title}]({song.webpage_url})", inline=False)
            embed.add_field(name="Duration", value=song.duration_str, inline=True)
            embed.add_field(name="Position", value=f"#{len(state.queue)}", inline=True)
            embed.set_footer(text=f"Requested by {song.requester}")
            await interaction.followup.send(embed=embed)
        else:
            state.current = song
            await self._start_playback(state, song, interaction.guild_id)
            embed = discord.Embed(title="🎵 Now Playing", color=discord.Color.green())
            embed.add_field(name="Track", value=f"[{song.title}]({song.webpage_url})", inline=False)
            embed.add_field(name="Duration", value=song.duration_str, inline=True)
            embed.add_field(name="Channel", value=voice_channel.mention, inline=True)
            embed.set_footer(text=f"Requested by {song.requester}")
            await interaction.followup.send(embed=embed)

    # ── /skip ────────────────────────────────────────────────────────────────

    @app_commands.command(name="skip", description="Skip the current song")
    @app_commands.guild_only()
    async def skip(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)

        if not state.voice_client or not state.voice_client.is_playing():
            return await interaction.response.send_message("❌ Nothing is playing right now.", ephemeral=True)
        if not interaction.user.voice or interaction.user.voice.channel != state.voice_client.channel:
            return await interaction.response.send_message("❌ You must be in the same voice channel as the bot.", ephemeral=True)

        skipped = state.current
        state.voice_client.stop()  # triggers _after_play → plays next song

        embed = discord.Embed(title="⏭️ Skipped", color=discord.Color.orange())
        if skipped:
            embed.description = f"Skipped **{skipped.title}**"
        next_up = state.queue[0].title if state.queue else None
        if next_up:
            embed.add_field(name="Up Next", value=next_up, inline=False)
        await interaction.response.send_message(embed=embed)

    # ── /stop ────────────────────────────────────────────────────────────────

    @app_commands.command(name="stop", description="Stop playback and disconnect the bot from voice")
    @app_commands.guild_only()
    async def stop(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)

        if not state.voice_client or not state.voice_client.is_connected():
            return await interaction.response.send_message("❌ The bot is not in a voice channel.", ephemeral=True)
        if not interaction.user.voice or interaction.user.voice.channel != state.voice_client.channel:
            return await interaction.response.send_message("❌ You must be in the same voice channel as the bot.", ephemeral=True)

        state.queue.clear()
        state.current = None
        await state.voice_client.disconnect()
        state.voice_client = None

        await interaction.response.send_message("⏹️ Stopped playback and disconnected.")

    # ── /queue ───────────────────────────────────────────────────────────────

    @app_commands.command(name="queue", description="Show the current music queue")
    @app_commands.guild_only()
    async def queue(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)

        if not state.current and not state.queue:
            return await interaction.response.send_message("📋 The queue is empty.", ephemeral=True)

        embed = discord.Embed(title="📋 Music Queue", color=discord.Color.blurple())
        if state.current:
            embed.add_field(
                name="🎵 Now Playing",
                value=f"[{state.current.title}]({state.current.webpage_url}) `{state.current.duration_str}` — {state.current.requester}",
                inline=False,
            )
        if state.queue:
            lines = []
            for i, song in enumerate(state.queue[:10], start=1):
                lines.append(f"`{i}.` [{song.title}]({song.webpage_url}) `{song.duration_str}` — {song.requester}")
            if len(state.queue) > 10:
                lines.append(f"*…and {len(state.queue) - 10} more*")
            embed.add_field(name="Up Next", value="\n".join(lines), inline=False)

        await interaction.response.send_message(embed=embed)

    # ── /nowplaying ──────────────────────────────────────────────────────────

    @app_commands.command(name="nowplaying", description="Show the currently playing song")
    @app_commands.guild_only()
    async def nowplaying(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild_id)

        if not state.current:
            return await interaction.response.send_message("❌ Nothing is playing right now.", ephemeral=True)

        song = state.current
        embed = discord.Embed(title="🎵 Now Playing", color=discord.Color.green())
        embed.add_field(name="Track", value=f"[{song.title}]({song.webpage_url})", inline=False)
        embed.add_field(name="Duration", value=song.duration_str, inline=True)
        embed.add_field(name="Queued songs", value=str(len(state.queue)), inline=True)
        embed.set_footer(text=f"Requested by {song.requester}")
        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Auto-disconnect if the bot is left alone in a voice channel."""
        if member == self.bot.user:
            return
        state = self.get_state(member.guild.id)
        if not state.voice_client or not state.voice_client.is_connected():
            return
        if before.channel == state.voice_client.channel:
            remaining = [m for m in state.voice_client.channel.members if not m.bot]
            if not remaining:
                await asyncio.sleep(30)  # wait 30 s in case someone rejoins
                remaining = [m for m in state.voice_client.channel.members if not m.bot]
                if not remaining:
                    state.queue.clear()
                    state.current = None
                    await state.voice_client.disconnect()
                    state.voice_client = None


async def setup(bot):
    await bot.add_cog(Music(bot))
