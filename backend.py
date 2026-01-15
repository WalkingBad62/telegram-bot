from fastapi import FastAPI
from datetime import datetime, timedelta
import sqlite3
import os

app = FastAPI()

# For Render deployment - use environment variable or default
DB_NAME = os.getenv("DATABASE_URL", "bot_users.db")

# --- DB Init ---
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            last_message_time TEXT
        )
        """)
        conn.commit()

init_db()
print("Backend DB ready ✅")

# --- Store user ---
@app.post("/user/store")
def store_user(data: dict):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO users
                (telegram_id, username, last_message_time)
                VALUES (?, ?, ?)
            """, (
                data["telegram_id"],
                data["username"],
                data["last_message_time"]
            ))
            conn.commit()
        return {"status": "stored"}
    except Exception as e:
        return {"error": str(e)}

# --- Get reply ---
@app.post("/reply/get")
def get_reply(data: dict):
    text = data.get("text", "").lower()

    if "hello" in text:
        return {"reply": "Hello miya vai 😄"}
    elif "price" in text:
        return {"reply": "Current price is 100$ 💰"}
    else:
        return {"reply": "Sorry, I didn't understand 😅"}

# --- Retarget old users ---
@app.get("/retarget/users")
def retarget_users():
    limit_time = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT telegram_id FROM users
            WHERE last_message_time < ?
        """, (limit_time,))
        users = c.fetchall()

    return {"users": [u[0] for u in users]}

# --- Get all users ---
@app.get("/users")
def get_all_users():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT telegram_id, username FROM users")
        users = c.fetchall()

    return {"users": [{"telegram_id": user[0], "username": user[1]} for user in users]}
