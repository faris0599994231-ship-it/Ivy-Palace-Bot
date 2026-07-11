import logging
from threading import Thread

from flask import Flask

logger = logging.getLogger("discord_bot.keep_alive")

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is alive!"


def _run():
    # Keep Flask's per-request access log out of the bot's console output.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    app.run(host="0.0.0.0", port=8000)


def keep_alive():
    """Start a tiny Flask server in a background thread.

    This gives external uptime pingers (or a health check) an HTTP
    endpoint to hit so the process is known to be alive, independent of
    the Discord gateway connection.
    """
    thread = Thread(target=_run, daemon=True)
    thread.start()
    logger.info("keep_alive Flask server started on port 8000")
