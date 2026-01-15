# 🚀 Totem Bot - Render Deployment Guide

## 📋 Prerequisites
- Render account (free): https://render.com
- Telegram Bot Token from @BotFather

## 🔧 Step-by-Step Deployment

### Step 1: Prepare Your Code
✅ Code is ready! Modified for Render deployment.

### Step 2: Create Render Account
1. Go to https://render.com
2. Sign up with GitHub/Google
3. Verify your email

### Step 3: Connect Your Repository
1. Click "New" → "Blueprint"
2. Connect your GitHub repository
3. Select the `render.yaml` file

### Step 4: Deploy Backend First
1. Render will create two services automatically
2. **totem-backend** will deploy first
3. Wait for it to build and deploy (5-10 minutes)
4. Copy the backend URL (e.g., `https://totem-backend.onrender.com`)

### Step 5: Deploy Bot
1. **totem-bot** will deploy after backend
2. Set environment variables:
   - `BOT_TOKEN`: Your bot token from @BotFather
   - `BACKEND_URL`: Will auto-populate from backend service

### Step 6: Set Webhook URL
After bot deploys, set the webhook:
```
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://totem-bot.onrender.com/webhook"
```

Replace `<YOUR_BOT_TOKEN>` with your actual token.

## 🔍 Testing Your Deployment

### Check Backend
Visit: `https://totem-backend.onrender.com/users`

### Check Bot
Send `/start` to your bot on Telegram

### View Logs
- Go to Render dashboard
- Click on your service
- View "Logs" tab

## 💡 Important Notes

### Free Tier Limitations
- Services sleep after 15 minutes of inactivity
- Wake up on new requests (may take 10-30 seconds)
- 750 hours/month free

### Database
- SQLite database persists in container
- Data survives restarts but not re-deploys
- For production, consider PostgreSQL upgrade

### Environment Variables
- `BOT_TOKEN`: Keep secret, never commit to code
- `BACKEND_URL`: Auto-set by Render

## 🛠 Troubleshooting

### Bot Not Responding
1. Check webhook is set: `https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
2. View Render logs for errors
3. Ensure BACKEND_URL is correct

### Backend Issues
1. Check `/` endpoint returns JSON
2. View database: Access via `/users` endpoint

### Webhook Setup
```bash
# Set webhook
curl -X POST "https://api.telegram.org/botYOUR_TOKEN/setWebhook?url=https://your-bot-url.onrender.com/webhook"

# Check webhook status
curl "https://api.telegram.org/botYOUR_TOKEN/getWebhookInfo"

# Remove webhook (for local testing)
curl -X POST "https://api.telegram.org/botYOUR_TOKEN/deleteWebhook"
```

## 🎯 Your Services URLs
- Backend: `https://totem-backend.onrender.com`
- Bot Webhook: `https://totem-bot.onrender.com/webhook`

## 📞 Support
- Render Docs: https://docs.render.com
- Telegram Bot API: https://core.telegram.org/bots/api

---
✅ **Ready to deploy! Follow the steps above.**