from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.error import RetryAfter
from datetime import datetime
import requests
import asyncio
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
BACKEND_URL = "http://127.0.0.1:8000"

# Logging setup
logging.basicConfig(
    filename="bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Start command
async def start(update, context):
    await update.message.reply_text(
        "Hello miya vai 😄\nBot is running safely 🔐"
    )

# Message handler
async def handle_message(update, context):
    user = update.message.from_user
    text = update.message.text

    data = {
        "telegram_id": user.id,
        "username": user.username or "Unknown",
        "last_message_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        requests.post(f"{BACKEND_URL}/user/store", json=data, timeout=3)
        r = requests.post(
            f"{BACKEND_URL}/reply/get",
            json={"text": text},
            timeout=3
        )
        reply = r.json().get("reply", "Backend issue 😅")

    except Exception as e:
        logging.error(f"Backend error: {e}")
        reply = "Server busy 😅 Try later."

    await update.message.reply_text(reply)

# Broadcast command
async def broadcast(update, context):
    await update.message.reply_text("Broadcast started 🚀")

    try:
        r = requests.get(f"{BACKEND_URL}/retarget/users", timeout=5)
        users = r.json().get("users", [])
    except Exception as e:
        logging.error(f"User fetch failed: {e}")
        await update.message.reply_text("Backend down ❌")
        return

    for uid in users:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text="🔥 Hey miya vai! New update available 💰"
            )
            await asyncio.sleep(1.5)

        except RetryAfter as e:
            logging.warning(f"FloodWait: sleeping {e.retry_after}")
            await asyncio.sleep(e.retry_after)

        except Exception as e:
            logging.error(f"Send failed {uid}: {e}")

    await update.message.reply_text("Broadcast done ✅")

# App setup
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🤖 Bot running safely...")
app.run_polling()