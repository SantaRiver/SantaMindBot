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
GITHUB_REPO  = os.environ["GITHUB_REPO"]   # "username/vault-repo"
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
INBOX_PATH   = os.environ.get("INBOX_PATH", "00_inbox")

# ─── Logging ──────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─── GitHub ───────────────────────────────────────────────
def push_note(filename: str, content: str) -> bool:
    """Create a file in the GitHub repo via Contents API."""
    url = (
        f"https://api.github.com/repos/{GITHUB_REPO}"
        f"/contents/{INBOX_PATH}/{filename}"
    )
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
    resp = requests.put(url, json=payload, headers=headers, timeout=10)
    if resp.status_code not in (200, 201):
        logger.error("GitHub %s: %s", resp.status_code, resp.text[:200])
        return False
    return True


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
    msg = update.message
    if not msg or msg.chat_id != CHAT_ID:
        return

    text = (msg.text or msg.caption or "").strip()
    if not text:
        return

    now = datetime.now()
    filename, content = build_note(text, now)

    logger.info("→ %s", filename)

    if push_note(filename, content):
        # Тихий успех — не засоряем чат ответами
        logger.info("✓ pushed")
    else:
        await msg.reply_text("⚠️ Не сохранилось — проверь логи Railway")


# ─── Entry point ──────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    logger.info("Bot running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
