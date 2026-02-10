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

AWAIT_IMAGEAI_KEY = "await_imageai"
AWAIT_CURRENCY_KEY = "await_currency_pair"

CURRENCY_PAIRS = {
    "EURUSD": {"price": "1.19", "link": "http://currency.com/buy/EURUSD/"},
    "USDJPY": {"price": "N/A", "link": "http://currency.com/buy/USDJPY/"},
    "AUDCAD": {"price": "N/A", "link": "http://currency.com/buy/AUDCAD/"},
    "CHFUSD": {"price": "N/A", "link": "http://currency.com/buy/CHFUSD/"},
    "BTCUSD": {"price": "N/A", "link": "http://currency.com/buy/BTCUSD/"},
}

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

async def store_user(update):
    user = update.message.from_user
    data = {
        "telegram_id": user.id,
        "username": user.username or "Unknown",
        "last_message_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        requests.post(f"{BACKEND_URL}/user/store", json=data, timeout=5)
    except Exception:
        pass

# Start command
async def start(update, context):
    await store_user(update)
    await update.message.reply_text(
        "Welcome To Currency Exchange Bot\n\n"
        "User Register and create our account through http://currency.com/"
    )
    await update.message.reply_text(
        "You can use this following feature:\n\n"
        "1. ImageAI: /imageai\n"
        "2. Convert Currency: /currencycoveter"
    )

# ImageAI command
async def imageai(update, context):
    await store_user(update)
    context.user_data[AWAIT_IMAGEAI_KEY] = True
    await update.message.reply_text("Please Upload your image")

# Currency converter command
async def currencycoveter(update, context):
    await store_user(update)
    context.user_data[AWAIT_CURRENCY_KEY] = True
    await update.message.reply_text(
        "Please Choose a Pair of Currency\n\n"
        "1. EURUSD\n"
        "2. USDJPY\n"
        "3. AUDCAD\n"
        "4. CHFUSD\n"
        "5. BTCUSD"
    )

# Message handler
async def handle_message(update, context):
    await store_user(update)
    text = update.message.text or ""

    if context.user_data.get(AWAIT_CURRENCY_KEY):
        pair = text.strip().upper()
        if pair in CURRENCY_PAIRS:
            context.user_data.pop(AWAIT_CURRENCY_KEY, None)
            info = CURRENCY_PAIRS[pair]
            await update.message.reply_text(
                f"Price: {info[\'price\']}\n"
                f"link: {info[\'link\']}"
            )
        else:
            await update.message.reply_text(
                "Invalid pair. Please choose one of:\n"
                "EURUSD, USDJPY, AUDCAD, CHFUSD, BTCUSD"
            )
        return

    try:
        r = requests.post(
            f"{BACKEND_URL}/reply/get",
            json={"text": text},
            timeout=5
        )
        reply = r.json().get("reply", "Backend issue")

    except Exception as e:
        logger.error(f"Backend error: {e}")
        reply = "Server busy. Try later."

    await update.message.reply_text(reply)

# Media handler
async def media_handler(update, context):
    await store_user(update)

    if context.user_data.get(AWAIT_IMAGEAI_KEY):
        if update.message.photo:
            context.user_data.pop(AWAIT_IMAGEAI_KEY, None)
            await update.message.reply_text(
                "Currency: USD\n"
                "Price: $90\n"
                "Discount: $10"
            )
        else:
            await update.message.reply_text("Please upload an image.")
        return

    if update.message.photo:
        await update.message.reply_text("Image received!")
    elif update.message.video:
        await update.message.reply_text("Video received!")
    elif update.message.document:
        await update.message.reply_text("File received!")
    elif update.message.audio:
        await update.message.reply_text("Audio received!")
    elif update.message.voice:
        await update.message.reply_text("Voice message received!")
    else:
        await update.message.reply_text("Attachment received!")

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
bot_app.add_handler(CommandHandler("imageai", imageai))
bot_app.add_handler(CommandHandler("currencycoveter", currencycoveter))
bot_app.add_handler(CommandHandler("broadcast", broadcast))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
bot_app.add_handler(MessageHandler(
    filters.PHOTO | filters.VIDEO | filters.ATTACHMENT | filters.AUDIO | filters.VOICE,
    media_handler
))

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
