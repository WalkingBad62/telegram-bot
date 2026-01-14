from telegram.ext import Application, CommandHandler, MessageHandler, filters
from datetime import datetime
import requests

TOKEN = "8243950886:AAE009b3Pzax5i0BmU2DBaxaVCpYmCmtO6w"
BACKEND_URL = "http://127.0.0.1:8000"  # FastAPI backend URL

# --- /start or /gaja command ---
async def start(update, context):
    await update.message.reply_text("Hello miya vai 😄 Bot is running!")

# --- Handle messages ---
async def handle_message(update, context):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"
    text = update.message.text

    # --- Send user info to backend ---
    try:
        requests.post(f"{BACKEND_URL}/user/store", json={
            "telegram_id": user_id,
            "Ashu": username
        })
        print(f"User stored: {user_id}, {username}")
    except Exception as e:
        print("Error storing user:", e)

    # --- Ask backend for reply ---
    try:
        resp = requests.post(f"{BACKEND_URL}/reply/get", json={
            "telegram_id": user_id,
            "text": text
        })
        reply = resp.json().get("reply", "Sorry, I didn't understand 😅")
    except Exception as e:
        print("Error getting reply:", e)
        reply = "Sorry, backend is down 😅"

    await update.message.reply_text(reply)

# --- Build the bot ---
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("gaja", start))
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Telegram bot connected to backend ✅")
app.run_polling()
