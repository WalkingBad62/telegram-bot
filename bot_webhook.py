from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import requests
import logging
import ast
import json
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
BOT_MODE = (os.getenv("BOT_MODE", "currency") or "currency").strip().lower()
if BOT_MODE not in ("currency", "trading"):
    BOT_MODE = "currency"
MODE_SUFFIX = BOT_MODE.upper()
TOKEN = os.getenv(f"BOT_TOKEN_{MODE_SUFFIX}") or TOKEN

AWAIT_IMAGEAI_KEY = "await_imageai"
AWAIT_CURRENCY_KEY = "await_currency_pair"

CURRENCY_PAIRS = {
    "EURUSD": {"price": 1.19, "link": "http://currency.com/buy/EURUSD/"},
    "USDJPY": {"price": 150.25, "link": "http://currency.com/buy/USDJPY/"},
    "AUDCAD": {"price": 0.91, "link": "http://currency.com/buy/AUDCAD/"},
    "CHFUSD": {"price": 1.12, "link": "http://currency.com/buy/CHFUSD/"},
    "BTCUSD": {"price": 43000.0, "link": "http://currency.com/buy/BTCUSD/"},
}
CURRENCY_PAIR_CHOICES = {
    "1": "EURUSD",
    "2": "USDJPY",
    "3": "AUDCAD",
    "4": "CHFUSD",
    "5": "BTCUSD",
}

def build_default_start_message(mode: str) -> str:
    if mode == "trading":
        return (
            "Welcome To Trading Bot\n\n"
            "Upload your chart screenshot for instant analysis.\n\n"
            "You can use this following feature:\n"
            "1. GajaAI: /gajaai"
        )
    return (
        "Welcome To Currency Exchange Bot\n\n"
        "User Register and create our account through http://currency.com/\n\n"
        "You can use this following feature:\n"
        "1. GajaAI: /gajaai\n"
        "2. Convert Currency: /currencycoveter"
    )

DEFAULT_START_MESSAGE = build_default_start_message(BOT_MODE)

def fetch_start_message():
    try:
        res = requests.get(f"{BACKEND_URL}/settings/start-message", timeout=5)
        if res.status_code == 200:
            msg = res.json().get("message")
            if msg:
                return msg
    except Exception:
        pass
    return DEFAULT_START_MESSAGE

def fetch_currency_pair(pair: str):
    try:
        res = requests.get(f"{BACKEND_URL}/currency/pair/{pair}", timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None

def format_money(value):
    try:
        val = float(value)
        if val.is_integer():
            return str(int(val))
        return f"{val:.2f}"
    except Exception:
        return str(value)

def fetch_imageai_price(file_bytes, filename):
    try:
        files = {"file": (filename, file_bytes)}
        res = requests.post(f"{BACKEND_URL}/gajaai/price", files=files, timeout=10)
        if res.status_code == 200:
            return res.json()
        try:
            data = res.json()
            detail = data.get("detail", data)
        except Exception:
            detail = res.text
        return {"error": detail}
    except Exception:
        pass
    return None

def format_analysis_value(value):
    if isinstance(value, dict):
        parts = []
        for key, val in value.items():
            parts.append(f"{key}: {val}")
        return "\n".join(parts)
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)

def format_analysis_price(value):
    try:
        return f"{float(value):.4f}"
    except Exception:
        return str(value)

def title_text(value):
    text = str(value or "").replace("_", " ").strip()
    return text.title() if text else ""

def is_present(value):
    return value not in (None, "", [], {})

def get_ci(mapping, key):
    key_l = key.lower()
    for k, v in mapping.items():
        if str(k).lower() == key_l:
            return v
    return None

def parse_maybe_json(value):
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    try:
        return json.loads(text)
    except Exception:
        pass
    try:
        return ast.literal_eval(text)
    except Exception:
        return value

def unwrap_trading_analysis(analysis):
    analysis = parse_maybe_json(analysis)
    if not isinstance(analysis, dict):
        return analysis
    success = get_ci(analysis, "success")
    if success is False:
        message = get_ci(analysis, "message") or get_ci(analysis, "detail") or "analysis failed"
        return {"_error": f"Trading analysis failed: {message}"}
    nested_analysis = get_ci(analysis, "analysis")
    if nested_analysis is not None:
        nested_analysis = parse_maybe_json(nested_analysis)
        if isinstance(nested_analysis, dict):
            analysis = nested_analysis
    for key in ("TradingAnalysis", "trading_analysis", "result", "data"):
        nested = get_ci(analysis, key)
        nested = parse_maybe_json(nested)
        if isinstance(nested, dict):
            analysis = nested
            break
    return analysis

