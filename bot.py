from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters
)
from telegram.error import RetryAfter
from datetime import datetime
import asyncio
import ast
import json
import logging
import os
import requests
from dotenv import load_dotenv

# ================= ENV =================
load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
BOT_MODE = (os.getenv("BOT_MODE", "currency") or "currency").strip().lower()
if BOT_MODE not in ("currency", "trading"):
    BOT_MODE = "currency"
MODE_SUFFIX = BOT_MODE.upper()
TOKEN = os.getenv(f"BOT_TOKEN_{MODE_SUFFIX}") or os.getenv("BOT_TOKEN")

# ================= ADMIN =================
ADMIN_IDS = [8544013336]
def is_admin(uid): return uid in ADMIN_IDS

# ================= LOG =================
logging.basicConfig(level=logging.INFO)

# ================= MEMORY =================
custom_commands = {}
AWAIT_IMAGEAI_KEY = "await_imageai"
AWAIT_CURRENCY_KEY = "await_currency_pair"
AWAIT_TIMEFRAME_KEY = "await_timeframe"
AWAIT_FUTURESIGNAL_PAIR_KEY = "await_futuresignal_pair"
AWAIT_FUTURESIGNAL_TIMEFRAME_KEY = "await_futuresignal_timeframe"
VALID_TIMEFRAMES = {"1", "2", "5", "15", "30", "60"}

CURRENCY_PAIRS = {
    "EURUSD": {"price": 1.19, "link": "http://currency.com/buy/EURUSD/"},
    "USDJPY": {"price": 150.25, "link": "http://currency.com/buy/USDJPY/"},
    "AUDCAD": {"price": 0.91, "link": "http://currency.com/buy/AUDCAD/"},
    "CHFUSD": {"price": 1.12, "link": "http://currency.com/buy/CHFUSD/"},
    "AUDCAD_OTC": {"price": 0.89, "link": "http://currency.com/buy/AUDCAD_otc/"},
    "BTCUSD": {"price": 43000.0, "link": "http://currency.com/buy/BTCUSD/"},
}
CURRENCY_PAIR_CHOICES = {
    "1": "EURUSD",
    "2": "USDJPY",
    "3": "AUDCAD",
    "4": "CHFUSD",
    "5": "AUDCAD_OTC",
    "6": "BTCUSD",
}
CURRENCY_PAIR_DISPLAY = {"AUDCAD_OTC": "AUDCAD_otc"}

def display_pair_name(pair: str) -> str:
    return CURRENCY_PAIR_DISPLAY.get(pair, pair)

