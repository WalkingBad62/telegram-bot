from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import requests
import logging
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Initialize bot application
bot_app = Application.builder().token(TOKEN).build()

@asynccontextmanager
async def lifespan(app):
    await bot_app.initialize()
    yield
    await bot_app.shutdown()

app = FastAPI(lifespan=lifespan)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        requests.post(f"{BACKEND_URL}/user/store", json=data, timeout=5)
        r = requests.post(
            f"{BACKEND_URL}/reply/get",
            json={"text": text},
            timeout=5
        )
        reply = r.json().get("reply", "Backend issue 😅")

    except Exception as e:
        logger.error(f"Backend error: {e}")
        reply = "Server busy 😅 Try later."

    await update.message.reply_text(reply)

# Broadcast command
async def broadcast(update, context):
    await update.message.reply_text("Broadcast started 🚀")

    try:
        r = requests.get(f"{BACKEND_URL}/retarget/users", timeout=10)
        users = r.json().get("users", [])
    except Exception as e:
        logger.error(f"User fetch failed: {e}")
        await update.message.reply_text("Backend down ❌")
        return

    for uid in users:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text="🔥 Hey miya vai! New update available 💰"
            )
            await asyncio.sleep(1.5)

        except Exception as e:
            logger.error(f"Send failed {uid}: {e}")

    await update.message.reply_text("Broadcast done ✅")

# Add handlers
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("broadcast", broadcast))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.post("/webhook")
async def webhook(request: Request):
    """Handle Telegram webhook updates"""
    try:
        data = await request.json()
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error"}

@app.get("/")
async def root():
    return {"message": "Bot webhook server is running"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)