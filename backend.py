from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import sqlite3

app = FastAPI()

# --- DB setup ---
with sqlite3.connect("bot_users.db") as conn:
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            last_message_time TEXT
        )
    """)
    conn.commit()
print("Backend DB ready ✅")

# --- Pydantic models ---
class User(BaseModel):
    telegram_id: int
    username: str

class Message(BaseModel):
    telegram_id: int
    text: str

# --- Store user endpoint ---
@app.post("/user/store")
def store_user(user: User):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect("bot_users.db") as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO users (telegram_id, username, last_message_time)
            VALUES (?, ?, ?)
        """, (user.telegram_id, user.username, now))
        conn.commit()
    return {"status": "success", "message": f"User {user.username} stored"}

# --- Get reply endpoint ---
@app.post("/reply/get")
def get_reply(message: Message):
    text = message.text.lower()
    
    if "price" in text:
        reply = "Current price is 100$"
    elif "hello" in text:
        reply = "Hello miya vai 😄"
    else:
        reply = "Sorry, I didn't understand 😅"
    
    return {"reply": reply}
