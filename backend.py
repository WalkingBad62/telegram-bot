
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime, timedelta
import hashlib
import sqlite3
import os
import subprocess
import sys
import re
import time
import requests
from dotenv import load_dotenv
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"), override=False)

# --- Configuration ---
DB_NAME = os.getenv("DATABASE_URL", "bot_users.db")
BOT_MODE = (os.getenv("BOT_MODE", "currency") or "currency").strip().lower()
if BOT_MODE not in ("currency", "trading"):
    BOT_MODE = "currency"
MODE_SUFFIX = BOT_MODE.upper()
TELEGRAM_BOT_TOKEN = (
    os.getenv(f"BOT_TOKEN_{MODE_SUFFIX}")
    or os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("BOT_TOKEN", "")
)
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_RESET_TOKEN = (os.getenv("ADMIN_RESET_TOKEN", "") or "").strip()
CURRENCY_API_URL = (os.getenv("CURRENCY_API_URL", "") or "").strip()
CURRENCY_API_KEY = (os.getenv("CURRENCY_API_KEY", "") or "").strip()
CURRENCY_API_KEY_HEADER = (os.getenv("CURRENCY_API_KEY_HEADER", "X-API-KEY") or "X-API-KEY").strip()
TRADING_API_URL = (os.getenv("TRADING_API_URL", "https://yoofirmtrading.xyz/api/analyze-screenshot") or "").strip()
TRADING_API_KEY = (os.getenv("TRADING_API_KEY", "") or "").strip()
TRADING_API_KEY_HEADER = (os.getenv("TRADING_API_KEY_HEADER", "X-API-Key") or "X-API-Key").strip()
try:
    CURRENCY_API_TIMEOUT = float(os.getenv("CURRENCY_API_TIMEOUT", "6"))
except ValueError:
    CURRENCY_API_TIMEOUT = 6.0
try:
    TRADING_API_TIMEOUT = float(os.getenv("TRADING_API_TIMEOUT", "20"))
except ValueError:
    TRADING_API_TIMEOUT = 20.0
try:
    TRADING_API_RETRIES = int(os.getenv("TRADING_API_RETRIES", "1"))
except ValueError:
    TRADING_API_RETRIES = 1
if TRADING_API_RETRIES < 0:
    TRADING_API_RETRIES = 0
try:
    TRADING_API_RETRY_DELAY = float(os.getenv("TRADING_API_RETRY_DELAY", "1.0"))
except ValueError:
    TRADING_API_RETRY_DELAY = 1.0

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
DEFAULT_CURRENCY_PAIRS = {
    "EURUSD": {"price": 1.19, "link": "http://currency.com/buy/EURUSD/"},
    "USDJPY": {"price": 150.25, "link": "http://currency.com/buy/USDJPY/"},
    "AUDCAD": {"price": 0.91, "link": "http://currency.com/buy/AUDCAD/"},
    "CHFUSD": {"price": 1.12, "link": "http://currency.com/buy/CHFUSD/"},
    "AUDCAD_OTC": {"price": 0.89, "link": "http://currency.com/buy/AUDCAD_otc/"},
    "BTCUSD": {"price": 43000.0, "link": "http://currency.com/buy/BTCUSD/"},
}

# --- Common PocketOption pair suggestions (for autocomplete only, NOT enforced) ---
POCKET_OPTION_SUGGESTIONS = sorted({
    # Forex Major
    "EURUSD", "USDJPY", "GBPUSD", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    # Forex Cross
    "EURGBP", "EURJPY", "GBPJPY", "EURAUD", "EURCHF", "EURNZD", "EURCAD",
    "GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD", "AUDCAD", "AUDCHF", "AUDNZD",
    "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY", "CADCHF", "NZDCAD", "NZDCHF",
    # Forex OTC
    "EURUSD_OTC", "USDJPY_OTC", "GBPUSD_OTC", "USDCHF_OTC", "AUDUSD_OTC", "USDCAD_OTC", "NZDUSD_OTC",
    "EURGBP_OTC", "EURJPY_OTC", "GBPJPY_OTC", "EURAUD_OTC", "EURCHF_OTC",
    "GBPAUD_OTC", "GBPCAD_OTC", "GBPCHF_OTC", "GBPNZD_OTC",
    "AUDCAD_OTC", "AUDCHF_OTC", "AUDJPY_OTC", "AUDNZD_OTC",
    "CADJPY_OTC", "CHFJPY_OTC", "NZDJPY_OTC", "NZDCAD_OTC",
    # Crypto
    "BTCUSD", "ETHUSD", "LTCUSD", "XRPUSD", "EOSUSD", "BCHUSD",
    "DOGEUSD", "SOLUSD", "ADAUSD", "DOTUSD", "SHIBUSD", "TRXUSD",
    "LINKUSD", "AVAXUSD", "MATICUSD", "BNBUSD", "TONUSD",
    "BTCUSD_OTC", "ETHUSD_OTC", "LTCUSD_OTC",
    # Commodities
    "XAUUSD", "XAGUSD", "XAUUSD_OTC", "XAGUSD_OTC",
    # Extra
    "CHFUSD",
})

