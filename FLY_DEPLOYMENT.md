# Fly.io Deployment Guide (FREE Alternative)

## 🛩️ Fly.io - Another Great Free Option

Fly.io gives **free tier with 3 shared CPUs, 256MB RAM** - no credit card!

### Free Limits:
- ✅ **256MB RAM**
- ✅ **3 shared CPUs**
- ✅ **No credit card required**
- ✅ **Global CDN**
- ✅ **PostgreSQL available**

---

## 📋 Quick Deployment:

### 1. Install Fly CLI
```bash
# Windows (PowerShell as Admin)
iwr https://fly.io/install.ps1 -useb | iex
```

### 2. Login & Create App
```bash
fly auth login
fly launch  # Creates fly.toml automatically
```

### 3. Deploy
```bash
fly deploy
```

### 4. Set Environment
```bash
fly secrets set BOT_TOKEN="8243950886:AAHUj2w0WFxarJ_xSG778hZjDcJZujapSVw"
```

### 5. Set Webhook
```bash
curl -X POST "https://api.telegram.org/bot8243950886:AAHUj2w0WFxarJ_xSG778hZjDcJZujapSVw/setWebhook?url=https://your-app.fly.dev/webhook"
```

---

## 🎯 Your URL:
- App: `https://your-app-name.fly.dev`

---

## 💡 Why Fly.io?
- **True free tier** (no card needed)
- **Fast deployments**
- **Global performance**
- **Great for bots**

**Also perfect for students!** 📚