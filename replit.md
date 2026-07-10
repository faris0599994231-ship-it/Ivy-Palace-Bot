# Discord Bot

A general-purpose Discord bot built with Python and discord.py, featuring moderation, utility, and fun commands.

## Run & Operate

- `cd discord-bot && python main.py` — run the bot (managed via "Discord Bot" workflow)
- Required secret: `DISCORD_BOT_TOKEN` — your bot token from discord.com/developers

## Stack

- Python 3.11 + discord.py 2.x
- Cog-based command architecture
- Prefix commands (`!`) + slash command sync

## Where things live

- `discord-bot/main.py` — entry point, bot setup, event handlers
- `discord-bot/cogs/moderation.py` — kick, ban, unban, timeout, clear, warn
- `discord-bot/cogs/utility.py` — ping, serverinfo, userinfo, avatar, roleinfo, botinfo
- `discord-bot/cogs/fun.py` — roll, flip, 8ball, choose, poll, rps, say
- `discord-bot/cogs/help.py` — custom help command

## Commands

### 🛡️ Moderation (requires permissions)
| Command | Description |
|---|---|
| `!kick @user [reason]` | Kick a member |
| `!ban @user [reason]` | Ban a member |
| `!unban <user_id>` | Unban by user ID |
| `!timeout @user <minutes> [reason]` | Timeout a member |
| `!untimeout @user` | Remove timeout |
| `!clear [amount]` | Delete messages (1–100, default 10) |
| `!warn @user [reason]` | Warn a member via embed + DM |

### 🔧 Utility
| Command | Description |
|---|---|
| `!ping` | Bot latency |
| `!serverinfo` | Server statistics |
| `!userinfo [@user]` | User info |
| `!avatar [@user]` | Display avatar |
| `!roleinfo <role>` | Role details |
| `!botinfo` | Bot statistics |

### 🎉 Fun
| Command | Description |
|---|---|
| `!roll [NdN]` | Roll dice (e.g. `!roll 2d20`) |
| `!flip` | Flip a coin |
| `!8ball <question>` | Ask the magic 8-ball |
| `!choose opt1 \| opt2` | Pick between options |
| `!poll <question>` | Create a ✅/❌ poll |
| `!rps <rock/paper/scissors>` | Play RPS |
| `!say <message>` | Bot repeats your message |

## Architecture decisions

- Cogs pattern keeps commands organized and modular — new features go in a new cog file
- Bot token loaded from `DISCORD_BOT_TOKEN` env secret only — never hardcoded
- Error handling in `on_command_error` covers missing permissions, bad args, and member not found

## User preferences

_Populate as you build._

## Gotchas

- Voice commands require PyNaCl (`pip install discord.py[voice]`) — not installed by default
- `!say` and `!clear` require `manage_messages` permission
- Timeout requires `moderate_members` permission (Discord server setting)
- Bot needs `Message Content Intent` enabled in the Discord Developer Portal (Bot → Privileged Gateway Intents)
- Bot needs `Server Members Intent` enabled for `!userinfo` and online count in `!serverinfo`
