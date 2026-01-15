# Railway Deployment Guide (FREE Alternative)

## 🚂 Railway - Best Free Alternative to Render

Railway offers **$5/month free credits** (about 512MB RAM, 1GB disk) - no credit card required!

### Features:
- ✅ **No credit card needed**
- ✅ **512MB RAM free**
- ✅ **PostgreSQL database** (better than SQLite)
- ✅ **Auto-deploy from GitHub**
- ✅ **Custom domains free**

---

## 📋 Deployment Steps:

### 1. Create Railway Account
- Go to: https://railway.app
- Sign up with GitHub (free)

### 2. Create Project
- Click "New Project"
- Choose "Deploy from GitHub repo"
- Connect: `WalkingBad62/telegram-bot`

### 3. Configure Services

#### Backend Service:
- **Name:** totem-backend
- **Source:** GitHub repo
- **Root Directory:** `/` (leave blank)
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python main.py`

#### Bot Service:
- **Name:** totem-bot
- **Source:** GitHub repo
- **Root Directory:** `/`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python bot_webhook.py`

### 4. Environment Variables
For **totem-bot** service:
- `BOT_TOKEN`: `8243950886:AAHUj2w0WFxarJ_xSG778hZjDcJZujapSVw`
- `BACKEND_URL`: Will be set automatically

### 5. Database (Optional)
- Add PostgreSQL database
- Update code to use `DATABASE_URL` env var

### 6. Set Webhook
After deployment, run:
```bash
curl -X POST "https://api.telegram.org/bot8243950886:AAHUj2w0WFxarJ_xSG778hZjDcJZujapSVw/setWebhook?url=https://totem-bot.railway.app/webhook"
```

---

## 🎯 Your URLs:
- Backend: `https://totem-backend.railway.app`
- Bot: `https://totem-bot.railway.app`

---

## 💡 Pro Tips:
- Railway auto-deploys on GitHub push
- Monitor usage in dashboard
- Upgrade anytime with credit card

**Perfect for students!** 🎓