def build_trading_summary(analysis):
    analysis = unwrap_trading_analysis(analysis)

    if not isinstance(analysis, dict):
        return format_analysis_value(analysis)
    if analysis.get("_error"):
        return analysis.get("_error")

    pair = get_ci(analysis, "pair")
    if not is_present(pair):
        pair = get_ci(analysis, "symbol")
    pair_text = str(pair) if is_present(pair) else "N/A"

    trend = title_text(get_ci(analysis, "current_trend") or get_ci(analysis, "trend"))
    trend_text = trend if trend else "N/A"
    signal = str(get_ci(analysis, "signal") or "").upper().strip()
    signal_text = signal if signal else "N/A"
    strength = get_ci(analysis, "signal_strength")
    strength_text = f"{strength}%" if is_present(strength) else "N/A"
    pattern = title_text(get_ci(analysis, "chart_pattern"))
    pattern_text = pattern if pattern else "N/A"
    chart_type = title_text(get_ci(analysis, "chart_type"))
    chart_type_text = chart_type if chart_type else "N/A"
    support = get_ci(analysis, "support_zone_price")
    resistance = get_ci(analysis, "resistance_zone_price")

    rows = [
        f"Pair: {pair_text}",
        f"Current Trend: {trend_text}",
        f"Signal: {signal_text}",
        f"Signal Strength: {strength_text}",
        f"Chart Pattern: {pattern_text}",
        f"Chart Type: {chart_type_text}",
        f"Support Zone Price: {format_analysis_price(support) if is_present(support) else 'N/A'}",
        f"Resistance Zone Price: {format_analysis_price(resistance) if is_present(resistance) else 'N/A'}",
    ]

    known_keys = {
        "pair", "current_trend", "signal", "signal_strength", "chart_pattern", "chart_type",
        "entry_price", "take_profit_price", "stop_loss_price", "support_zone_price", "resistance_zone_price",
        "symbol", "trend",
    }
    for key, value in analysis.items():
        if str(key).lower() in known_keys:
            continue
        if not is_present(value):
            continue
        rows.append(f"{title_text(key)}: {value}")

    return "\n".join(rows)

def build_ai_reply(data):
    if not isinstance(data, dict):
        return "Image processed, but response format is invalid."
    if "error" in data:
        return f"Error: {data.get('error')}"
    if data.get("mode") == "trading" or "analysis" in data:
        analysis = data.get("analysis")
        if analysis is None:
            analysis = data
        return build_trading_summary(analysis)
    currency = data.get("currency", "USD")
    price = format_money(data.get("price", ""))
    discount = format_money(data.get("discount", ""))
    return (
        f"Currency: {currency}\n"
        f"Price: ${price}\n"
        f"Discount: ${discount}"
    )

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
    await update.message.reply_text(fetch_start_message())

# ImageAI command
async def imageai(update, context):
    await store_user(update)
    context.user_data[AWAIT_IMAGEAI_KEY] = True
    await update.message.reply_text("Please Upload your image")

# Currency converter command
async def currencycoveter(update, context):
    await store_user(update)
    if BOT_MODE == "trading":
        await update.message.reply_text("This command is available in currency bot only.")
        return
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
        raw = text.strip().upper()
        pair = CURRENCY_PAIR_CHOICES.get(raw, raw)
        if pair in CURRENCY_PAIRS:
            context.user_data.pop(AWAIT_CURRENCY_KEY, None)
            data = fetch_currency_pair(pair) or {
                "price": CURRENCY_PAIRS[pair]["price"],
                "link": CURRENCY_PAIRS[pair]["link"],
            }
            price = format_money(data.get("price", ""))
            link = data.get("link", CURRENCY_PAIRS[pair]["link"])
            await update.message.reply_text(
                f"Price: {price}\n"
                f"link: {link}"
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
            try:
                photo = update.message.photo[-1]
                tg_file = await photo.get_file()
                file_bytes = await tg_file.download_as_bytearray()
                data = fetch_imageai_price(bytes(file_bytes), f"{photo.file_unique_id}.jpg")
                if data:
                    await update.message.reply_text(build_ai_reply(data))
                else:
                    await update.message.reply_text("Image processed, but result not available.")
            except Exception:
                await update.message.reply_text("Image processed, but result not available.")
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
bot_app.add_handler(CommandHandler("gajaai", imageai))
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
