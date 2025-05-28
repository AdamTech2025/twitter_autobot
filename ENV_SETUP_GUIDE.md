# Environment Variables Setup for Vercel

## 🔧 **Required Environment Variables for Vercel Dashboard**

Copy these **exact** environment variables to your Vercel project settings:

### **Twitter API Configuration**
```
TWITTER_API_KEY=pkR7YliRuFVA0krkgw3MkadgA
TWITTER_API_SECRET_KEY=Gw36n77pA0Kt1GI6mIQtnpF4Mk4s1hi8kDnVbwHJLyMYqZXv7x
TWITTER_CALLBACK_URL=https://twitter-autobot.vercel.app/twitter/callback
```

### **Flask Configuration**
```
FLASK_SECRET_KEY=supersecretkey_twitter_bot_2024
FLASK_ENV=production
VERCEL_ENV=production
```

### **AI/Content Generation**
```
GOOGLE_API_KEY=AIzaSyAgjfO_O_b-L1VwvQ5fsdOIfU8EzCdDO2Q
```

### **Email Service**
```
EMAIL_SENDER_ADDRESS=techtitanadamtechnologies@gmail.com
EMAIL_SENDER_PASSWORD=gzqx hcbs fyuq shqu
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

### **Database (Neon PostgreSQL)**
```
DATABASE_URL=postgres://neondb_owner:npg_17dMhjwAlsnI@ep-twilight-term-a4tdliz0-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require
POSTGRES_URL=postgresql://neondb_owner:npg_17dMhjwAlsnI@ep-twilight-term-a4tdliz0-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require
```

## 🔄 **Key Changes Made:**

### 1. **Twitter Callback URL Fixed**
- **Before**: `http://localhost:5001/twitter/callback`
- **After**: `https://twitter-autobot.vercel.app/twitter/callback`

### 2. **AI Service Updated**
- **Now Using**: Google Gemini API (you have the key)
- **Fallback**: OpenAI (if you add `OPENAI_API_KEY` later)

### 3. **Production Environment**
- Added `VERCEL_ENV=production`
- Set `FLASK_ENV=production`

## 📋 **How to Set These in Vercel:**

1. Go to your Vercel Dashboard
2. Select your `twitter-autobot` project
3. Go to **Settings** → **Environment Variables**
4. Add each variable above with its exact value
5. Make sure to select **Production** environment
6. Click **Save**

## 🧪 **Testing After Setup:**

After setting these environment variables, test your cron functionality:

```powershell
# Test health
Invoke-WebRequest -Uri "https://twitter-autobot.vercel.app/api/cron/health"

# Test manual trigger
Invoke-WebRequest -Uri "https://twitter-autobot.vercel.app/api/cron/content-generation" -Method POST
```

## ⚠️ **Important Notes:**

1. **Twitter Callback URL**: Must match exactly in both:
   - Vercel environment variables
   - Twitter Developer Portal app settings

2. **Database**: Using Neon PostgreSQL (production-ready)

3. **AI Service**: Using Google Gemini (free tier available)

4. **Email**: Using Gmail SMTP (app password required)

## 🔐 **Security Recommendations:**

1. **Rotate API Keys**: Regularly rotate your Twitter and Google API keys
2. **App Passwords**: Use Gmail app passwords, not your main password
3. **Environment Only**: Never commit these values to your code repository

## 🚀 **Deployment:**

After setting these environment variables:
1. Push your latest code changes
2. Vercel will automatically redeploy
3. Cron jobs will start working at scheduled times:
   - **09:00 AM IST** (03:30 UTC)
   - **03:00 PM IST** (09:30 UTC)  
   - **06:00 PM IST** (12:30 UTC)
   - **08:30 PM IST** (15:00 UTC) 