def build_default_start_message(mode: str) -> str:
    if mode == "trading":
        return (
            "\U0001f680 Welcome to the YOO/twExSavage Trading Edge!\n"
            "Ready to stop guessing and start winning on Pocket Option? "
            "I've helped 500+ traders turn their first deposit into a consistent daily income. "
            "https://tinyurl.com/twExSavage\n\n"
            "Why Join Us?\n"
            "\u26a1 Pro Signals: 90%+ Accuracy.\n"
            "\U0001f4ca Live Coaching: Learn while you earn.\n"
            "\U0001f4b0 Pocket Option Bonus: Use code [HEYYOO] for a 50% deposit bonus!\n"
            "How to start: > 1. Register via the link below\n\n"
            "WORLDWIDE LINK\U0001f310\nhttps://tinyurl.com/twExSavage\n"
            "RUSSIAN LINK\U0001f1f7\U0001f1fa\nhttps://tinyurl.com/twExSavageRU\n"
            "2. Send me your Pocket Option ID to verify.\n"
            "3. Get added to the Private Couching Room instantly.\n\n"
            "You can use this following feature:\n\n"
            "1. Future Signal: /futuresignal\n"
            "2. YooAI: /yooai\n\n"
            "CONTACT TRADERS @YOO_SUPPORT1"
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

def fetch_currency_signal(pair: str, timeframe: int):
    try:
        res = requests.post(
            f"{BACKEND_URL}/currency/signal",
            json={"pair": pair, "timeframe": timeframe},
            timeout=15
        )
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None

def format_signal_result(data):
    if not isinstance(data, dict):
        return "Signal data unavailable."
    if "error" in data:
        return f"Error: {data['error']}"
    pair = data.get("pair", "N/A")
    timeframe = data.get("timeframe", "N/A")
    signal = data.get("signal", "N/A")
    entry = data.get("entry_price")
    tp = data.get("take_profit")
    sl = data.get("stop_loss")
    confidence = data.get("confidence", "N/A")
    return (
        f"\U0001f4ca Signal for {display_pair_name(pair)} ({timeframe}min)\n\n"
        f"Signal: {signal}\n"
        f"Entry Price: {format_analysis_price(entry) if entry is not None else 'N/A'}\n"
        f"Take Profit: {format_analysis_price(tp) if tp is not None else 'N/A'}\n"
        f"Stop Loss: {format_analysis_price(sl) if sl is not None else 'N/A'}\n"
        f"Confidence: {confidence}%"
    )

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
    entry = get_ci(analysis, "entry_price")
    take_profit = get_ci(analysis, "take_profit_price")
    stop_loss = get_ci(analysis, "stop_loss_price")
    support = get_ci(analysis, "support_zone_price")
    resistance = get_ci(analysis, "resistance_zone_price")

    rows = [
        f"Pair: {pair_text}",
        f"Current Trend: {trend_text}",
        f"Signal: {signal_text}",
        f"Signal Strength: {strength_text}",
        f"Chart Pattern: {pattern_text}",
        f"Chart Type: {chart_type_text}",
        f"Entry Price: {format_analysis_price(entry) if is_present(entry) else 'N/A'}",
        f"Take Profit Price: {format_analysis_price(take_profit) if is_present(take_profit) else 'N/A'}",
        f"Stop Loss Price: {format_analysis_price(stop_loss) if is_present(stop_loss) else 'N/A'}",
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

# ================= REMOVE MENU =================
async def remove_menu(app):
    await app.bot.set_my_commands([])

# ================= SAWA COMMAND =================
async def sawa(update, context):
    await store_user(update)
    await update.message.reply_text("Sawa! 😄")

# ================= AIDI COMMAND =================
async def aidi(update, context):
    await store_user(update)
    user_id = update.message.from_user.id
    await update.message.reply_text(f"Your Telegram ID: {user_id}")

# ================= START =================
async def start(update, context):
    await store_user(update)
    await update.message.reply_text(fetch_start_message())

# ================= IMAGEAI COMMAND =================
async def imageai(update, context):
    await store_user(update)
    context.user_data[AWAIT_IMAGEAI_KEY] = True
    await update.message.reply_text("Please Upload your image")

# ================= CURRENCY CONVERTER COMMAND =================
async def currencycoveter(update, context):
    await store_user(update)
    pair_list = "\n".join(
        f"{k}. {display_pair_name(v)}" for k, v in CURRENCY_PAIR_CHOICES.items()
    )
    context.user_data[AWAIT_CURRENCY_KEY] = True
    await update.message.reply_text(
        f"Please Choose a Pair of Currency\n\n{pair_list}"
    )

# ================= FUTURE SIGNAL COMMAND =================
async def futuresignal(update, context):
    await store_user(update)
    pair_list = "\n".join(
        f"{k}. {display_pair_name(v)}" for k, v in CURRENCY_PAIR_CHOICES.items()
    )
    context.user_data[AWAIT_FUTURESIGNAL_PAIR_KEY] = True
    await update.message.reply_text(
        f"Please Choose a Pair for Signal\n\n{pair_list}"
    )

# ================= STORE USER =================
async def store_user(update):
    user = update.message.from_user
    data = {
        "telegram_id": user.id,
        "username": user.username or "Unknown",
        "last_message_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        requests.post(f"{BACKEND_URL}/user/store", json=data, timeout=5)
    except:
        pass

# ================= NORMAL MESSAGE =================
async def normal_message(update, context):
    await store_user(update)

    # Admin retarget: forward text to target users
    if is_admin(update.message.from_user.id):
        if "retarget_user" in context.user_data or "retarget_all" in context.user_data:
            await admin_media_handler(update, context)
            return

    # --- Future Signal: pair selection ---
    if context.user_data.get(AWAIT_FUTURESIGNAL_PAIR_KEY):
        raw = (update.message.text or "").strip().upper()
        pair = CURRENCY_PAIR_CHOICES.get(raw, raw)
        if pair in CURRENCY_PAIRS:
            context.user_data.pop(AWAIT_FUTURESIGNAL_PAIR_KEY, None)
            context.user_data["futuresignal_pair"] = pair
            context.user_data[AWAIT_FUTURESIGNAL_TIMEFRAME_KEY] = True
            await update.message.reply_text("Enter the timeframe (1, 2, 5, 15, 30, 60)")
        else:
            pair_names = ", ".join(display_pair_name(p) for p in CURRENCY_PAIRS)
            await update.message.reply_text(
                f"Invalid pair. Please choose one of:\n{pair_names}"
            )
        return

    # --- Future Signal: timeframe selection ---
    if context.user_data.get(AWAIT_FUTURESIGNAL_TIMEFRAME_KEY):
        raw = (update.message.text or "").strip()
        if raw in VALID_TIMEFRAMES:
            context.user_data.pop(AWAIT_FUTURESIGNAL_TIMEFRAME_KEY, None)
            pair = context.user_data.pop("futuresignal_pair", "EURUSD")
            timeframe = int(raw)
            data = fetch_currency_signal(pair, timeframe)
            if data:
                await update.message.reply_text(format_signal_result(data))
            else:
                await update.message.reply_text("Signal not available right now. Please try again later.")
        else:
            await update.message.reply_text("Invalid timeframe. Please enter: 1, 2, 5, 15, 30, or 60")
        return

    # --- Currency Converter: pair selection ---
    if context.user_data.get(AWAIT_CURRENCY_KEY):
        raw = (update.message.text or "").strip().upper()
        pair = CURRENCY_PAIR_CHOICES.get(raw, raw)
        if pair in CURRENCY_PAIRS:
            context.user_data.pop(AWAIT_CURRENCY_KEY, None)
            context.user_data["selected_pair"] = pair
            context.user_data[AWAIT_TIMEFRAME_KEY] = True
            await update.message.reply_text("Enter the timeframe (1, 2, 5, 15, 30, 60)")
        else:
            pair_names = ", ".join(display_pair_name(p) for p in CURRENCY_PAIRS)
            await update.message.reply_text(
                f"Invalid pair. Please choose one of:\n{pair_names}"
            )
        return

    # --- Currency Converter: timeframe selection ---
    if context.user_data.get(AWAIT_TIMEFRAME_KEY):
        raw = (update.message.text or "").strip()
        if raw in VALID_TIMEFRAMES:
            context.user_data.pop(AWAIT_TIMEFRAME_KEY, None)
            pair = context.user_data.pop("selected_pair", "EURUSD")
            timeframe = int(raw)
            data = fetch_currency_signal(pair, timeframe)
            if data:
                await update.message.reply_text(format_signal_result(data))
            else:
                pair_data = fetch_currency_pair(pair) or CURRENCY_PAIRS.get(pair, {})
                price = format_money(pair_data.get("price", ""))
                link = pair_data.get("link", "")
                await update.message.reply_text(
                    f"Pair: {display_pair_name(pair)}\n"
                    f"Timeframe: {timeframe}min\n"
                    f"Price: {price}\n"
                    f"Link: {link}"
                )
        else:
            await update.message.reply_text("Invalid timeframe. Please enter: 1, 2, 5, 15, 30, or 60")
        return

    try:
        res = requests.post(
            f"{BACKEND_URL}/reply/get",
            json={"text": update.message.text},
            timeout=5
        )
        if res.status_code == 200:
            reply = res.json().get("reply")
            if reply:
                await update.message.reply_text(reply)
                return
    except:
        pass

    await update.message.reply_text("???? reply ?????? ???????")

# ================= USER MEDIA HANDLER =================
async def user_media_handler(update, context):
    await store_user(update)

    # Admin retarget: forward media to target users
    if is_admin(update.message.from_user.id):
        if "retarget_user" in context.user_data or "retarget_all" in context.user_data:
            await admin_media_handler(update, context)
            return

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

# ================= ADD CUSTOM COMMAND =================
async def add_command(update, context):
    await store_user(update)
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Admin only")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /add <command> <reply>")
        return

    cmd = context.args[0].lower()
    reply = " ".join(context.args[1:])
    custom_commands[cmd] = reply

    await update.message.reply_text(f"✅ /{cmd} added")

# ================= COMMAND ROUTER =================
async def command_router(update, context):
    await store_user(update)

    cmd = update.message.text.lstrip("/").split()[0].lower()

    if cmd in ["start", "add", "retarget", "retarget_all", "imageai", "gajaai", "yooai", "currencycoveter", "futuresignal"]:
        return

    if cmd in custom_commands:
        await update.message.reply_text(custom_commands[cmd])
    else:
        await update.message.reply_text("❓ Unknown command")

# ================= FETCH USERS =================
def get_users():
    try:
        r = requests.get(f"{BACKEND_URL}/retarget/users", timeout=5)
        return r.json().get("users", [])
    except:
        return []

# ================= RETARGET ALL =================
async def retarget_all(update, context):
    await store_user(update)
    if not is_admin(update.message.from_user.id):
        return

    context.user_data["retarget_all"] = True
    await update.message.reply_text("📢 Now send message / image / video")

# ================= RETARGET ONE =================
async def retarget_user(update, context):
    await store_user(update)
    if not is_admin(update.message.from_user.id):
        return

    if not context.args:
        await update.message.reply_text("❌ User ID dao")
        return

    context.user_data["retarget_user"] = int(context.args[0])
    await update.message.reply_text("🎯 Target set.\nNow send message / image / video")

# ================= ADMIN MEDIA HANDLER =================
async def admin_media_handler(update, context):
    if not is_admin(update.message.from_user.id):
        return

    if "retarget_user" in context.user_data:
        uid = context.user_data.pop("retarget_user")
        await forward_any(update, context, [uid])
        await update.message.reply_text("✅ Retarget sent")
        return

    if "retarget_all" in context.user_data:
        context.user_data.pop("retarget_all")
        users = get_users()
        await forward_any(update, context, users)
        await update.message.reply_text("✅ Broadcast done")

# ================= FORWARD ANY =================
async def forward_any(update, context, users):
    for uid in users:
        try:
            if update.message.text:
                await context.bot.send_message(uid, update.message.text)

            elif update.message.photo:
                await context.bot.send_photo(
                    uid,
                    update.message.photo[-1].file_id,
                    caption=update.message.caption
                )

            elif update.message.video:
                await context.bot.send_video(
                    uid,
                    update.message.video.file_id,
                    caption=update.message.caption
                )

            await asyncio.sleep(2)

        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except:
            pass

# ================= APP =================
app = ApplicationBuilder().token(TOKEN).build()

app.post_init = remove_menu  # 🔥 MENU HIDDEN HERE

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("add", add_command))
app.add_handler(CommandHandler("sawa", sawa))
app.add_handler(CommandHandler("id", aidi))
app.add_handler(CommandHandler("retarget", retarget_user))
app.add_handler(CommandHandler("retarget_all", retarget_all))
app.add_handler(CommandHandler("imageai", imageai))
app.add_handler(CommandHandler("gajaai", imageai))
app.add_handler(CommandHandler("yooai", imageai))
app.add_handler(CommandHandler("futuresignal", futuresignal))
app.add_handler(CommandHandler("currencycoveter", currencycoveter))

app.add_handler(MessageHandler(filters.COMMAND, command_router))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, normal_message))
app.add_handler(MessageHandler(
    filters.PHOTO | filters.VIDEO | filters.ATTACHMENT | filters.AUDIO | filters.VOICE,
    user_media_handler
))

print("🤖 Bot running...")
app.run_polling()
