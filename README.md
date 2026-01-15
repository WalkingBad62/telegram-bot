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
