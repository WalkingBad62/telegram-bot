from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from telegram import BotCommand
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

# ================= START =================
async def start(update, context):
    await update.message.reply_text("Hello miya vai 😄\nBot is alive ✅")

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
    import re
    def normalize(text):
        return re.sub(r'[^a-z0-9 ]', '', text.strip().lower())

    user_text = normalize(update.message.text)
    print(f"[DEBUG] User text: {user_text}")
    try:
        res = requests.get(f"{BACKEND_URL}/replies")
        print(f"[DEBUG] Backend /replies status: {res.status_code}")
        if res.status_code == 200:
            replies = res.json().get("replies", [])
            print(f"[DEBUG] Replies fetched: {replies}")
            for r in replies:
                if r["active"]:
                    q_norm = normalize(r["question"])
                    print(f"[DEBUG] Comparing user_text='{user_text}' to q_norm='{q_norm}'")
                    if user_text == q_norm:
                        print(f"[DEBUG] Match found! Reply: {r['reply']}")
                        await update.message.reply_text(r["reply"])
                        return
    except Exception as e:
        print("Reply fetch error:", e)
    print("[DEBUG] No match found. Sending fallback message.")
    await update.message.reply_text("Menu খুলে command use করো miya vai 😄")

# ================= ADD CUSTOM COMMAND =================
async def add_command(update, context):
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("❌ Admin only")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /add <command> <reply>")
        return
    cmd = context.args[0].lower()
    reply = " ".join(context.args[1:])
    custom_commands[cmd] = reply
    await update_menu(context.application)
    await update.message.reply_text(f"✅ /{cmd} added")

# ================= COMMAND ROUTER =================
async def command_router(update, context):
    await store_user(update)
    cmd = update.message.text.lstrip("/").split()[0].lower()
    if cmd in ["start", "add", "retarget", "retarget_all"]:
        return
    if cmd in custom_commands:
        await update.message.reply_text(custom_commands[cmd])
    else:
        await update.message.reply_text("❓ Unknown command")

# ================= UPDATE MENU =================
async def update_menu(app):
    cmds = [
        BotCommand("start", "Start bot"),
        BotCommand("add", "Add custom command (admin)"),
        BotCommand("retarget", "Admin retarget specific user"),
        BotCommand("retarget_all", "Admin broadcast (manual)"),
    ]
    for c, r in custom_commands.items():
        cmds.append(BotCommand(c, r[:30]))
    await app.bot.set_my_commands(cmds)

# ================= FETCH USERS =================
def get_users():
    try:
        r = requests.get(f"{BACKEND_URL}/retarget/users", timeout=5)
        return r.json().get("users", [])
    except:
        return []

# ================= RETARGET ALL (MANUAL ONLY) =================
async def retarget_all(update, context):
    if not is_admin(update.message.from_user.id):
        return
    context.user_data["retarget_all"] = True
    await update.message.reply_text(
        "📢 Now send message / image / video to broadcast"
    )

# ================= RETARGET ONE =================
async def retarget_user(update, context):
    if not is_admin(update.message.from_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("❌ User ID dao")
        return
    context.user_data["retarget_user"] = int(context.args[0])
    await update.message.reply_text(
        "🎯 Target set.\nNow send message / image / video"
    )

# ================= HANDLE ADMIN MEDIA =================
async def admin_media_handler(update, context):
    if not is_admin(update.message.from_user.id):
        return

    # Single user
    if "retarget_user" in context.user_data:
        uid = context.user_data.pop("retarget_user")
        await forward_any(update, context, [uid])
        await update.message.reply_text("✅ Retarget sent")
        return

    # All users
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

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("add", add_command))
app.add_handler(CommandHandler("retarget", retarget_user))
app.add_handler(CommandHandler("retarget_all", retarget_all))
app.add_handler(MessageHandler(filters.COMMAND, command_router))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, normal_message))

# 🔥 ADMIN MEDIA HANDLER
app.add_handler(
    MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.TEXT,
        admin_media_handler
    )
)

print("🤖 Bot running...")
app.run_polling()