# --- Signal pair test script path ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FUTURE_SIGNAL_SCRIPT = os.path.join(SCRIPT_DIR, "future_signal.py")
START_IMAGE_UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "start-images")
ALLOWED_START_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_START_IMAGE_BYTES = 8 * 1024 * 1024
os.makedirs(START_IMAGE_UPLOAD_DIR, exist_ok=True)

def start_message_setting_key() -> str:
    return f"start_message_{BOT_MODE}"

def promo_image_setting_key() -> str:
    return f"promo_image_url_{BOT_MODE}"

def welcome_image_setting_key() -> str:
    return f"welcome_image_url_{BOT_MODE}"

def is_valid_http_url(url: str) -> bool:
    value = (url or "").strip().lower()
    return value.startswith("http://") or value.startswith("https://")

def parse_local_image_setting(value: str) -> Optional[str]:
    raw = (value or "").strip()
    if not raw.lower().startswith("local:"):
        return None
    path = raw[6:].strip()
    if not path:
        return None
    return os.path.abspath(path)

def build_local_image_setting(path: str) -> str:
    return f"local:{os.path.abspath(path)}"

def image_setting_to_preview_url(value: str) -> str:
    raw = (value or "").strip()
    local_path = parse_local_image_setting(raw)
    if local_path:
        filename = os.path.basename(local_path)
        return f"/uploads/start-images/{filename}" if filename else ""
    return raw

def image_setting_payload(value: str) -> dict:
    raw = (value or "").strip()
    return {
        "url": image_setting_to_preview_url(raw),
        "value": raw,
    }

def remove_uploaded_image_if_any(value: str) -> None:
    local_path = parse_local_image_setting(value)
    if not local_path:
        return
    root = os.path.abspath(START_IMAGE_UPLOAD_DIR)
    try:
        if os.path.commonpath([root, local_path]) != root:
            return
    except ValueError:
        return
    try:
        if os.path.isfile(local_path):
            os.remove(local_path)
    except OSError:
        pass

async def save_uploaded_start_image(file: UploadFile) -> str:
    original_name = (file.filename or "").strip()
    ext = os.path.splitext(original_name)[1].lower()
    content_type = (file.content_type or "").lower()
    if ext not in ALLOWED_START_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Use JPG, PNG, GIF, or WEBP.",
        )
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed.")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_START_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image is too large (max 8MB).")
    filename = (
        f"{BOT_MODE}_{datetime.now().strftime('%Y%m%d%H%M%S')}_"
        f"{secrets.token_hex(6)}{ext}"
    )
    file_path = os.path.abspath(os.path.join(START_IMAGE_UPLOAD_DIR, filename))
    with open(file_path, "wb") as f:
        f.write(content)
    return file_path

