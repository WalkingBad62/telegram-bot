from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import RetryAfter
from datetime import datetime
import requests
import asyncio
import logging
import os
from dotenv import load_dotenv

# Load env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
BACKEND_URL = "http://127.0.0.1:8000"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ---------------- START ----------------
async def start(update, context):
    await update.message.reply_text(
        "Hello miya vai 😄\nBot is running safely 🔐"
    )

# ---------------- MESSAGE HANDLER ----------------
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

        reply = r.json().get("reply", "Backend error 😅")

    except Exception as e:
        logging.error(e)
        reply = "Server busy 😅"

    await update.message.reply_text(reply)

# ---------------- AUTO RETARGET JOB ----------------
async def retarget_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        r = requests.get(f"{BACKEND_URL}/retarget/users", timeout=3)
        users = r.json().get("users", [])
    except Exception as e:
        logging.error(f"Retarget fetch failed: {e}")
        return

    for uid in users:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text="👋 Hey miya vai! We miss you 😄\nCome back and chat with us!"
            )
            await asyncio.sleep(2)  # flood safety

        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)

        except Exception as e:
            logging.error(f"Retarget send failed {uid}: {e}")

# ---------------- MANUAL BROADCAST ----------------
async def broadcast(update, context):
    await update.message.reply_text("Broadcast started 🚀")

    try:
        r = requests.get(f"{BACKEND_URL}/retarget/users", timeout=5)
        users = r.json().get("users", [])
    except Exception as e:
        logging.error(f"Broadcast fetch failed: {e}")
        await update.message.reply_text("Backend down ❌")
        return

    for uid in users:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text="🔥 New update available miya vai 💰"
            )
            await asyncio.sleep(2)

        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)

        except Exception as e:
            logging.error(f"Broadcast send failed {uid}: {e}")

    await update.message.reply_text("Broadcast done ✅")

# ---------------- APP SETUP ----------------
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("broadcast", broadcast))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# ⏱ Auto retarget every 10 seconds
app.job_queue.run_repeating(retarget_job, interval=10, first=5)

print("🤖 Bot running safely...")
app.run_polling()
