from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler, CommandHandler, MessageHandler,
    filters
)
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import RetryAfter
from datetime import datetime
import asyncio
import ast
import io
import html as html_mod
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw

# ================= ENV =================
load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8002")
BOT_MODE = (os.getenv("BOT_MODE", "currency") or "currency").strip().lower()
if BOT_MODE not in ("currency", "trading"):
    BOT_MODE = "currency"
MODE_SUFFIX = BOT_MODE.upper()
TOKEN = os.getenv(f"BOT_TOKEN_{MODE_SUFFIX}") or os.getenv("BOT_TOKEN")
try:
    IMAGEAI_TIMEOUT = float(os.getenv("IMAGEAI_TIMEOUT", "35"))
except ValueError:
    IMAGEAI_TIMEOUT = 35.0
YOOAI_LOADING_GIF_URL = os.getenv(
    "YOOAI_LOADING_GIF_URL",
    "https://upload.wikimedia.org/wikipedia/commons/c/c7/Loading_2.gif",
).strip()
USE_DARK_LOADING_GIF = (os.getenv("USE_DARK_LOADING_GIF", "1") or "1").strip().lower() not in ("0", "false", "no")
try:
    YOOAI_LOADING_GIF_SECONDS = float(os.getenv("YOOAI_LOADING_GIF_SECONDS", "1"))
except ValueError:
    YOOAI_LOADING_GIF_SECONDS = 1.0
if YOOAI_LOADING_GIF_SECONDS < 0.2:
    YOOAI_LOADING_GIF_SECONDS = 0.2

_DARK_LOADING_GIF_CACHE: dict[str, bytes] = {}

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
AWAIT_BOT_NAME_KEY = "await_bot_name"
AWAIT_BOT_ABOUT_KEY = "await_bot_about"
AWAIT_BOT_DESCRIPTION_KEY = "await_bot_description"
AWAIT_BOT_COMMANDS_KEY = "await_bot_commands"
AWAIT_BOT_PRIVACY_POLICY_KEY = "await_bot_privacy_policy"
AWAIT_BOTPIC_KEY = "await_botpic"
AWAIT_DESCRIPTION_PICTURE_KEY = "await_description_picture"
VALID_TIMEFRAMES = {"1", "2", "5", "15", "30", "60"}

BTN_EDIT_NAME = "Edit Name"
BTN_EDIT_ABOUT = "Edit About"
BTN_EDIT_DESCRIPTION = "Edit Description"
BTN_EDIT_DESCRIPTION_PICTURE = "Edit Description Picture"
BTN_EDIT_BOTPIC = "Edit Botpic"
BTN_EDIT_COMMANDS = "Edit Commands"
BTN_EDIT_PRIVACY_POLICY = "Edit Privacy Policy"
BTN_BACK_TO_BOT = "<< Back to Bot"

CB_EDIT_NAME = "botpanel:edit_name"
CB_EDIT_ABOUT = "botpanel:edit_about"
CB_EDIT_DESCRIPTION = "botpanel:edit_description"
CB_EDIT_DESCRIPTION_PICTURE = "botpanel:edit_description_picture"
CB_EDIT_BOTPIC = "botpanel:edit_botpic"
CB_EDIT_COMMANDS = "botpanel:edit_commands"
CB_EDIT_PRIVACY_POLICY = "botpanel:edit_privacy_policy"
CB_BACK_TO_BOT = "botpanel:back"

START_BTN_FUTURE_SIGNAL = "Generate Future Signal"
START_BTN_YOOAI = "YOOAI Prediction"
START_BTN_CONTACT = "Contact Support"

CB_START_FUTURE_SIGNAL = "startmenu:futuresignal"
CB_START_YOOAI = "startmenu:yooai"
CB_START_CONTACT = "startmenu:contact"

CB_FUTURESIGNAL_PAIR_PREFIX = "futuresignal:pair:"
CB_FUTURESIGNAL_TIMEFRAME_PREFIX = "futuresignal:tf:"

BOT_SETTINGS_STATE_KEYS = (
    AWAIT_BOT_NAME_KEY,
    AWAIT_BOT_ABOUT_KEY,
    AWAIT_BOT_DESCRIPTION_KEY,
    AWAIT_BOT_COMMANDS_KEY,
    AWAIT_BOT_PRIVACY_POLICY_KEY,
    AWAIT_BOTPIC_KEY,
    AWAIT_DESCRIPTION_PICTURE_KEY,
)

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

FEATURE_USAGE_LIMIT = int(os.getenv("FEATURE_USAGE_LIMIT", "3") or "3")
if FEATURE_USAGE_LIMIT < 1:
    FEATURE_USAGE_LIMIT = 3
FEATURE_WINDOW_SECONDS = 24 * 60 * 60
FEATURE_FUTURESIGNAL = "future_signal"
FEATURE_YOOAI = "yooai"
FEATURE_LABELS = {
    FEATURE_FUTURESIGNAL: "Generate Future Signal",
    FEATURE_YOOAI: "YOOAI Prediction",
}
USAGE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_usage.db")
try:
    YOOAI_PENDING_TTL_SECONDS = int(os.getenv("YOOAI_PENDING_TTL_SECONDS", "1800") or "1800")
except ValueError:
    YOOAI_PENDING_TTL_SECONDS = 1800
if YOOAI_PENDING_TTL_SECONDS < 60:
    YOOAI_PENDING_TTL_SECONDS = 60