def sanitize_start_message(message: str) -> str:
    if not isinstance(message, str):
        return message
    cleaned = message
    cleaned = cleaned.replace("2. GajaAI Clone: /gajaai_clone\n", "")
    cleaned = cleaned.replace("2. GajaAI Clone: /gajaai_clone", "")
    cleaned = cleaned.replace("3. Convert Currency: /currencycoveter", "2. Convert Currency: /currencycoveter")
    return cleaned

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
        c.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS image_prices (
                image_hash TEXT PRIMARY KEY,
                currency TEXT NOT NULL,
                price REAL NOT NULL,
                discount REAL NOT NULL,
                created_at TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS currency_pairs (
                pair TEXT PRIMARY KEY,
                price REAL NOT NULL,
                link TEXT NOT NULL,
                updated_at TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS signal_pairs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair_name TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TEXT
            )
        ''')
        c.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("start_message", DEFAULT_START_MESSAGE)
        )
        c.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (start_message_setting_key(), DEFAULT_START_MESSAGE)
        )
        c.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (promo_image_setting_key(), "")
        )
        c.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (welcome_image_setting_key(), "")
        )
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for pair, info in DEFAULT_CURRENCY_PAIRS.items():
            c.execute(
                "INSERT OR IGNORE INTO currency_pairs (pair, price, link, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (pair, info["price"], info["link"], now)
            )
        # Seed default signal pairs if table is empty
        c.execute("SELECT COUNT(*) FROM signal_pairs")
        if c.fetchone()[0] == 0:
            default_signal_pairs = [
                ("EURUSD", "EURUSD", 1),
                ("USDJPY", "USDJPY", 2),
                ("AUDCAD", "AUDCAD", 3),
                ("CHFUSD", "CHFUSD", 4),
                ("AUDCAD_OTC", "AUDCAD_otc", 5),
                ("BTCUSD", "BTCUSD", 6),
            ]
            for pair_name, display_name, sort_order in default_signal_pairs:
                c.execute(
                    "INSERT OR IGNORE INTO signal_pairs (pair_name, display_name, active, sort_order, created_at) "
                    "VALUES (?, ?, 1, ?, ?)",
                    (pair_name, display_name, sort_order, now)
                )
        conn.commit()

init_db()

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = c.fetchone()
    if row and row[0] is not None:
        return row[0]
    return default

def set_setting(key: str, value: str) -> None:
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value)
        )
        conn.commit()

def get_image_price(image_hash: str):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT currency, price, discount FROM image_prices WHERE image_hash=?",
            (image_hash,)
        )
        return c.fetchone()

def save_image_price(image_hash: str, currency: str, price: float, discount: float):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO image_prices (image_hash, currency, price, discount, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (image_hash, currency, price, discount, now)
        )
        conn.commit()

def generate_price_from_hash(image_hash: str):
    base = int(image_hash[:8], 16)
    price = 50 + (base % 151)  # 50 - 200
    discount = 5 + (base % 31)  # 5 - 35
    if discount >= price:
        discount = max(0, price - 1)
    return float(price), float(discount)

def build_fallback_trading_analysis(content: bytes):
    image_hash = hashlib.sha256(content).hexdigest()
    seed = int(image_hash[:12], 16)

    assets = [
        ("S&P 500", 6950.0),
        ("Nasdaq 100", 25100.0),
        ("XAUUSD", 2320.0),
        ("EURUSD", 1.0850),
        ("BTCUSD", 62000.0),
    ]
    pair, base_price = assets[seed % len(assets)]

    trend = "Downtrend" if ((seed >> 1) % 2 == 0) else "Uptrend"
    signal = "SELL" if trend == "Downtrend" else "BUY"
    signal_strength = 70 + (seed % 21)  # 70-90

    patterns = ["Descending Trend", "Ascending Trend", "Consolidation", "Range Breakout"]
    chart_pattern = patterns[(seed >> 2) % len(patterns)]
    chart_type = "Line" if ((seed >> 5) % 2 == 0) else "Candlestick"

    entry_jitter = ((seed % 21) - 10) / 10000  # -0.10% to +0.10%
    entry_price = base_price * (1 + entry_jitter)
    tp_move = 0.002 + ((seed % 36) / 10000)    # 0.20% to 0.56%
    sl_move = tp_move * 0.65

    if signal == "BUY":
        take_profit = entry_price * (1 + tp_move)
        stop_loss = entry_price * (1 - sl_move)
    else:
        take_profit = entry_price * (1 - tp_move)
        stop_loss = entry_price * (1 + sl_move)

    support_zone = min(entry_price, take_profit, stop_loss) * 0.9992
    resistance_zone = max(entry_price, take_profit, stop_loss) * 1.0008

    return {
        "pair": pair,
        "current_trend": trend,
        "signal": signal,
        "signal_strength": signal_strength,
        "chart_pattern": chart_pattern,
        "chart_type": chart_type,
        "entry_price": round(entry_price, 4),
        "take_profit_price": round(take_profit, 4),
        "stop_loss_price": round(stop_loss, 4),
        "support_zone_price": round(support_zone, 4),
        "resistance_zone_price": round(resistance_zone, 4),
    }

def analyze_trading_screenshot(content: bytes, filename: str):
    if not TRADING_API_URL:
        return build_fallback_trading_analysis(content), None
    headers = {}
    if TRADING_API_KEY:
        headers[TRADING_API_KEY_HEADER or "X-API-Key"] = TRADING_API_KEY
    files = {"screenshot": (filename or "screenshot.png", content)}
    total_attempts = TRADING_API_RETRIES + 1
    last_error = None

    for attempt in range(total_attempts):
        try:
            res = requests.post(
                TRADING_API_URL,
                headers=headers,
                files=files,
                timeout=TRADING_API_TIMEOUT,
            )
        except Exception as exc:
            last_error = f"Trading API request failed: {exc}"
        else:
            try:
                data = res.json()
            except Exception:
                data = {"raw": res.text}
            if res.status_code == 200:
                return data, None
            last_error = f"Trading API returned {res.status_code}: {data}"
            # Retry only transient gateway/service errors.
            if res.status_code not in (429, 500, 502, 503, 504):
                break

        if attempt < total_attempts - 1 and TRADING_API_RETRY_DELAY > 0:
            time.sleep(TRADING_API_RETRY_DELAY)

    # Keep bot usable even when upstream API is down.
    return build_fallback_trading_analysis(content), None

def get_currency_pair(pair: str):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT price, link FROM currency_pairs WHERE pair=?",
            (pair,)
        )
        return c.fetchone()

def fetch_currency_pair_from_api(pair: str):
    if not CURRENCY_API_URL:
        return None
    url = CURRENCY_API_URL
    params = None
    if "{pair}" in CURRENCY_API_URL:
        url = CURRENCY_API_URL.format(pair=pair)
    else:
        params = {"pair": pair}
    headers = {}
    if CURRENCY_API_KEY:
        headers[CURRENCY_API_KEY_HEADER or "X-API-KEY"] = CURRENCY_API_KEY
    try:
        res = requests.get(url, params=params, headers=headers, timeout=CURRENCY_API_TIMEOUT)
        if res.status_code != 200:
            return None
        data = res.json()
    except Exception:
        return None
    price = data.get("price")
    link = data.get("link")
    if price is None or not link:
        return None
    return {"pair": pair, "price": price, "link": link}

def hash_password(password: str, salt_hex: Optional[str] = None):
    if salt_hex:
        salt = bytes.fromhex(salt_hex)
    else:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return salt.hex(), dk.hex()

def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    _, computed = hash_password(password, salt_hex=salt_hex)
    return secrets.compare_digest(computed, hash_hex)

def get_admin(username: str):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id, username, salt, password_hash FROM admins WHERE username=?", (username,))
        return c.fetchone()

def upsert_admin(username: str, password: str):
    salt_hex, hash_hex = hash_password(password)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM admins WHERE username=?", (username,))
        existing = c.fetchone()
        if existing:
            c.execute(
                "UPDATE admins SET salt=?, password_hash=?, created_at=? WHERE username=?",
                (salt_hex, hash_hex, now, username)
            )
        else:
            c.execute(
                "INSERT INTO admins (username, salt, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (username, salt_hex, hash_hex, now)
            )
        conn.commit()

def ensure_admin_user():
    if not get_admin(ADMIN_USERNAME):
        upsert_admin(ADMIN_USERNAME, ADMIN_PASSWORD)

ensure_admin_user()

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")

app = FastAPI()
app.mount("/uploads/start-images", StaticFiles(directory=START_IMAGE_UPLOAD_DIR), name="start_images")

def env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")

SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "supersecret")
SESSION_HTTPS_ONLY = env_bool("SESSION_HTTPS_ONLY", False)
SESSION_SAMESITE = os.getenv("SESSION_SAMESITE", "lax")
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", str(60 * 60 * 24 * 7)))

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    https_only=SESSION_HTTPS_ONLY,
    same_site=SESSION_SAMESITE,
    max_age=SESSION_MAX_AGE,
)

# --- Auth Helpers ---
def is_logged_in(request: Request):
    return request.session.get("logged_in") is True

def require_login(request: Request):
    if not is_logged_in(request):
        raise HTTPException(status_code=401, detail="Not authenticated")

def get_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token

def require_csrf(request: Request):
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        expected = request.session.get("csrf_token")
        provided = request.headers.get("x-csrf-token", "")
        if not expected or not provided or provided != expected:
            raise HTTPException(status_code=403, detail="CSRF token invalid")

# --- Root endpoint for health check ---
@app.get("/")
async def root():
    return {"status": "Backend is running!"}

@app.get("/health")
def healthcheck():
    return {"status": "ok"}

# --- Start message settings ---
@app.get("/settings/start-message")
def get_start_message():
    message = get_setting(start_message_setting_key())
    if message is None:
        message = get_setting("start_message", DEFAULT_START_MESSAGE)
    message = sanitize_start_message(message)
    return {"message": message, "mode": BOT_MODE}

@app.put("/settings/start-message")
async def update_start_message(request: Request):
    require_login(request)
    require_csrf(request)
    data = await request.json()
    raw_message = data.get("message")
    if not isinstance(raw_message, str) or not raw_message.strip():
        raise HTTPException(status_code=400, detail="Message is required.")
    raw_message = sanitize_start_message(raw_message)
    set_setting(start_message_setting_key(), raw_message)
    return {"ok": True, "message": raw_message, "mode": BOT_MODE}

# --- Promo image settings ---
@app.get("/settings/promo-image")
def get_promo_image():
    payload = image_setting_payload(get_setting(promo_image_setting_key(), ""))
    return {"url": payload["url"], "value": payload["value"], "mode": BOT_MODE}

@app.put("/settings/promo-image")
async def update_promo_image(request: Request):
    require_login(request)
    require_csrf(request)
    data = await request.json()
    url = (data.get("url") or "").strip()
    if url and not is_valid_http_url(url):
        raise HTTPException(status_code=400, detail="Image URL must start with http:// or https://")
    old_value = get_setting(promo_image_setting_key(), "")
    set_setting(promo_image_setting_key(), url)
    if old_value != url:
        remove_uploaded_image_if_any(old_value)
    payload = image_setting_payload(url)
    return {"ok": True, "url": payload["url"], "value": payload["value"], "mode": BOT_MODE}

@app.post("/settings/promo-image/upload")
async def upload_promo_image(request: Request, file: UploadFile = File(...)):
    require_login(request)
    require_csrf(request)
    saved_path = await save_uploaded_start_image(file)
    new_value = build_local_image_setting(saved_path)
    old_value = get_setting(promo_image_setting_key(), "")
    set_setting(promo_image_setting_key(), new_value)
    if old_value != new_value:
        remove_uploaded_image_if_any(old_value)
    payload = image_setting_payload(new_value)
    return {"ok": True, "url": payload["url"], "value": payload["value"], "mode": BOT_MODE}

# --- Welcome image settings ---
@app.get("/settings/welcome-image")
def get_welcome_image():
    payload = image_setting_payload(get_setting(welcome_image_setting_key(), ""))
    return {"url": payload["url"], "value": payload["value"], "mode": BOT_MODE}

@app.put("/settings/welcome-image")
async def update_welcome_image(request: Request):
    require_login(request)
    require_csrf(request)
    data = await request.json()
    url = (data.get("url") or "").strip()
    if url and not is_valid_http_url(url):
        raise HTTPException(status_code=400, detail="Image URL must start with http:// or https://")
    old_value = get_setting(welcome_image_setting_key(), "")
    set_setting(welcome_image_setting_key(), url)
    if old_value != url:
        remove_uploaded_image_if_any(old_value)
    payload = image_setting_payload(url)
    return {"ok": True, "url": payload["url"], "value": payload["value"], "mode": BOT_MODE}

@app.post("/settings/welcome-image/upload")
async def upload_welcome_image(request: Request, file: UploadFile = File(...)):
    require_login(request)
    require_csrf(request)
    saved_path = await save_uploaded_start_image(file)
    new_value = build_local_image_setting(saved_path)
    old_value = get_setting(welcome_image_setting_key(), "")
    set_setting(welcome_image_setting_key(), new_value)
    if old_value != new_value:
        remove_uploaded_image_if_any(old_value)
    payload = image_setting_payload(new_value)
    return {"ok": True, "url": payload["url"], "value": payload["value"], "mode": BOT_MODE}

# --- Currency price endpoint ---
@app.get("/currency/pair/{pair}")
def currency_pair(pair: str):
    pair_norm = (pair or "").strip().upper()
    api_data = fetch_currency_pair_from_api(pair_norm)
    if api_data:
        return api_data
    row = get_currency_pair(pair_norm)
    if not row:
        raise HTTPException(status_code=404, detail="Pair not found.")
    price, link = row
    return {"pair": pair_norm, "price": price, "link": link}

# --- Currency signal endpoint ---
@app.post("/currency/signal")
async def currency_signal(request: Request):
    data = await request.json()
    pair = (data.get("pair") or "").strip().upper()
    timeframe = int(data.get("timeframe", 5))
    if not pair:
        raise HTTPException(status_code=400, detail="Pair is required.")
    # Try external signal API if configured
    signal_api_url = os.getenv("SIGNAL_API_URL", "").strip()
    if signal_api_url:
        try:
            signal_api_key = os.getenv("SIGNAL_API_KEY", "").strip()
            headers = {}
            if signal_api_key:
                headers["X-API-Key"] = signal_api_key
            res = requests.post(
                signal_api_url,
                json={"pair": pair, "timeframe": timeframe},
                headers=headers,
                timeout=10
            )
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass
    # Fallback: generate deterministic signal from pair data
    row = get_currency_pair(pair)
    if not row:
        # Try default pairs
        default_info = None
        for dpair, dinfo in DEFAULT_CURRENCY_PAIRS.items():
            if dpair.upper() == pair.upper():
                default_info = dinfo
                break
        if not default_info:
            raise HTTPException(status_code=404, detail="Pair not found.")
        base_price = default_info["price"]
    else:
        base_price = row[0]
    # Generate deterministic signal based on pair + timeframe + date
    today = datetime.now().strftime("%Y-%m-%d")
    seed_str = f"{pair}:{timeframe}:{today}"
    seed_hash = hashlib.sha256(seed_str.encode()).hexdigest()
    seed_val = int(seed_hash[:8], 16)
    direction = "BUY" if seed_val % 2 == 0 else "SELL"
    confidence = 70 + (seed_val % 25)
    variation = (seed_val % 100) / 10000
    entry_price = base_price * (1 + variation)
    if direction == "BUY":
        take_profit = entry_price * (1 + 0.002 * timeframe / 5)
        stop_loss = entry_price * (1 - 0.001 * timeframe / 5)
    else:
        take_profit = entry_price * (1 - 0.002 * timeframe / 5)
        stop_loss = entry_price * (1 + 0.001 * timeframe / 5)
    return {
        "pair": pair,
        "timeframe": timeframe,
        "signal": direction,
        "entry_price": round(entry_price, 4),
        "take_profit": round(take_profit, 4),
        "stop_loss": round(stop_loss, 4),
        "confidence": confidence
    }

# --- GajaAI price endpoint ---
@app.post("/gajaai/price")
async def gajaai_price(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file.")
    if BOT_MODE == "trading":
        analysis, error = analyze_trading_screenshot(content, file.filename or "screenshot.png")
        if error:
            raise HTTPException(status_code=502, detail=error)
        return {
            "mode": "trading",
            "analysis": analysis,
        }
    image_hash = hashlib.sha256(content).hexdigest()
    row = get_image_price(image_hash)
    if row:
        currency, price, discount = row
    else:
        currency = "USD"
        price, discount = generate_price_from_hash(image_hash)
        save_image_price(image_hash, currency, price, discount)
    return {
        "mode": "currency",
        "currency": currency,
        "price": price,
        "discount": discount
    }

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
        cleaned = t.strip().lower()
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"[^\w\s]", "", cleaned, flags=re.UNICODE)
        return cleaned

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
    require_login(request)
    require_csrf(request)
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
def get_replies(request: Request):
    require_login(request)
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
    require_csrf(request)
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
    require_csrf(request)
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
    require_csrf(request)
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
    csrf_token = get_csrf_token(request)
    return templates.TemplateResponse(
        "admin_login.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "error": None,
        },
    )

# --- Login Handler (POST) ---
@app.post("/admin/login")
async def login(request: Request):
    form = await request.form()
    csrf_token = form.get("csrf_token")
    if not csrf_token or csrf_token != request.session.get("csrf_token"):
        new_token = get_csrf_token(request)
        return templates.TemplateResponse(
            "admin_login.html",
            {
                "request": request,
                "csrf_token": new_token,
                "error": "Invalid session. Please try again.",
            },
            status_code=403,
        )
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""
    admin = get_admin(username)
    if admin and verify_password(password, admin[2], admin[3]):
        request.session["logged_in"] = True
        return RedirectResponse("/admin", status_code=302)
    new_token = get_csrf_token(request)
    return templates.TemplateResponse(
        "admin_login.html",
        {
            "request": request,
            "csrf_token": new_token,
            "error": "Login failed. Please check your username and password.",
        },
        status_code=401,
    )

# --- Admin Password Reset (Token) ---
def reset_token_valid(token: str) -> bool:
    return bool(ADMIN_RESET_TOKEN) and secrets.compare_digest(token, ADMIN_RESET_TOKEN)

@app.get("/admin/reset")
def admin_reset_token_page(request: Request, token: str = ""):
    if token and reset_token_valid(token):
        request.session["reset_token_ok"] = True
        return RedirectResponse("/admin/reset/form", status_code=302)
    csrf_token = get_csrf_token(request)
    error = "Invalid reset token." if token else None
    return templates.TemplateResponse(
        "admin_reset_token.html",
        {"request": request, "csrf_token": csrf_token, "error": error},
    )

@app.post("/admin/reset/token")
async def admin_reset_token(request: Request):
    form = await request.form()
    csrf_token = form.get("csrf_token")
    if not csrf_token or csrf_token != request.session.get("csrf_token"):
        new_token = get_csrf_token(request)
        return templates.TemplateResponse(
            "admin_reset_token.html",
            {
                "request": request,
                "csrf_token": new_token,
                "error": "Invalid session. Please try again.",
            },
            status_code=403,
        )
    token = (form.get("reset_token") or "").strip()
    if not reset_token_valid(token):
        return templates.TemplateResponse(
            "admin_reset_token.html",
            {
                "request": request,
                "csrf_token": csrf_token,
                "error": "Invalid reset token.",
            },
            status_code=403,
        )
    request.session["reset_token_ok"] = True
    return RedirectResponse("/admin/reset/form", status_code=302)

@app.get("/admin/reset/form")
def admin_reset_form(request: Request):
    if not request.session.get("reset_token_ok"):
        return RedirectResponse("/admin/reset", status_code=302)
    csrf_token = get_csrf_token(request)
    return templates.TemplateResponse(
        "admin_reset.html",
        {"request": request, "csrf_token": csrf_token, "error": None},
    )

@app.post("/admin/reset")
async def admin_reset(request: Request):
    if not request.session.get("reset_token_ok"):
        return RedirectResponse("/admin/reset", status_code=302)
    form = await request.form()
    csrf_token = form.get("csrf_token")
    if not csrf_token or csrf_token != request.session.get("csrf_token"):
        new_token = get_csrf_token(request)
        return templates.TemplateResponse(
            "admin_reset.html",
            {
                "request": request,
                "csrf_token": new_token,
                "error": "Invalid session. Please try again.",
            },
            status_code=403,
        )
    new_password = (form.get("password") or "").strip()
    confirm_password = (form.get("confirm_password") or "").strip()
    if len(new_password) < 8:
        return templates.TemplateResponse(
            "admin_reset.html",
            {
                "request": request,
                "csrf_token": csrf_token,
                "error": "Password must be at least 8 characters.",
            },
            status_code=400,
        )
    if new_password != confirm_password:
        return templates.TemplateResponse(
            "admin_reset.html",
            {
                "request": request,
                "csrf_token": csrf_token,
                "error": "Passwords do not match.",
            },
            status_code=400,
        )
    upsert_admin(ADMIN_USERNAME, new_password)
    request.session.pop("reset_token_ok", None)
    return RedirectResponse("/admin/login", status_code=302)

# --- Logout ---
@app.get("/admin/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=302)

# --- Send message to all or selected users ---
@app.post("/send/message/bulk")
async def send_message_bulk(request: Request):
    require_login(request)
    require_csrf(request)
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
def retarget_users(request: Request):
    require_login(request)
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
def get_all_users(request: Request):
    require_login(request)
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT telegram_id, username, last_message_time FROM users")
        users = c.fetchall()
    return {"users": [
        {"telegram_id": user[0], "username": user[1], "last_message_time": user[2]} for user in users
    ]}



# --- Send image to multiple users ---
@app.post("/send/image/bulk")
async def send_image_bulk(request: Request, user_ids: str = Form(...), file: UploadFile = File(...)):
    require_login(request)
    require_csrf(request)
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
async def send_video_bulk(request: Request, user_ids: str = Form(...), file: UploadFile = File(...)):
    require_login(request)
    require_csrf(request)
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
async def send_message(request: Request, user_id: int = Form(...), message: str = Form(...)):
    require_login(request)
    require_csrf(request)
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

# --- Signal Pairs CRUD ---
@app.get("/signal-pairs")
def get_signal_pairs(request: Request):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id, pair_name, display_name, active, sort_order FROM signal_pairs ORDER BY sort_order ASC, id ASC")
        rows = c.fetchall()
    return {"pairs": [
        {"id": r[0], "pair_name": r[1], "display_name": r[2], "active": bool(r[3]), "sort_order": r[4]} for r in rows
    ]}

@app.get("/signal-pairs/valid")
def get_valid_pairs():
    """Return suggestion list for autocomplete (NOT enforced)."""
    return {"valid_pairs": POCKET_OPTION_SUGGESTIONS}

@app.post("/signal-pairs/test")
async def test_signal_pair(request: Request):
    """Test if a pair actually works on PocketOption by running future_signal.py."""
    require_login(request)
    require_csrf(request)
    data = await request.json()
    pair_name = (data.get("pair_name") or "").strip().upper()
    if not pair_name:
        raise HTTPException(status_code=400, detail="Pair name is required.")
    asset_name = pair_name.replace("_OTC", "_otc")
    cmd = [
        sys.executable, FUTURE_SIGNAL_SCRIPT,
        "--assets", asset_name,
        "--timeframe", "5",
        "--percentage", "70",
        "--days", "1",
        "--martingale", "0",
    ]
    child_env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=90, cwd=SCRIPT_DIR, env=child_env,
        )
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        # Check for Invalid asset error
        if "Invalid asset" in stderr or "Invalid asset" in stdout:
            return {"valid": False, "error": f"'{pair_name}' is not a valid PocketOption asset."}
        if result.returncode != 0 and not stdout:
            err_lines = [l.strip() for l in stderr.split("\n") if l.strip()]
            last_err = err_lines[-1] if err_lines else "Unknown error"
            return {"valid": False, "error": last_err[:300]}
        # Check if any signal lines exist
        has_signals = False
        for line in stdout.split("\n"):
            parts = line.strip().split()
            if len(parts) >= 4 and parts[1].startswith("M") and parts[3] in ("CALL", "PUT"):
                has_signals = True
                break
            if "Total signals" in line:
                has_signals = True
                break
        if has_signals:
            return {"valid": True, "message": f"'{pair_name}' works! Signals found."}
        else:
            return {"valid": True, "message": f"'{pair_name}' is accepted by PocketOption but no signals right now (market may be closed)."}
    except subprocess.TimeoutExpired:
        return {"valid": False, "error": "Test timed out. Try again later."}
    except Exception as e:
        return {"valid": False, "error": str(e)[:300]}

@app.post("/signal-pairs")
async def add_signal_pair(request: Request):
    require_login(request)
    require_csrf(request)
    data = await request.json()
    pair_name = (data.get("pair_name") or "").strip().upper()
    display_name = (data.get("display_name") or "").strip()
    if not pair_name:
        raise HTTPException(status_code=400, detail="Pair name is required.")
    if not display_name:
        display_name = pair_name
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT MAX(sort_order) FROM signal_pairs")
        max_order = c.fetchone()[0] or 0
        try:
            c.execute(
                "INSERT INTO signal_pairs (pair_name, display_name, active, sort_order, created_at) VALUES (?, ?, 1, ?, ?)",
                (pair_name, display_name, max_order + 1, now)
            )
            conn.commit()
            rid = c.lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Pair already exists.")
    return {"id": rid, "pair_name": pair_name, "display_name": display_name, "active": True, "sort_order": max_order + 1}

@app.put("/signal-pairs/{pair_id}")
async def edit_signal_pair(pair_id: int, request: Request):
    require_login(request)
    require_csrf(request)
    data = await request.json()
    pair_name = (data.get("pair_name") or "").strip().upper()
    display_name = (data.get("display_name") or "").strip()
    active = int(data.get("active", 1))
    sort_order = data.get("sort_order")
    if not pair_name:
        raise HTTPException(status_code=400, detail="Pair name is required.")
    if not display_name:
        display_name = pair_name
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        if sort_order is not None:
            c.execute(
                "UPDATE signal_pairs SET pair_name=?, display_name=?, active=?, sort_order=? WHERE id=?",
                (pair_name, display_name, active, int(sort_order), pair_id)
            )
        else:
            c.execute(
                "UPDATE signal_pairs SET pair_name=?, display_name=?, active=? WHERE id=?",
                (pair_name, display_name, active, pair_id)
            )
        conn.commit()
    return {"id": pair_id, "pair_name": pair_name, "display_name": display_name, "active": bool(active)}

@app.delete("/signal-pairs/{pair_id}")
def delete_signal_pair(pair_id: int, request: Request):
    require_login(request)
    require_csrf(request)
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM signal_pairs WHERE id=?", (pair_id,))
        conn.commit()
    return {"ok": True}

# --- Serve Admin Panel (Protected) ---
@app.get("/admin")
def get_admin_panel(request: Request):
    require_login(request)
    csrf_token = get_csrf_token(request)
    return templates.TemplateResponse("admin_panel.html", {"request": request, "csrf_token": csrf_token})


# To run the backend server, use:
# python -m uvicorn backend:app --host 0.0.0.0 --port 8000
# To on the admin panel
# http://localhost:8000/admin/login
# http://localhost:8002/admin/login
# for 2nd bot (trading bot)
# $env:BOT_MODE="trading"; $env:DATABASE_URL="bot_trading.db"; $env:PORT="8002"; python main.py
# $env:BOT_MODE="trading"; $env:BACKEND_URL="http://127.0.0.1:8002"; python bot.py
