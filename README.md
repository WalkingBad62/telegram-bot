# 🐍 Totem Bot - Telegram Income Automation

My first Python project. A Telegram bot for automated income management with 24/7 cloud hosting.

## 🚀 Features
- 🤖 Automated responses
- 💾 User data storage
- 📊 User management
- 🔄 Broadcast messaging
- ☁️ 24/7 Render hosting

## 🛠 Tech Stack
- **Backend**: FastAPI + SQLite
- **Bot**: Python Telegram Bot
- **Hosting**: Render (Free)
- **Language**: Python 3.9+

## 📦 Installation (Local Development)

```bash
# Clone repository
git clone <your-repo-url>
cd totem-bot

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your BOT_TOKEN

# Run locally
python main.py  # Backend on port 8000
python bot.py   # Bot with polling
```

## Run 2 Bots From Same Folder

Use two backend processes and two bot processes with different env values.
Set `.env` like this first:

```env
BOT_TOKEN_CURRENCY="your_currency_bot_token"
BOT_TOKEN_TRADING="your_trading_bot_token"
```

Quick launcher scripts:

```powershell
.\start_two_bots.ps1
.\status_two_bots.ps1
.\stop_two_bots.ps1
```

### 1) Currency backend + bot

```powershell
# Terminal A (backend)
$env:BOT_MODE="currency"
$env:DATABASE_URL="bot_currency.db"
python -m uvicorn backend:app --host 0.0.0.0 --port 8000

# Terminal B (bot)
$env:BOT_MODE="currency"
$env:BACKEND_URL="http://127.0.0.1:8000"
python bot.py
```

### 2) Trading backend + bot

```powershell
# Terminal C (backend)
$env:BOT_MODE="trading"
$env:DATABASE_URL="bot_trading.db"
$env:TRADING_API_URL="https://yoofirmtrading.xyz/api/analyze-screenshot"
$env:TRADING_API_KEY="YOUR_TRADING_API_KEY"
python -m uvicorn backend:app --host 0.0.0.0 --port 8002

# Terminal D (bot)
$env:BOT_MODE="trading"
$env:BACKEND_URL="http://127.0.0.1:8002"
python bot.py
```

## 🌐 Deployment to Render (24/7 Free)

### Quick Deploy
1. **Fork** this repository
2. **Connect** to Render: https://render.com
3. **Deploy** using `render.yaml`
4. **Set webhook** for bot

### Detailed Guide
See [DEPLOYMENT_README.md](DEPLOYMENT_README.md) for step-by-step instructions.

## 📊 API Endpoints

- `GET /users` - View all stored users
- `POST /user/store` - Store user data
- `POST /reply/get` - Get bot reply
- `GET /retarget/users` - Get inactive users

## 🤖 Bot Commands

- `/start` - Welcome message
- `/broadcast` - Send messages to all users

## 📈 Usage Stats
- Users stored in SQLite database
- 24/7 availability on Render
- Automatic user data collection

---
Made with ❤️ by Baba Asraf
