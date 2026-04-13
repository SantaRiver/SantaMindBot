import os
import base64
import logging
from datetime import datetime

import requests
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ─── Config ───────────────────────────────────────────────
BOT_TOKEN    = os.environ["BOT_TOKEN"]
CHAT_ID      = int(os.environ["CHAT_ID"])
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO  = os.environ["GITHUB_REPO"]
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
INBOX_PATH   = os.environ.get("INBOX_PATH", "00_inbox")

# ─── Logging ──────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

logger.info("=== Bot starting ===")
logger.info("CHAT_ID from env: %s", CHAT_ID)
logger.info("GITHUB_REPO: %s", GITHUB_REPO)
logger.info("GITHUB_BRANCH: %s", GITHUB_BRANCH)
logger.info("INBOX_PATH: %s", INBOX_PATH)


# ─── GitHub ───────────────────────────────────────────────
def push_note(filename: str, content: str) -> bool:
    """Create a file in the GitHub repo via Contents API."""
    url = (
        f"https://api.github.com/repos/{GITHUB_REPO}"
        f"/contents/{INBOX_PATH}/{filename}"
    )
    logger.info("GitHub PUT → %s", url)
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "message": f"inbox: {filename}",
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        "branch": GITHUB_BRANCH,
    }
    try:
        resp = requests.put(url, json=payload, headers=headers, timeout=10)
        logger.info("GitHub response: %s", resp.status_code)
        if resp.status_code not in (200, 201):
            logger.error("GitHub error body: %s", resp.text[:500])
            return False
        logger.info("GitHub ✓ file created")
        return True
    except Exception as e:
        logger.error("GitHub request failed: %s", e)
        return False


# ─── Note builder ─────────────────────────────────────────
def build_note(text: str, dt: datetime) -> tuple[str, str]:
    """Return (filename, markdown content)."""
    filename = dt.strftime("%Y-%m-%d_%H-%M-%S") + ".md"
    content = (
        f"---\n"
        f"date: {dt.strftime('%Y-%m-%d')}\n"
        f"source: telegram\n"
        f"---\n\n"
        f"{text}\n"
    )
    return filename, content


# ─── Handler ──────────────────────────────────────────────
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("--- on_message called ---")

    msg = update.message or update.channel_post

    if not msg:
        logger.warning("No message and no channel_post, skipping")
        return

    logger.info("Incoming chat_id: %s (expected: %s)", msg.chat_id, CHAT_ID)
    logger.info("Chat type: %s", msg.chat.type)

    # from_user отсутствует в каналах
    if msg.from_user:
        logger.info("From user: %s (id=%s)", msg.from_user.username, msg.from_user.id)
    else:
        logger.info("From user: (channel post, no user)")

    if msg.chat_id != CHAT_ID:
        logger.warning("chat_id mismatch! got=%s expected=%s — ignoring", msg.chat_id, CHAT_ID)
        return

    text = (msg.text or msg.caption or "").strip()
    logger.info("Text: %r", text[:100] if text else "")

    if not text:
        logger.warning("Empty text, skipping")
        return

    now = datetime.now()
    filename, content = build_note(text, now)
    logger.info("→ pushing %s", filename)

    if push_note(filename, content):
        logger.info("✓ pushed successfully")
    else:
        logger.error("✗ push failed")
        await msg.reply_text("⚠️ Не сохранилось — проверь логи Railway")

# ─── Entry point ──────────────────────────────────────────
def main():
    logger.info("Building application...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POSTS & filters.TEXT, on_message))
    logger.info("Bot running, waiting for messages...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()