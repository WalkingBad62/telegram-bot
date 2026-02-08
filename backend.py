
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime, timedelta
import sqlite3
import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
DB_NAME = os.getenv("DATABASE_URL", "bot_users.db")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN", "")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# --- Ensure tables exist ---
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                reply TEXT NOT NULL,
                active INTEGER DEFAULT 1
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                last_message_time TEXT
            )
        ''')
        conn.commit()

init_db()

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", "supersecret"))

# --- Auth Helpers ---
def is_logged_in(request: Request):
    return request.session.get("logged_in") is True

def require_login(request: Request):
    if not is_logged_in(request):
        raise HTTPException(status_code=401, detail="Not authenticated")

# --- Root endpoint for health check ---
@app.get("/")
async def root():
    return {"status": "Backend is running!"}

@app.get("/health")
def healthcheck():
    return {"status": "ok"}

# --- Store user (used by bot) ---
@app.post("/user/store")
async def store_user(request: Request):
    data = await request.json()
    telegram_id = data.get("telegram_id")
    username = data.get("username", "Unknown")
    last_message_time = data.get("last_message_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO users (telegram_id, username, last_message_time)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username=excluded.username,
                last_message_time=excluded.last_message_time
        """, (telegram_id, username, last_message_time))
        conn.commit()
    return {"ok": True}

# --- Get reply for text (used by bot_webhook) ---
@app.post("/reply/get")
async def reply_get(request: Request):
    data = await request.json()
    text = data.get("text", "").lower()

    # Check database replies first
    def normalize(t):
        return re.sub(r'[^a-z0-9 ]', '', t.strip().lower())

    user_text = normalize(text)
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT question, reply, active FROM replies")
            rows = c.fetchall()
        for row in rows:
            if row[2] and normalize(row[0]) == user_text:
                return {"reply": row[1]}
    except:
        pass

    # Fallback replies
    if "hello" in text:
        return {"reply": "Hello gaja vai 😄"}
    elif "price" in text:
        return {"reply": "Current price is 100$ 💰"}
    else:
        return {"reply": "Sorry, I didn't understand 😅"}

# --- Send message, images, and videos to multiple users ---
@app.post("/send/all/bulk")
async def send_all_bulk(
    request: Request,
    user_ids: str = Form(...),
    message: str = Form(""),
    images: List[UploadFile] = File([]),
    videos: List[UploadFile] = File([])
):
    if not TELEGRAM_BOT_TOKEN:
        return {"error": "TELEGRAM_BOT_TOKEN not set in environment"}
    # user_ids is a comma-separated string from the form
    user_id_list = [int(uid) for uid in user_ids.split(",") if uid.strip()]
    sent = []
    failed = []
    for user_id in user_id_list:
        # Send message if provided
        if message:
            try:
                resp = requests.post(f"{TELEGRAM_API_URL}/sendMessage", data={"chat_id": user_id, "text": message})
                if resp.status_code == 200:
                    sent.append(user_id)
                else:
                    failed.append({"user_id": user_id, "error": resp.text, "type": "message"})
            except Exception as e:
                failed.append({"user_id": user_id, "error": str(e), "type": "message"})
        # Send images if provided
        for image in images:
            try:
                await image.seek(0)
                file_bytes = await image.read()
                files = {"photo": (image.filename, file_bytes)}
                data = {"chat_id": user_id}
                resp = requests.post(f"{TELEGRAM_API_URL}/sendPhoto", data=data, files=files)
                if resp.status_code == 200:
                    sent.append(user_id)
                else:
                    failed.append({"user_id": user_id, "error": resp.text, "type": "image"})
            except Exception as e:
                failed.append({"user_id": user_id, "error": str(e), "type": "image"})
        # Send videos if provided
        for video in videos:
            try:
                await video.seek(0)
                file_bytes = await video.read()
                files = {"video": (video.filename, file_bytes)}
                data = {"chat_id": user_id}
                resp = requests.post(f"{TELEGRAM_API_URL}/sendVideo", data=data, files=files)
                if resp.status_code == 200:
                    sent.append(user_id)
                else:
                    failed.append({"user_id": user_id, "error": resp.text, "type": "video"})
            except Exception as e:
                failed.append({"user_id": user_id, "error": str(e), "type": "video"})
    return JSONResponse({"success": True, "sent": list(set(sent)), "failed": failed})

# --- Get all replies (public for bot) ---
@app.get("/replies")
def get_replies():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id, question, reply, active FROM replies")
        rows = c.fetchall()
    return {"replies": [
        {"id": row[0], "question": row[1], "reply": row[2], "active": bool(row[3])} for row in rows
    ]}

# Add a new reply
@app.post("/replies")
async def add_reply(request: Request):
    require_login(request)
    data = await request.json()
    question = data.get("question", "").strip()
    reply = data.get("reply", "").strip()
    if not question or not reply:
        return {"error": "Question and reply are required."}
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO replies (question, reply, active) VALUES (?, ?, 1)", (question, reply))
        conn.commit()
        rid = c.lastrowid
    return {"id": rid, "question": question, "reply": reply, "active": True}

# Edit a reply
@app.put("/replies/{reply_id}")
async def edit_reply(reply_id: int, request: Request):
    require_login(request)
    data = await request.json()
    question = data.get("question", "").strip()
    reply = data.get("reply", "").strip()
    active = int(data.get("active", 1))
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE replies SET question=?, reply=?, active=? WHERE id=?", (question, reply, active, reply_id))
        conn.commit()
    return {"id": reply_id, "question": question, "reply": reply, "active": bool(active)}

# Delete a reply
@app.delete("/replies/{reply_id}")
def delete_reply(reply_id: int, request: Request):
    require_login(request)
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM replies WHERE id=?", (reply_id,))
        conn.commit()
    return {"ok": True}

# --- Login Page (GET) ---
@app.get("/admin/login")
def login_page(request: Request):
    if is_logged_in(request):
        return RedirectResponse("/admin", status_code=302)
    return HTMLResponse("""
        <h2>Admin Login</h2>
        <form method='post' action='/admin/login'>
            <input name='username' placeholder='Username' required><br>
            <input name='password' type='password' placeholder='Password' required><br>
            <button type='submit'>Login</button>
        </form>
    """)

# --- Login Handler (POST) ---
@app.post("/admin/login")
async def login(request: Request):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        request.session["logged_in"] = True
        return RedirectResponse("/admin", status_code=302)
    return HTMLResponse("<h2>Login failed</h2><a href='/admin/login'>Try again</a>", status_code=401)

# --- Logout ---
@app.get("/admin/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=302)

# --- Send message to all or selected users ---
@app.post("/send/message/bulk")
async def send_message_bulk(request: Request):
    if not TELEGRAM_BOT_TOKEN:
        return {"error": "TELEGRAM_BOT_TOKEN not set in environment"}
    data = await request.json()
    message = data.get("message", "")
    all_users = data.get("all", False)
    user_ids = data.get("user_ids", [])
    # Ensure user_ids are integers
    user_ids = [int(uid) for uid in user_ids]
    sent = []
    failed = []
    # Get all user ids from DB if 'all' is selected
    if all_users:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT telegram_id FROM users")
            user_ids = [row[0] for row in c.fetchall()]
    for uid in user_ids:
        try:
            resp = requests.post(f"{TELEGRAM_API_URL}/sendMessage", data={"chat_id": uid, "text": message})
            if resp.status_code == 200:
                sent.append(uid)
            else:
                failed.append({"user_id": uid, "error": resp.text})
        except Exception as e:
            failed.append({"user_id": uid, "error": str(e)})
    return {"sent": sent, "failed": failed}

# --- Retarget old users ---
@app.get("/retarget/users")
def retarget_users():
    limit_time = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT telegram_id FROM users
            WHERE last_message_time < ?
        """, (limit_time,))
        users = c.fetchall()

    return {"users": [u[0] for u in users]}

# --- Get all users with last seen ---
@app.get("/users")
def get_all_users():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT telegram_id, username, last_message_time FROM users")
        users = c.fetchall()
    return {"users": [
        {"telegram_id": user[0], "username": user[1], "last_message_time": user[2]} for user in users
    ]}



# --- Send image to multiple users ---
@app.post("/send/image/bulk")
async def send_image_bulk(user_ids: str = Form(...), file: UploadFile = File(...)):
    if not TELEGRAM_BOT_TOKEN:
        return {"error": "TELEGRAM_BOT_TOKEN not set in environment"}
    try:
        # user_ids is a comma-separated string from the form
        user_id_list = [int(uid) for uid in user_ids.split(",") if uid.strip()]
        file_bytes = await file.read()
        sent = []
        failed = []
        for user_id in user_id_list:
            files = {"photo": (file.filename, file_bytes)}
            data = {"chat_id": user_id}
            resp = requests.post(f"{TELEGRAM_API_URL}/sendPhoto", data=data, files=files)
            if resp.status_code == 200:
                sent.append(user_id)
                # Send a reply message after image is sent
                reply_data = {"chat_id": user_id, "text": "Image received! Thank you."}
                try:
                    requests.post(f"{TELEGRAM_API_URL}/sendMessage", data=reply_data)
                except Exception:
                    pass  # Ignore reply errors
            else:
                failed.append({"user_id": user_id, "error": resp.text})
        return {"sent": sent, "failed": failed}
    except Exception as e:
        return {"error": str(e)}



# --- Send video to multiple users ---
@app.post("/send/video/bulk")
async def send_video_bulk(user_ids: str = Form(...), file: UploadFile = File(...)):
    if not TELEGRAM_BOT_TOKEN:
        return {"error": "TELEGRAM_BOT_TOKEN not set in environment"}
    try:
        user_id_list = [int(uid) for uid in user_ids.split(",") if uid.strip()]
        file_bytes = await file.read()
        sent = []
        failed = []
        for user_id in user_id_list:
            files = {"video": (file.filename, file_bytes)}
            data = {"chat_id": user_id}
            resp = requests.post(f"{TELEGRAM_API_URL}/sendVideo", data=data, files=files)
            if resp.status_code == 200:
                sent.append(user_id)
            else:
                failed.append({"user_id": user_id, "error": resp.text})
        return {"sent": sent, "failed": failed}
    except Exception as e:
        return {"error": str(e)}
# --- Send text message to user ---
@app.post("/send/message")
async def send_message(user_id: int = Form(...), message: str = Form(...)):
    if not TELEGRAM_BOT_TOKEN:
        return {"error": "TELEGRAM_BOT_TOKEN not set in environment"}
    try:
        data = {"chat_id": user_id, "text": message}
        resp = requests.post(f"{TELEGRAM_API_URL}/sendMessage", data=data)
        if resp.status_code == 200:
            return {"status": "sent", "user_id": user_id, "message": message}
        else:
            return {"error": resp.text}
    except Exception as e:
        return {"error": str(e)}

# --- Serve Admin Panel (Protected) ---
@app.get("/admin")
def get_admin_panel(request: Request):
    require_login(request)
    return templates.TemplateResponse("admin_panel.html", {"request": request})


# local host web
# $env:TELEGRAM_BOT_TOKEN=" Bot Tocken"
# To run the backend server, use:
# python -m uvicorn backend:app --host 0.0.0.0 --port 8000
# To on the admin panel
# http://localhost:8000/admin/login