def init_usage_db():
    with sqlite3.connect(USAGE_DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS feature_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                username TEXT,
                feature TEXT NOT NULL,
                used_at INTEGER NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_feature_usage_user_feature_time
            ON feature_usage (telegram_id, feature, used_at)
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_uploads (
                telegram_id INTEGER NOT NULL,
                feature TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (telegram_id, feature)
            )
            """
        )
        conn.commit()


def _now_ts() -> int:
    return int(datetime.utcnow().timestamp())


def _format_reset_time(reset_ts: int | None) -> str:
    if not reset_ts:
        return "after 24 hours"
    return datetime.fromtimestamp(reset_ts).strftime("%Y-%m-%d %H:%M:%S")


def _feature_label(feature: str) -> str:
    return FEATURE_LABELS.get(feature, feature)


def _build_limit_block_message(feature: str, reset_ts: int | None) -> str:
    return (
        f"\u26A0\uFE0F Daily limit reached for {_feature_label(feature)}.\n"
        f"Limit: {FEATURE_USAGE_LIMIT} uses per 24 hours.\n"
        f"You can use it again after: {_format_reset_time(reset_ts)} (server time)."
    )


def _build_limit_reminder(feature: str, remaining: int) -> str:
    return (
        f"Reminder ({_feature_label(feature)}): "
        f"{remaining}/{FEATURE_USAGE_LIMIT} uses left in this 24-hour window."
    )


def _build_usage_after_consume_message(feature: str, remaining: int, reset_ts: int | None) -> str:
    if remaining > 0:
        return _build_limit_reminder(feature, remaining)
    return (
        f"Reminder ({_feature_label(feature)}): 0/{FEATURE_USAGE_LIMIT} uses left in this 24-hour window.\n"
        f"Next reset: {_format_reset_time(reset_ts)} (server time)."
    )


def get_feature_remaining(telegram_id: int, feature: str) -> tuple[int, int | None]:
    now_ts = _now_ts()
    window_start = now_ts - FEATURE_WINDOW_SECONDS
    cleanup_before = now_ts - (FEATURE_WINDOW_SECONDS * 7)
    with sqlite3.connect(USAGE_DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM feature_usage WHERE used_at < ?", (cleanup_before,))
        c.execute(
            """
            SELECT COUNT(*), MIN(used_at)
            FROM feature_usage
            WHERE telegram_id = ? AND feature = ? AND used_at >= ?
            """,
            (telegram_id, feature, window_start),
        )
        used, oldest = c.fetchone()
        conn.commit()
    used = int(used or 0)
    remaining = max(0, FEATURE_USAGE_LIMIT - used)
    reset_ts = (int(oldest) + FEATURE_WINDOW_SECONDS) if (oldest and remaining == 0) else None
    return remaining, reset_ts


def consume_feature_usage(telegram_id: int, username: str, feature: str) -> tuple[bool, int, int | None]:
    now_ts = _now_ts()
    window_start = now_ts - FEATURE_WINDOW_SECONDS
    cleanup_before = now_ts - (FEATURE_WINDOW_SECONDS * 7)
    with sqlite3.connect(USAGE_DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM feature_usage WHERE used_at < ?", (cleanup_before,))
        c.execute(
            """
            SELECT COUNT(*), MIN(used_at)
            FROM feature_usage
            WHERE telegram_id = ? AND feature = ? AND used_at >= ?
            """,
            (telegram_id, feature, window_start),
        )
        used, oldest = c.fetchone()
        used = int(used or 0)
        if used >= FEATURE_USAGE_LIMIT:
            conn.commit()
            reset_ts = (int(oldest) + FEATURE_WINDOW_SECONDS) if oldest else (now_ts + FEATURE_WINDOW_SECONDS)
            return False, 0, reset_ts

        c.execute(
            "INSERT INTO feature_usage (telegram_id, username, feature, used_at) VALUES (?, ?, ?, ?)",
            (telegram_id, username or "", feature, now_ts),
        )
        conn.commit()

    remaining = max(0, FEATURE_USAGE_LIMIT - (used + 1))
    first_use_in_window = int(oldest) if oldest else now_ts
    reset_ts = (first_use_in_window + FEATURE_WINDOW_SECONDS) if remaining == 0 else None
    return True, remaining, reset_ts


def set_pending_feature(telegram_id: int, feature: str):
    now_ts = _now_ts()
    cleanup_before = now_ts - (FEATURE_WINDOW_SECONDS * 7)
    with sqlite3.connect(USAGE_DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM pending_uploads WHERE created_at < ?", (cleanup_before,))
        c.execute(
            """
            INSERT INTO pending_uploads (telegram_id, feature, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id, feature) DO UPDATE SET created_at = excluded.created_at
            """,
            (telegram_id, feature, now_ts),
        )
        conn.commit()


def clear_pending_feature(telegram_id: int, feature: str):
    with sqlite3.connect(USAGE_DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "DELETE FROM pending_uploads WHERE telegram_id = ? AND feature = ?",
            (telegram_id, feature),
        )
        conn.commit()


def has_pending_feature(telegram_id: int, feature: str, ttl_seconds: int) -> bool:
    now_ts = _now_ts()
    with sqlite3.connect(USAGE_DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT created_at FROM pending_uploads WHERE telegram_id = ? AND feature = ?",
            (telegram_id, feature),
        )
        row = c.fetchone()
        if not row:
            return False
        created_at = int(row[0] or 0)
        if created_at <= 0 or (now_ts - created_at) > ttl_seconds:
            c.execute(
                "DELETE FROM pending_uploads WHERE telegram_id = ? AND feature = ?",
                (telegram_id, feature),
            )
            conn.commit()
            return False
        return True

def iter_backend_urls() -> list[str]:
    """Return candidate backend base URLs in priority order (deduplicated)."""
    candidates = [
        (BACKEND_URL or "").strip(),
        os.getenv("BACKEND_URL_ALT", "").strip(),
        "http://127.0.0.1:8002",
        "http://127.0.0.1:8000",
        "http://localhost:8002",
        "http://localhost:8000",
    ]
    seen = set()
    ordered = []
    for url in candidates:
        if not url:
            continue
        cleaned = url.rstrip("/")
        if cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered

def fetch_signal_pairs():
    """Fetch signal pairs from backend. Returns (choices_dict, display_dict, valid_set) or fallback defaults."""
    for base_url in iter_backend_urls():
        try:
            res = requests.get(f"{base_url}/signal-pairs", timeout=5)
            if res.status_code != 200:
                logging.warning(f"/signal-pairs returned {res.status_code} from {base_url}")
                continue
            pairs = res.json().get("pairs", [])
            active_pairs = [p for p in pairs if p.get("active", True)]
            if not active_pairs:
                logging.warning(f"/signal-pairs from {base_url} returned no active pairs")
                continue
            choices = {}
            display = {}
            valid = set()
            for i, p in enumerate(active_pairs, 1):
                pair_name = p["pair_name"]
                disp_name = p.get("display_name", pair_name)
                choices[str(i)] = pair_name
                if disp_name != pair_name:
                    display[pair_name] = disp_name
                valid.add(pair_name)
            return choices, display, valid
        except Exception as e:
            logging.warning(f"Failed to fetch /signal-pairs from {base_url}: {e}")
    # Fallback to hardcoded
    logging.warning("Falling back to hardcoded signal pairs; backend could not be reached.")
    return CURRENCY_PAIR_CHOICES, CURRENCY_PAIR_DISPLAY, set(CURRENCY_PAIRS.keys())

def display_pair_name(pair: str, display_map=None) -> str:
    if display_map:
        return display_map.get(pair, pair)
    return CURRENCY_PAIR_DISPLAY.get(pair, pair)

def fix_mojibake(text: str) -> str:
    """Recover common UTF-8 text decoded as Windows-1252/Latin-1.

    Only attempts recovery when mojibake markers are detected AND
    the text does NOT already contain valid emoji/Unicode above BMP.
    This prevents accidentally re-encoding text that is already correct.
    """
    if not text:
        return text
    # If text already contains characters above U+00FF (proper Unicode
    # emoji, CJK, box-drawing, etc.), it is NOT mojibake – return as-is.
    if any(ord(ch) > 0xFF for ch in text):
        return text
    # Only attempt fix when mojibake markers are present
    if not any(marker in text for marker in ("Ã", "Â", "â", "ðŸ", "Ã¢", "Ã©")):
        return text
    for src_enc in ("cp1252", "latin-1"):
        try:
            fixed = text.encode(src_enc).decode("utf-8")
            if fixed and fixed != text:
                return fixed
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return text

def build_default_start_message(mode: str) -> str:
    if mode == "trading":
        return (
            "\U0001f31f Welcome to twExSavage Trading Bot \U0001f31f\n\n"
            "\U0001f7e1 How to use this bot\n"
            "1- AT FIRST START THE BOT\n"
            "2- THEN CLICK \u25b6\ufe0f Start Bot\n"
            "3- IF YOU DIDN'T JOIN OUR CHANNEL YOU HAVE TO JOIN FIRST\n"
            "4- CLICK I HAVE JOINED\n"
            "5- NOW YOU CAN USE ALL TRADING FEATURES\n\n"
            "FOLLOW THE PROCESS TO START TRADING \U0001f4c8"
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

def build_absolute_backend_url(base_url: str, value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return raw
    if raw.startswith("//"):
        return f"https:{raw}"
    return f"{base_url.rstrip('/')}/{raw.lstrip('/')}"

def resolve_backend_image_ref(base_url: str, payload: dict) -> str:
    raw_value = (payload.get("value") or "").strip()
    preview_url = (payload.get("url") or "").strip()

    local_path = parse_local_image_ref(raw_value)
    if local_path:
        if os.path.isfile(local_path):
            return raw_value
        if preview_url:
            return build_absolute_backend_url(base_url, preview_url)
        logging.warning(f"Backend image local file missing and no preview URL: {local_path}")
        return ""

    if raw_value:
        return build_absolute_backend_url(base_url, raw_value)
    if preview_url:
        return build_absolute_backend_url(base_url, preview_url)
    return ""

def fetch_promo_image_url():
    """Fetch promo image URL from backend settings."""
    for base_url in iter_backend_urls():
        try:
            res = requests.get(f"{base_url}/settings/promo-image", timeout=5)
            if res.status_code == 200:
                data = res.json()
                image_ref = resolve_backend_image_ref(base_url, data)
                if image_ref:
                    return image_ref
        except Exception:
            continue
    return ""

def fetch_welcome_image_url():
    """Fetch welcome image URL from backend settings."""
    for base_url in iter_backend_urls():
        try:
            res = requests.get(f"{base_url}/settings/welcome-image", timeout=5)
            if res.status_code == 200:
                data = res.json()
                image_ref = resolve_backend_image_ref(base_url, data)
                if image_ref:
                    return image_ref
        except Exception:
            continue
    return ""

def parse_local_image_ref(image_ref: str):
    raw = (image_ref or "").strip()
    if not raw.lower().startswith("local:"):
        return None
    path = raw[6:].strip()
    if not path:
        return None
    return os.path.abspath(path)

async def send_image_reply(message, image_ref: str, caption: str, reply_markup=None) -> bool:
    local_path = parse_local_image_ref(image_ref)
    try:
        if local_path:
            if not os.path.isfile(local_path):
                logging.warning(f"Local image file not found: {local_path}")
                return False
            with open(local_path, "rb") as photo_file:
                await message.reply_photo(photo=photo_file, caption=caption, reply_markup=reply_markup)
            return True
        await message.reply_photo(photo=image_ref, caption=caption, reply_markup=reply_markup)
        return True
    except Exception as e:
        logging.warning(f"Failed to send image reply: {e}")
        return False


def _short_loading_caption(caption: str) -> str:
    text = re.sub(r"\s+", " ", str(caption or "").strip())
    if not text:
        return "Please wait..."
    if len(text) <= 52:
        return text
    return text[:49].rstrip() + "..."


def _build_dark_loading_gif_bytes(caption: str) -> bytes | None:
    cache_key = "dark_ring_loader_v2"
    cached = _DARK_LOADING_GIF_CACHE.get(cache_key)
    if cached:
        return cached
    try:
        width, height = 500, 290
        center_x, center_y = width // 2, height // 2
        segment_count = 12
        step = 360 / segment_count
        gap_deg = 7
        outer_radius = 64
        ring_width = 12

        background = Image.new("RGBA", (width, height), (20, 20, 21, 255))
        bg_draw = ImageDraw.Draw(background, "RGBA")
        for y in range(height):
            shade = 18 + int((y / max(1, height - 1)) * 10)
            bg_draw.line((0, y, width, y), fill=(shade, shade, shade + 1, 255))
        for x in range(0, width, 3):
            alpha = 10 if (x // 3) % 2 == 0 else 5
            bg_draw.line((x, 0, x, height), fill=(0, 0, 0, alpha))

        ring_box = (
            center_x - outer_radius,
            center_y - outer_radius,
            center_x + outer_radius,
            center_y + outer_radius,
        )
        glow_box = (
            center_x - outer_radius - 5,
            center_y - outer_radius - 5,
            center_x + outer_radius + 5,
            center_y + outer_radius + 5,
        )
        inner_radius = outer_radius - ring_width - 3
        frames = []
        for idx in range(segment_count):
            img = background.copy()
            draw = ImageDraw.Draw(img, "RGBA")

            for seg in range(segment_count):
                seg_start = -90 + (seg * step) + (gap_deg / 2)
                seg_end = -90 + ((seg + 1) * step) - (gap_deg / 2)
                draw.arc(ring_box, seg_start, seg_end, fill=(52, 54, 58, 220), width=ring_width)
                draw.arc(ring_box, seg_start, seg_end, fill=(26, 28, 32, 255), width=2)

            trail = [
                (0, (56, 255, 98, 255), (56, 255, 98, 120)),
                (1, (30, 205, 70, 255), (30, 205, 70, 90)),
                (2, (17, 138, 46, 255), (17, 138, 46, 70)),
            ]
            for back_steps, arc_color, glow_color in trail:
                active_seg = (idx - back_steps) % segment_count
                seg_start = -90 + (active_seg * step) + (gap_deg / 2)
                seg_end = -90 + ((active_seg + 1) * step) - (gap_deg / 2)
                draw.arc(glow_box, seg_start, seg_end, fill=glow_color, width=ring_width + 9)
                draw.arc(ring_box, seg_start, seg_end, fill=arc_color, width=ring_width)

            draw.ellipse(
                (
                    center_x - inner_radius,
                    center_y - inner_radius,
                    center_x + inner_radius,
                    center_y + inner_radius,
                ),
                fill=(22, 22, 24, 255),
            )
            draw.ellipse(
                (
                    center_x - inner_radius + 2,
                    center_y - inner_radius + 2,
                    center_x + inner_radius - 2,
                    center_y + inner_radius - 2,
                ),
                outline=(34, 36, 40, 180),
                width=1,
            )

            frames.append(img.convert("P", palette=Image.ADAPTIVE))

        buff = io.BytesIO()
        frames[0].save(
            buff,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=90,
            loop=0,
            optimize=True,
            disposal=2,
        )
        data = buff.getvalue()
        if data:
            _DARK_LOADING_GIF_CACHE[cache_key] = data
        return data
    except Exception as e:
        logging.warning(f"Failed to build dark loading GIF: {e}")
        return None


async def send_temporary_loading_gif(message, caption: str = "Analyzing image...", auto_delete: bool = True):
    """Send loading GIF. Optionally keep it until caller deletes."""
    if not YOOAI_LOADING_GIF_URL and not USE_DARK_LOADING_GIF:
        return
    loading_msg = None
    short_caption = _short_loading_caption(caption)
    if USE_DARK_LOADING_GIF:
        dark_gif = _build_dark_loading_gif_bytes(short_caption)
        if dark_gif:
            try:
                dark_stream = io.BytesIO(dark_gif)
                dark_stream.name = "loading_dark.gif"
                loading_msg = await message.reply_animation(
                    animation=dark_stream,
                    caption=short_caption,
                )
            except Exception as e:
                logging.warning(f"Failed to send dark loading GIF: {e}")

    if not loading_msg and YOOAI_LOADING_GIF_URL:
        try:
            loading_msg = await message.reply_animation(
                animation=YOOAI_LOADING_GIF_URL,
                caption=short_caption,
            )
        except Exception as e:
            logging.warning(f"Failed to send loading GIF: {e}")
            return None
    if not loading_msg:
        return None

    if auto_delete:
        await asyncio.sleep(YOOAI_LOADING_GIF_SECONDS)
        try:
            await loading_msg.delete()
        except Exception as e:
            logging.warning(f"Failed to delete YOOAI loading GIF message: {e}")
        return None
    return loading_msg


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
        res = requests.post(f"{BACKEND_URL}/gajaai/price", files=files, timeout=IMAGEAI_TIMEOUT)
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
        ("Pair", pair_text),
        ("Current Trend", trend_text),
        ("Signal", signal_text),
        ("Signal Strength", strength_text),
        ("Chart Pattern", pattern_text),
        ("Chart Type", chart_type_text),
        ("Support Zone Price", format_analysis_price(support) if is_present(support) else "N/A"),
        ("Resistance Zone Price", format_analysis_price(resistance) if is_present(resistance) else "N/A"),
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
        rows.append((title_text(key) or str(key), format_analysis_value(value)))

    key_col = max(len(str(label)) for label, _ in rows) if rows else 4
    formatted_lines = []
    for label, value in rows:
        value_text = str(value).replace("\r\n", "\n").replace("\r", "\n")
        value_text = " | ".join(part.strip() for part in value_text.split("\n") if part.strip()) or "N/A"
        formatted_lines.append(f"{str(label).ljust(key_col)} : {value_text}")
    return "\n".join(formatted_lines)

def build_ai_reply(data):
    if not isinstance(data, dict):
        return "Image processed, but response format is invalid."
    if "error" in data:
        err = str(data.get("error"))
        if "502 Bad Gateway" in err or "Trading API returned 502" in err:
            return "Trading analysis server is temporarily busy. Please try again in a moment."
        return f"Error: {err}"
    if data.get("mode") == "trading" or "analysis" in data:
        analysis = data.get("analysis")
        if analysis is None:
            analysis = data
        safe_summary = html_mod.escape(build_trading_summary(analysis))
        return f"\U0001F9E0 <b>YooAI \u2014 Trade Analysis</b>\n\n<pre>{safe_summary}</pre>"
    currency = data.get("currency", "USD")
    price = format_money(data.get("price", ""))
    discount = format_money(data.get("discount", ""))
    safe_currency = html_mod.escape(str(currency))
    safe_price = html_mod.escape(str(price))
    safe_discount = html_mod.escape(str(discount))
    return (
        "\U0001F4B1 <b>YooAI \u2014 Currency</b>\n\n"
        f"<pre>Currency : {safe_currency}\nPrice    : ${safe_price}\nDiscount : ${safe_discount}</pre>"
    )


# ================= FUTURE SIGNAL SUBPROCESS =================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FUTURE_SIGNAL_SCRIPT = os.path.join(SCRIPT_DIR, "future_signal.py")

async def run_future_signal_script(pair: str, timeframe: int) -> str:
    """Run future_signal.py as a subprocess and return its stdout output."""
    # Normalize pair name for the script
    asset_name = pair.replace("_OTC", "_otc")

    cmd = [
        sys.executable, FUTURE_SIGNAL_SCRIPT,
        "--assets", asset_name,
        "--timeframe", str(timeframe),
        "--percentage", "70",
        "--days", "10",
        "--martingale", "0",
    ]

    # Force child Python process to use UTF-8 for all I/O
    child_env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=120,
                    cwd=SCRIPT_DIR,
                    env=child_env,
                )
            ),
            timeout=130,
        )

        output = result.stdout.strip()
        error_output = result.stderr.strip()

        if result.returncode != 0:
            logging.error(f"future_signal.py error (rc={result.returncode}): {error_output}")
            if not output:
                # Show meaningful error to user
                if error_output:
                    # Extract last meaningful error line
                    err_lines = [l.strip() for l in error_output.split("\n") if l.strip()]
                    last_err = err_lines[-1] if err_lines else error_output[:300]
                    return f"\u26A0\uFE0F Signal generation failed for this pair.\n\nError: {last_err[:300]}"
                return "\u26A0\uFE0F Signal generation failed. This pair may not be supported."

        # Build a clean, canonical message from parsed signal rows only.
        signal_pattern = re.compile(
            r"([A-Za-z][A-Za-z0-9_]*)\s+M(\d{1,3})\s+([0-2]\d:[0-5]\d)\s+(CALL|PUT)\b",
            re.IGNORECASE,
        )
        total_pattern = re.compile(r"Total\s+signals\s*:\s*(\d+)", re.IGNORECASE)

        # Filter out non-signal lines (keep only parsed signal rows + total)
        lines = output.split("\n")
        signal_rows = []
        reported_total = None
        # Known noise lines to skip
        skip_phrases = [
            "list created successfully",
            "cataloger schedules signals",
            "schedule at",
            "Signals will always be available",
            "hours in the future",
        ]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Skip known noise/warning lines
            if any(phrase in line for phrase in skip_phrases):
                continue
            # Parse signal row from anywhere in the line; ignore broken prefixes.
            m_signal = signal_pattern.search(line)
            if m_signal:
                asset, tf, hhmm, direction = m_signal.groups()
                direction_up = direction.upper()
                dir_emoji = "\U0001F7E2" if direction_up == "CALL" else "\U0001F534"
                signal_rows.append((dir_emoji, asset.upper(), f"M{tf}", hhmm, direction_up))
                continue

            m_total = total_pattern.search(line)
            if m_total:
                reported_total = int(m_total.group(1))
                continue

            if "No signals found" in line:
                return f"\u26A0\uFE0F No signals found for {display_pair_name(pair)}."
            # All other lines are skipped as noise.

        if signal_rows:
            safe_pair = html_mod.escape(str(pair))
            count = reported_total if reported_total is not None else len(signal_rows)
            header = f"\U0001F4C8 <b>Future Signals \u2014 {safe_pair} (M{timeframe})</b>\n\n"
            pair_col = max(len(asset) for _, asset, _, _, _ in signal_rows)
            tf_col = max(len(tf) for _, _, tf, _, _ in signal_rows)
            table_lines = []
            for emoji, asset, tf, hhmm, direction_up in signal_rows:
                table_lines.append(
                    f"{emoji} {asset.ljust(pair_col)}  {tf.ljust(tf_col)}  {hhmm}  {direction_up}"
                )
            code_block = html_mod.escape("\n".join(table_lines))
            total_text = f"\n\n\U0001F4CB <b>Total signals: {count}</b>"
            return header + f"<pre>{code_block}</pre>" + total_text
        else:
            # No valid signal lines found
            logging.warning(f"No signal lines parsed for {pair} M{timeframe}. Raw output: {output[:300]}. Stderr: {error_output[:200]}")
            if error_output:
                err_lines = [l.strip() for l in error_output.split("\n") if l.strip()]
                last_err = err_lines[-1] if err_lines else error_output[:300]
                return f"\u26A0\uFE0F No signals found for {display_pair_name(pair)}.\n\nError: {last_err[:300]}"
            return ""

    except asyncio.TimeoutError:
        logging.error("future_signal.py timed out")
        return "\u26A0\uFE0F Signal generation timed out. Please try again."
    except Exception as e:
        logging.error(f"future_signal.py exception: {e}")
        return f"\u26A0\uFE0F Error running signal script: {str(e)[:200]}"


def split_message(text: str, max_length: int = 4000) -> list:
    """Split a long message into chunks for Telegram (max 4096 chars)."""
    if len(text) <= max_length:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break
        # Find a good split point (newline)
        split_at = text.rfind("\n", 0, max_length)
        if split_at <= 0:
            split_at = max_length
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks

def start_menu_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(START_BTN_FUTURE_SIGNAL, callback_data=CB_START_FUTURE_SIGNAL)],
            [InlineKeyboardButton(START_BTN_YOOAI, callback_data=CB_START_YOOAI)],
            [InlineKeyboardButton(START_BTN_CONTACT, callback_data=CB_START_CONTACT)],
        ]
    )

def futuresignal_pair_keyboard(choices, display):
    ordered_pairs = []
    for k, pair in choices.items():
        rank = int(k) if str(k).isdigit() else 10_000
        ordered_pairs.append((rank, str(k), pair))
    ordered_pairs.sort(key=lambda item: (item[0], item[1]))

    rows = []
    current_row = []
    for _, _, pair in ordered_pairs:
        label = display_pair_name(pair, display)
        current_row.append(
            InlineKeyboardButton(
                label,
                callback_data=f"{CB_FUTURESIGNAL_PAIR_PREFIX}{pair}",
            )
        )
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    return InlineKeyboardMarkup(rows)

def futuresignal_timeframe_keyboard(pair: str):
    rows = []
    current_row = []
    for tf in ("1", "2", "5", "15", "30", "60"):
        current_row.append(
            InlineKeyboardButton(
                f"M{tf}",
                callback_data=f"{CB_FUTURESIGNAL_TIMEFRAME_PREFIX}{pair}:{tf}",
            )
        )
        if len(current_row) == 3:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    return InlineKeyboardMarkup(rows)

async def send_futuresignal_result(message, pair: str, timeframe: int, display=None):
    loading_msg = await send_temporary_loading_gif(
        message,
        caption=f"Generating signals for {display_pair_name(pair, display)} (M{timeframe})...",
        auto_delete=False,
    )
    try:
        signal_output = fix_mojibake(await run_future_signal_script(pair, timeframe))
    finally:
        if loading_msg:
            try:
                await loading_msg.delete()
            except Exception as e:
                logging.warning(f"Failed to delete futuresignal loading GIF message: {e}")
    if signal_output:
        for chunk in split_message(signal_output, 4000):
            safe_chunk = fix_mojibake(chunk)
            try:
                await message.reply_text(safe_chunk, parse_mode="HTML")
            except Exception as e:
                logging.warning(f"Failed to send futuresignal chunk with HTML parse mode: {e}")
                plain_chunk = re.sub(r"</?[^>]+>", "", safe_chunk)
                await message.reply_text(fix_mojibake(plain_chunk))
    else:
        await message.reply_text(
            f"\u26A0\uFE0F No signals found for {display_pair_name(pair, display)} (M{timeframe}).\n\n"
            "Possible reasons:\n"
            "\u2022 This pair may not be supported on the platform\n"
            "\u2022 Market may be closed right now\n"
            "\u2022 Not enough data to generate signals\n\n"
            "Try with a different pair or timeframe."
        )

def bot_settings_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(BTN_EDIT_NAME, callback_data=CB_EDIT_NAME),
                InlineKeyboardButton(BTN_EDIT_ABOUT, callback_data=CB_EDIT_ABOUT),
            ],
            [
                InlineKeyboardButton(BTN_EDIT_DESCRIPTION, callback_data=CB_EDIT_DESCRIPTION),
                InlineKeyboardButton(BTN_EDIT_DESCRIPTION_PICTURE, callback_data=CB_EDIT_DESCRIPTION_PICTURE),
            ],
            [
                InlineKeyboardButton(BTN_EDIT_BOTPIC, callback_data=CB_EDIT_BOTPIC),
                InlineKeyboardButton(BTN_EDIT_COMMANDS, callback_data=CB_EDIT_COMMANDS),
            ],
            [
                InlineKeyboardButton(BTN_EDIT_PRIVACY_POLICY, callback_data=CB_EDIT_PRIVACY_POLICY),
                InlineKeyboardButton(BTN_BACK_TO_BOT, callback_data=CB_BACK_TO_BOT),
            ],
        ]
    )

def clear_bot_settings_state(context):
    for key in BOT_SETTINGS_STATE_KEYS:
        context.user_data.pop(key, None)

def set_bot_settings_state(context, key):
    clear_bot_settings_state(context)
    context.user_data[key] = True

def parse_bot_commands(text: str):
    commands = []
    seen = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("/"):
            line = line[1:]
        if " - " in line:
            cmd, desc = line.split(" - ", 1)
        elif ":" in line:
            cmd, desc = line.split(":", 1)
        else:
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                return None
            cmd, desc = parts
        cmd = cmd.strip().lower()
        desc = desc.strip()
        if not cmd or not desc:
            return None
        if len(cmd) > 32 or not cmd.replace("_", "").isalnum():
            return None
        if cmd in seen:
            continue
        seen.add(cmd)
        commands.append(BotCommand(cmd, desc[:256]))
    return commands

def is_valid_http_url(url: str) -> bool:
    value = (url or "").strip().lower()
    return value.startswith("http://") or value.startswith("https://")

# ================= SET BOT MENU =================
async def set_bot_menu(app):
    """Register bot commands that appear in the Telegram menu."""
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("menu", "Main Menu"),
    ]
    await app.bot.set_my_commands(commands)

# ================= SAWA COMMAND =================
async def sawa(update, context):
    await store_user(update)
    await update.message.reply_text("Sawa! \U0001F604")

# ================= AIDI COMMAND =================
async def aidi(update, context):
    await store_user(update)
    user_id = update.message.from_user.id
    await update.message.reply_text(f"Your Telegram ID: {user_id}")

# ================= START =================
PROMO_TEXT = (
    "\U0001F525\U0001F4C8 Want 10 FREE NON MTG BUG Quotex Signals?\n\n"
    "\U0001F449 Click on JOIN CHANNEL now!\n"
    "And you will get FREE 10 QUOTEX SIGNALS\n\n"
    "\U0001F517 LINK :\U0001F447\U0001F447\U0001F447\U0001F447\n"
    "https://t.me/+Gfa2prDUdPVlMzE1\n"
    "https://t.me/+Gfa2prDUdPVlMzE1\n"
    "https://t.me/+Gfa2prDUdPVlMzE1\n"
    "https://t.me/+Gfa2prDUdPVlMzE1\n\n"
    "Signals starting in 5 Minutes"
)

TRADING_START_PROMO_TEXT = (
    "\U0001F680 Welcome to the YOO/twExSavage Trading Edge!\n"
    "Ready to stop guessing and start winning on Pocket Option? I've helped 500+ traders turn their first deposit into a consistent daily income. https://tinyurl.com/twExSavage\n\n"
    "Why Join Us?\n"
    "\u26A1\uFE0F Pro Signals: 90%+ Accuracy.\n"
    "\U0001F4CA Live Coaching: Learn while you earn.\n"
    "\U0001F4B0 Pocket Option Bonus: Use code [HEYYOO] for a 50% deposit bonus!\n"
    "How to start: > 1. Register via the link below\n\n"
    "WORLDWIDE LINK\U0001F310\n"
    "https://tinyurl.com/twExSavage\n"
    "RUSSIAN LINK\U0001F1F7\U0001F1FA\n"
    "https://tinyurl.com/twExSavageRU\n"
    "2. Send me your Pocket Option ID to verify.\n"
    "3. Get added to the Private Couching Room instantly.\n\n"
    "CONTACT TRADERS @YOO_SUPPORT1"
)

TRADING_WELCOME_TEXT = (
    "\U0001F44B Welcome to twExSavage Trading Bot!\n"
    "Choose an option below to continue."
)

async def start(update, context):
    await store_user(update)

    if BOT_MODE == "trading":
        first_message_text = TRADING_START_PROMO_TEXT
        second_message_text = TRADING_WELCOME_TEXT
    else:
        first_message_text = PROMO_TEXT
        second_message_text = fetch_start_message()

    # --- 1st message: Promo image + promo text ---
    promo_image_url = fetch_promo_image_url()
    welcome_image_url = fetch_welcome_image_url() or promo_image_url
    if promo_image_url:
        sent = await send_image_reply(update.message, promo_image_url, first_message_text)
        if not sent:
            await update.message.reply_text(first_message_text)
    else:
        await update.message.reply_text(first_message_text)

    # --- 2nd message: Welcome message + menu buttons (with image when available) ---
    if welcome_image_url:
        sent = await send_image_reply(
            update.message,
            welcome_image_url,
            second_message_text,
            reply_markup=start_menu_keyboard(),
        )
        if sent:
            return

    await update.message.reply_text(
        second_message_text,
        reply_markup=start_menu_keyboard(),
    )

async def menu(update, context):
    """Show main menu with inline buttons."""
    await store_user(update)
    if BOT_MODE == "trading":
        await update.message.reply_text(
            "\U0001F4CB Main Menu\nChoose an option below:",
            reply_markup=start_menu_keyboard(),
        )
    else:
        choices, display, valid = fetch_signal_pairs()
        context.user_data["_pair_choices"] = choices
        context.user_data["_pair_display"] = display
        context.user_data["_pair_valid"] = valid
        await update.message.reply_text(
            "\U0001F4CB Main Menu\nChoose an option below:",
            reply_markup=start_menu_keyboard(),
        )

async def start_menu_callback(update, context):
    query = update.callback_query
    if not query:
        return

    data = query.data or ""
    user = query.from_user
    user_id = user.id if user else 0
    await query.answer()
    if not query.message:
        return

    if data == CB_START_FUTURE_SIGNAL:
        remaining, reset_ts = get_feature_remaining(user_id, FEATURE_FUTURESIGNAL)
        if remaining <= 0:
            await query.message.reply_text(_build_limit_block_message(FEATURE_FUTURESIGNAL, reset_ts))
            return
        choices, display, valid = fetch_signal_pairs()
        context.user_data["_pair_choices"] = choices
        context.user_data["_pair_display"] = display
        context.user_data["_pair_valid"] = valid
        context.user_data[AWAIT_FUTURESIGNAL_PAIR_KEY] = True
        await query.message.reply_text(
            f"{_build_limit_reminder(FEATURE_FUTURESIGNAL, remaining)}\n\nPlease Choose a Pair for Signal",
            reply_markup=futuresignal_pair_keyboard(choices, display),
        )
        return

    if data == CB_START_YOOAI:
        remaining, reset_ts = get_feature_remaining(user_id, FEATURE_YOOAI)
        if remaining <= 0:
            await query.message.reply_text(_build_limit_block_message(FEATURE_YOOAI, reset_ts))
            return
        context.user_data[AWAIT_IMAGEAI_KEY] = True
        set_pending_feature(user_id, FEATURE_YOOAI)
        await query.message.reply_text(
            f"{_build_limit_reminder(FEATURE_YOOAI, remaining)}\nPlease Upload your image"
        )
        return

    if data == CB_START_CONTACT:
        await query.message.reply_text(
            "Support option is not configured yet. Please contact @YOO_SUPPORT1."
        )
        return

async def futuresignal_callback(update, context):
    query = update.callback_query
    if not query:
        return
    data = query.data or ""

    if data.startswith(CB_FUTURESIGNAL_PAIR_PREFIX):
        raw_pair = data[len(CB_FUTURESIGNAL_PAIR_PREFIX):].strip().upper()
        choices, display, valid = fetch_signal_pairs()
        context.user_data["_pair_choices"] = choices
        context.user_data["_pair_display"] = display
        context.user_data["_pair_valid"] = valid
        if raw_pair not in valid:
            await query.answer("Pair unavailable", show_alert=True)
            return
        context.user_data.pop(AWAIT_FUTURESIGNAL_PAIR_KEY, None)
        context.user_data["futuresignal_pair"] = raw_pair
        context.user_data[AWAIT_FUTURESIGNAL_TIMEFRAME_KEY] = True
        await query.answer()
        if query.message:
            await query.message.reply_text(
                f"Pair selected: {display_pair_name(raw_pair, display)}\nChoose timeframe:",
                reply_markup=futuresignal_timeframe_keyboard(raw_pair),
            )
        return

    if data.startswith(CB_FUTURESIGNAL_TIMEFRAME_PREFIX):
        payload = data[len(CB_FUTURESIGNAL_TIMEFRAME_PREFIX):]
        pair_part, sep, tf = payload.rpartition(":")
        pair = pair_part.strip().upper() if sep else ""
        tf = tf.strip()
        choices, display, valid = fetch_signal_pairs()
        context.user_data["_pair_choices"] = choices
        context.user_data["_pair_display"] = display
        context.user_data["_pair_valid"] = valid
        if pair not in valid:
            await query.answer("Pair unavailable", show_alert=True)
            return
        if tf not in VALID_TIMEFRAMES:
            await query.answer("Invalid timeframe", show_alert=True)
            return
        context.user_data.pop(AWAIT_FUTURESIGNAL_TIMEFRAME_KEY, None)
        context.user_data.pop("futuresignal_pair", None)
        username = query.from_user.username if query.from_user else ""
        allowed, remaining, reset_ts = consume_feature_usage(
            query.from_user.id if query.from_user else 0,
            username or "",
            FEATURE_FUTURESIGNAL,
        )
        if not allowed:
            await query.answer("Daily limit reached", show_alert=True)
            if query.message:
                await query.message.reply_text(_build_limit_block_message(FEATURE_FUTURESIGNAL, reset_ts))
            return
        await query.answer()
        if query.message:
            await query.message.reply_text(_build_usage_after_consume_message(FEATURE_FUTURESIGNAL, remaining, reset_ts))
            await send_futuresignal_result(query.message, pair, int(tf), display)
        return

    await query.answer()

# ================= BOT PANEL =================
async def botpanel(update, context):
    await store_user(update)
    if not is_admin(update.message.from_user.id):
        await update.message.reply_text("Admin only")
        return
    clear_bot_settings_state(context)
    await update.message.reply_text(
        "Bot settings panel opened. Choose an option.",
        reply_markup=bot_settings_keyboard(),
    )

async def botpanel_callback(update, context):
    query = update.callback_query
    if not query:
        return

    if not is_admin(query.from_user.id):
        await query.answer("Admin only", show_alert=True)
        return

    data = query.data or ""
    if data == CB_BACK_TO_BOT:
        clear_bot_settings_state(context)
        await query.answer("Back to bot")
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    prompt_map = {
        CB_EDIT_NAME: (AWAIT_BOT_NAME_KEY, "OK. Send me the new bot name."),
        CB_EDIT_ABOUT: (AWAIT_BOT_ABOUT_KEY, "OK. Send me the new about text."),
        CB_EDIT_DESCRIPTION: (AWAIT_BOT_DESCRIPTION_KEY, "OK. Send me the new description."),
        CB_EDIT_DESCRIPTION_PICTURE: (AWAIT_DESCRIPTION_PICTURE_KEY, "OK. Send me the new description picture."),
        CB_EDIT_BOTPIC: (AWAIT_BOTPIC_KEY, "OK. Send me the new profile photo for the bot."),
        CB_EDIT_COMMANDS: (
            AWAIT_BOT_COMMANDS_KEY,
            "Send commands as lines. Example:\n"
            "/start - Start bot\n"
            "/help - Help text\n\n"
            "Send 'clear' to remove all commands."
        ),
        CB_EDIT_PRIVACY_POLICY: (AWAIT_BOT_PRIVACY_POLICY_KEY, "Send the privacy policy URL (http:// or https://)."),
    }

    flow = prompt_map.get(data)
    if not flow:
        await query.answer()
        return

    state_key, prompt = flow
    set_bot_settings_state(context, state_key)
    await query.answer()
    if query.message:
        await query.message.reply_text(prompt)

# ================= IMAGEAI COMMAND =================
async def imageai(update, context):
    await store_user(update)
    user = update.message.from_user
    remaining, reset_ts = get_feature_remaining(user.id, FEATURE_YOOAI)
    if remaining <= 0:
        await update.message.reply_text(_build_limit_block_message(FEATURE_YOOAI, reset_ts))
        return
    context.user_data[AWAIT_IMAGEAI_KEY] = True
    set_pending_feature(user.id, FEATURE_YOOAI)
    await update.message.reply_text(
        f"{_build_limit_reminder(FEATURE_YOOAI, remaining)}\nPlease Upload your image"
    )

# ================= CURRENCY CONVERTER COMMAND =================
async def currencycoveter(update, context):
    await store_user(update)
    choices, display, valid = fetch_signal_pairs()
    context.user_data["_pair_choices"] = choices
    context.user_data["_pair_display"] = display
    context.user_data["_pair_valid"] = valid
    pair_list = "\n".join(
        f"{k}. {display_pair_name(v, display)}" for k, v in choices.items()
    )
    context.user_data[AWAIT_CURRENCY_KEY] = True
    await update.message.reply_text(
        f"Please Choose a Pair of Currency\n\n{pair_list}"
    )

# ================= FUTURE SIGNAL COMMAND =================
async def futuresignal(update, context):
    await store_user(update)
    user = update.message.from_user
    remaining, reset_ts = get_feature_remaining(user.id, FEATURE_FUTURESIGNAL)
    if remaining <= 0:
        await update.message.reply_text(_build_limit_block_message(FEATURE_FUTURESIGNAL, reset_ts))
        return
    choices, display, valid = fetch_signal_pairs()
    context.user_data["_pair_choices"] = choices
    context.user_data["_pair_display"] = display
    context.user_data["_pair_valid"] = valid
    context.user_data[AWAIT_FUTURESIGNAL_PAIR_KEY] = True
    await update.message.reply_text(
        f"{_build_limit_reminder(FEATURE_FUTURESIGNAL, remaining)}\n\nPlease Choose a Pair for Signal",
        reply_markup=futuresignal_pair_keyboard(choices, display),
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
    text = (update.message.text or "").strip()

    # Admin retarget: forward text to target users
    if is_admin(update.message.from_user.id):
        if "retarget_user" in context.user_data or "retarget_all" in context.user_data:
            await admin_media_handler(update, context)
            return

        if context.user_data.get(AWAIT_BOT_NAME_KEY):
            name = text[:64]
            if not name:
                await update.message.reply_text("Name cannot be empty. Send a valid bot name.")
                return
            try:
                await context.bot.set_my_name(name=name)
                context.user_data.pop(AWAIT_BOT_NAME_KEY, None)
                await update.message.reply_text(f"Done. New bot name: {name}")
            except Exception as e:
                await update.message.reply_text(f"Failed to update name: {str(e)[:200]}")
            return

        if context.user_data.get(AWAIT_BOT_ABOUT_KEY):
            about = text[:120]
            if not about:
                await update.message.reply_text("About text cannot be empty.")
                return
            try:
                await context.bot.set_my_short_description(short_description=about)
                context.user_data.pop(AWAIT_BOT_ABOUT_KEY, None)
                await update.message.reply_text("Done. About text updated.")
            except Exception as e:
                await update.message.reply_text(f"Failed to update about text: {str(e)[:200]}")
            return

        if context.user_data.get(AWAIT_BOT_DESCRIPTION_KEY):
            description = text[:512]
            if not description:
                await update.message.reply_text("Description cannot be empty.")
                return
            try:
                await context.bot.set_my_description(description=description)
                context.user_data.pop(AWAIT_BOT_DESCRIPTION_KEY, None)
                await update.message.reply_text("Done. Description updated.")
            except Exception as e:
                await update.message.reply_text(f"Failed to update description: {str(e)[:200]}")
            return

        if context.user_data.get(AWAIT_BOT_COMMANDS_KEY):
            if text.lower() == "clear":
                try:
                    await context.bot.set_my_commands([])
                    context.user_data.pop(AWAIT_BOT_COMMANDS_KEY, None)
                    await update.message.reply_text("Done. Commands cleared.")
                except Exception as e:
                    await update.message.reply_text(f"Failed to clear commands: {str(e)[:200]}")
                return
            commands = parse_bot_commands(text)
            if not commands:
                await update.message.reply_text(
                    "Invalid format. Example:\n"
                    "/start - Start bot\n"
                    "/help - Help text"
                )
                return
            try:
                await context.bot.set_my_commands(commands)
                context.user_data.pop(AWAIT_BOT_COMMANDS_KEY, None)
                await update.message.reply_text(f"Done. {len(commands)} command(s) updated.")
            except Exception as e:
                await update.message.reply_text(f"Failed to update commands: {str(e)[:200]}")
            return

        if context.user_data.get(AWAIT_BOT_PRIVACY_POLICY_KEY):
            if not is_valid_http_url(text):
                await update.message.reply_text("Invalid URL. Please send http:// or https:// link.")
                return
            context.bot_data["privacy_policy_url"] = text
            context.user_data.pop(AWAIT_BOT_PRIVACY_POLICY_KEY, None)
            await update.message.reply_text(f"Done. Privacy Policy URL saved:\n{text}")
            return

    # --- Future Signal: pair selection ---
    if context.user_data.get(AWAIT_FUTURESIGNAL_PAIR_KEY):
        raw = text.upper()
        choices = context.user_data.get("_pair_choices", CURRENCY_PAIR_CHOICES)
        display = context.user_data.get("_pair_display", CURRENCY_PAIR_DISPLAY)
        valid = context.user_data.get("_pair_valid", set(CURRENCY_PAIRS.keys()))
        pair = choices.get(raw, raw)
        if pair in valid:
            context.user_data.pop(AWAIT_FUTURESIGNAL_PAIR_KEY, None)
            context.user_data["futuresignal_pair"] = pair
            context.user_data[AWAIT_FUTURESIGNAL_TIMEFRAME_KEY] = True
            await update.message.reply_text(
                f"Pair selected: {display_pair_name(pair, display)}\nChoose timeframe:",
                reply_markup=futuresignal_timeframe_keyboard(pair),
            )
        else:
            pair_names = ", ".join(display_pair_name(p, display) for p in valid)
            await update.message.reply_text(
                f"Invalid pair. Please choose one of:\n{pair_names}"
            )
        return

    # --- Future Signal: timeframe selection ---
    if context.user_data.get(AWAIT_FUTURESIGNAL_TIMEFRAME_KEY):
        raw = text
        if raw in VALID_TIMEFRAMES:
            context.user_data.pop(AWAIT_FUTURESIGNAL_TIMEFRAME_KEY, None)
            pair = context.user_data.pop("futuresignal_pair", "EURUSD")
            timeframe = int(raw)
            display = context.user_data.get("_pair_display", CURRENCY_PAIR_DISPLAY)
            user = update.message.from_user
            allowed, remaining, reset_ts = consume_feature_usage(
                user.id,
                user.username or "",
                FEATURE_FUTURESIGNAL,
            )
            if not allowed:
                await update.message.reply_text(_build_limit_block_message(FEATURE_FUTURESIGNAL, reset_ts))
                return
            await update.message.reply_text(_build_usage_after_consume_message(FEATURE_FUTURESIGNAL, remaining, reset_ts))
            await send_futuresignal_result(update.message, pair, timeframe, display)
            return
        else:
            await update.message.reply_text("Invalid timeframe. Please enter: 1, 2, 5, 15, 30, or 60")
        return

    # --- Currency Converter: pair selection ---
    if context.user_data.get(AWAIT_CURRENCY_KEY):
        raw = text.upper()
        choices = context.user_data.get("_pair_choices", CURRENCY_PAIR_CHOICES)
        display = context.user_data.get("_pair_display", CURRENCY_PAIR_DISPLAY)
        valid = context.user_data.get("_pair_valid", set(CURRENCY_PAIRS.keys()))
        pair = choices.get(raw, raw)
        if pair in valid:
            context.user_data.pop(AWAIT_CURRENCY_KEY, None)
            context.user_data["selected_pair"] = pair
            context.user_data[AWAIT_TIMEFRAME_KEY] = True
            await update.message.reply_text("Enter the timeframe (1, 2, 5, 15, 30, 60)")
        else:
            pair_names = ", ".join(display_pair_name(p, display) for p in valid)
            await update.message.reply_text(
                f"Invalid pair. Please choose one of:\n{pair_names}"
            )
        return

    # --- Currency Converter: timeframe selection ---
    if context.user_data.get(AWAIT_TIMEFRAME_KEY):
        raw = text
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
            json={"text": text},
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

        if context.user_data.get(AWAIT_BOTPIC_KEY):
            context.user_data.pop(AWAIT_BOTPIC_KEY, None)
            if update.message.photo:
                await update.message.reply_text(
                    "Telegram Bot API cannot update bot profile photo directly.\n"
                    "Use @BotFather -> /mybots -> Edit Bot -> Edit Botpic."
                )
            else:
                await update.message.reply_text("Please send a photo.")
            return

        if context.user_data.get(AWAIT_DESCRIPTION_PICTURE_KEY):
            context.user_data.pop(AWAIT_DESCRIPTION_PICTURE_KEY, None)
            if update.message.photo:
                await update.message.reply_text(
                    "Telegram Bot API cannot update description picture directly.\n"
                    "Use @BotFather -> /mybots -> Edit Bot."
                )
            else:
                await update.message.reply_text("Please send a photo.")
            return

    user = update.message.from_user
    yooai_pending = context.user_data.get(AWAIT_IMAGEAI_KEY) or has_pending_feature(
        user.id,
        FEATURE_YOOAI,
        YOOAI_PENDING_TTL_SECONDS,
    )
    if yooai_pending:
        image_doc = update.message.document if update.message.document and (update.message.document.mime_type or "").startswith("image/") else None
        if update.message.photo or image_doc:
            context.user_data.pop(AWAIT_IMAGEAI_KEY, None)
            clear_pending_feature(user.id, FEATURE_YOOAI)
            allowed, remaining, reset_ts = consume_feature_usage(
                user.id,
                user.username or "",
                FEATURE_YOOAI,
            )
            if not allowed:
                await update.message.reply_text(_build_limit_block_message(FEATURE_YOOAI, reset_ts))
                return
            await update.message.reply_text(_build_usage_after_consume_message(FEATURE_YOOAI, remaining, reset_ts))
            loading_msg = None
            data = None
            try:
                loading_msg = await send_temporary_loading_gif(
                    update.message,
                    caption="Analyzing image...",
                    auto_delete=False,
                )
                if update.message.photo:
                    photo = update.message.photo[-1]
                    tg_file = await photo.get_file()
                    filename = f"{photo.file_unique_id}.jpg"
                else:
                    tg_file = await image_doc.get_file()
                    filename = image_doc.file_name or f"{image_doc.file_unique_id}.jpg"
                file_bytes = await tg_file.download_as_bytearray()
                data = fetch_imageai_price(bytes(file_bytes), filename)
            except Exception:
                data = None
            finally:
                if loading_msg:
                    try:
                        await loading_msg.delete()
                    except Exception as e:
                        logging.warning(f"Failed to delete YooAI loading GIF message: {e}")

            if data:
                ai_reply = build_ai_reply(data)
                try:
                    await update.message.reply_text(ai_reply, parse_mode="HTML")
                except Exception as e:
                    logging.warning(f"Failed to send YooAI reply with HTML parse mode: {e}")
                    plain_reply = re.sub(r"</?[^>]+>", "", ai_reply)
                    await update.message.reply_text(fix_mojibake(plain_reply))
            else:
                await update.message.reply_text("Image processed, but result not available.")
        else:
            await update.message.reply_text("Please upload an image (photo or image file).")
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
        await update.message.reply_text("Admin only")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /add <command> <reply>")
        return

    cmd = context.args[0].lower()
    reply = " ".join(context.args[1:])
    custom_commands[cmd] = reply

    await update.message.reply_text(f"[OK] /{cmd} added")

# ================= COMMAND ROUTER =================
async def command_router(update, context):
    await store_user(update)

    cmd = update.message.text.lstrip("/").split()[0].lower()

    if cmd in ["start", "menu", "add", "retarget", "retarget_all", "imageai", "gajaai", "yooai", "currencycoveter", "futuresignal", "botpanel"]:
        return

    if cmd in custom_commands:
        await update.message.reply_text(custom_commands[cmd])
    else:
        await update.message.reply_text("Unknown command")

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
    await update.message.reply_text("Now send message / image / video")

# ================= RETARGET ONE =================
async def retarget_user(update, context):
    await store_user(update)
    if not is_admin(update.message.from_user.id):
        return

    if not context.args:
        await update.message.reply_text("User ID dao")
        return

    context.user_data["retarget_user"] = int(context.args[0])
    await update.message.reply_text("Target set.\nNow send message / image / video")

# ================= ADMIN MEDIA HANDLER =================
async def admin_media_handler(update, context):
    if not is_admin(update.message.from_user.id):
        return

    if "retarget_user" in context.user_data:
        uid = context.user_data.pop("retarget_user")
        await forward_any(update, context, [uid])
        await update.message.reply_text("[OK] Retarget sent")
        return

    if "retarget_all" in context.user_data:
        context.user_data.pop("retarget_all")
        users = get_users()
        await forward_any(update, context, users)
        await update.message.reply_text("[OK] Broadcast done")

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
init_usage_db()
app = ApplicationBuilder().token(TOKEN).build()

app.post_init = set_bot_menu

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", menu))
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
app.add_handler(CommandHandler("botpanel", botpanel))
app.add_handler(CallbackQueryHandler(start_menu_callback, pattern=r"^startmenu:"))
app.add_handler(CallbackQueryHandler(futuresignal_callback, pattern=r"^futuresignal:"))
app.add_handler(CallbackQueryHandler(botpanel_callback, pattern=r"^botpanel:"))

app.add_handler(MessageHandler(filters.COMMAND, command_router))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, normal_message))
app.add_handler(MessageHandler(
    filters.PHOTO | filters.VIDEO | filters.ATTACHMENT | filters.AUDIO | filters.VOICE,
    user_media_handler
))

print("Bot running...")
app.run_polling()
