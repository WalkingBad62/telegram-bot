from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters
)
from telegram.error import RetryAfter
from datetime import datetime
import asyncio
import logging
import os
import requests
from dotenv import load_dotenv

# ================= ENV =================
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
BACKEND_URL = "http://127.0.0.1:8000"

# ================= ADMIN =================
ADMIN_IDS = [8544013336]
def is_admin(uid): return uid in ADMIN_IDS

# ================= LOG =================
logging.basicConfig(level=logging.INFO)

# ================= MEMORY =================
custom_commands = {}
AWAIT_IMAGEAI_KEY = "await_imageai"
AWAIT_CURRENCY_KEY = "await_currency_pair"

CURRENCY_PAIRS = {
    "EURUSD": {"price": "1.19", "link": "http://currency.com/buy/EURUSD/"},
    "USDJPY": {"price": "N/A", "link": "http://currency.com/buy/USDJPY/"},
    "AUDCAD": {"price": "N/A", "link": "http://currency.com/buy/AUDCAD/"},
    "CHFUSD": {"price": "N/A", "link": "http://currency.com/buy/CHFUSD/"},
    "BTCUSD": {"price": "N/A", "link": "http://currency.com/buy/BTCUSD/"},
}

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
    await update.message.reply_text(
        "Welcome To Currency Exchange Bot\n\n"
        "User Register and create our account through http://currency.com/"
    )
    await update.message.reply_text(
        "You can use this following feature:\n\n"
        "1. ImageAI: /imageai\n"
        "2. Convert Currency: /currencycoveter"
    )

# ================= IMAGEAI COMMAND =================
async def imageai(update, context):
    await store_user(update)
    context.user_data[AWAIT_IMAGEAI_KEY] = True
    await update.message.reply_text("Please Upload your image")

# ================= CURRENCY CONVERTER COMMAND =================
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

    if context.user_data.get(AWAIT_CURRENCY_KEY):
        pair = (update.message.text or "").strip().upper()
        if pair in CURRENCY_PAIRS:
            context.user_data.pop(AWAIT_CURRENCY_KEY, None)
            info = CURRENCY_PAIRS[pair]
            await update.message.reply_text(
                f"Price: {info['price']}\n"
                f"link: {info['link']}"
            )
        else:
            await update.message.reply_text(
                "Invalid pair. Please choose one of:\n"
                "EURUSD, USDJPY, AUDCAD, CHFUSD, BTCUSD"
            )
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

    if cmd in ["start", "add", "retarget", "retarget_all", "imageai", "currencycoveter"]:
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
app.add_handler(CommandHandler("aidi", aidi))
app.add_handler(CommandHandler("retarget", retarget_user))
app.add_handler(CommandHandler("retarget_all", retarget_all))
app.add_handler(CommandHandler("imageai", imageai))
app.add_handler(CommandHandler("currencycoveter", currencycoveter))

app.add_handler(MessageHandler(filters.COMMAND, command_router))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, normal_message))
app.add_handler(MessageHandler(
    filters.PHOTO | filters.VIDEO | filters.ATTACHMENT | filters.AUDIO | filters.VOICE,
    user_media_handler
))

print("🤖 Bot running...")
app.run_polling()
