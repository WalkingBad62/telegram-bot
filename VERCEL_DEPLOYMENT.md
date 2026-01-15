# Vercel Deployment Guide (FREE Alternative)

## ▲ Vercel - Popular Free Platform

Vercel offers **free hobby tier** with generous limits.

### Free Limits:
- ✅ **100GB bandwidth/month**
- ✅ **100 hours/month**
- ✅ **No credit card for basic use**
- ✅ **Fast deployments**
- ✅ **Global CDN**

---

## 📋 Deployment Steps:

### 1. Create Vercel Account
- Go to: https://vercel.com
- Sign up with GitHub

### 2. Import Project
- Click "Import Project"
- Connect: `WalkingBad62/telegram-bot`

### 3. Configure Build
- **Framework:** Other
- **Root Directory:** `./`
- **Build Command:** `pip install -r requirements.txt`
- **Output Directory:** `./`
- **Install Command:** `pip install -r requirements.txt`

### 4. Environment Variables
- `BOT_TOKEN`: `8243950886:AAHUj2w0WFxarJ_xSG778hZjDcJZujapSVw`
- `BACKEND_URL`: Auto-set

### 5. Deploy
- Click "Deploy"
- Wait for build completion

### 6. Set Webhook
```bash
curl -X POST "https://api.telegram.org/bot8243950886:AAHUj2w0WFxarJ_xSG778hZjDcJZujapSVw/setWebhook?url=https://your-app.vercel.app/webhook"
```

---

## 🎯 Your URL:
- App: `https://your-app.vercel.app`

---

## 💡 Vercel Features:
- **Instant deployments**
- **Preview deployments**
- **Analytics included**
- **Great for APIs**

**Student-friendly!** 🎓