# Twitter Bot Deployment Guide for Vercel with Persistent Database & Cron Jobs

## Prerequisites

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **Vercel CLI**: Install with `npm install -g vercel`
3. **Twitter App**: Your Twitter API keys and callback URL configured

## Step 1: Setup Vercel Postgres Database

### Create Vercel Postgres Database:
1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click **Storage** → **Create Database**
3. Select **Postgres** 
4. Choose database name: `twitter-bot-db`
5. Select region (choose closest to your users)
6. Click **Create**

### Get Database Connection URL:
1. In your new database dashboard
2. Go to **Settings** tab
3. Copy the **POSTGRES_URL** value
4. Save it for the environment variables step

## Step 2: Update Twitter App Settings

1. Go to [Twitter Developer Portal](https://developer.twitter.com/en/portal/dashboard)
2. Select your Twitter App
3. Go to **App Settings** → **Authentication settings**
4. Update **Callback URL** to: `https://your-app-name.vercel.app/twitter/callback`
   - Replace `your-app-name` with your actual Vercel project name

## Step 3: Deploy to Vercel

### Option A: Deploy via Vercel CLI
```bash
# Install Vercel CLI (if not installed)
npm install -g vercel

# Login to Vercel
vercel login

# Deploy the project
vercel

# Follow the prompts:
# - Project name: your-twitter-bot
# - Framework: Other
# - Directory: current directory
```

### Option B: Deploy via GitHub
1. Push your code to GitHub
2. Connect your GitHub repo to Vercel
3. Import the project in Vercel Dashboard

## Step 4: Configure Environment Variables

In Vercel Dashboard → Your Project → Settings → Environment Variables, add:

### Required Variables:
```
TWITTER_API_KEY = pkR7YliRuFVA0krkgw3MkadgA
TWITTER_API_SECRET_KEY = Gw36n77pA0Kt1GI6mIQtnpF4Mk4s1hi8kDnVbwHJLyMYqZXv7x
TWITTER_CALLBACK_URL = https://your-app-name.vercel.app/twitter/callback
FLASK_SECRET_KEY = supersecretkey_production_minimum_32_chars
LITELLM_PROVIDER = gemini
GEMINI_API_KEY = your_gemini_api_key_here
POSTGRES_URL = your_postgres_connection_url_from_step_1
```

### Optional Variables:
```
EMAIL_SENDER = your-email@gmail.com
EMAIL_PASSWORD = your-gmail-app-password
EMAIL_SMTP_SERVER = smtp.gmail.com
EMAIL_SMTP_PORT = 587
CRON_SECRET = your_random_secret_for_cron_security
```

## Step 5: Initialize Database Schema

After deployment, initialize your PostgreSQL database:

1. **POST Request to initialize**:
   ```bash
   curl -X POST https://your-app-name.vercel.app/api/init-db
   ```

2. **Check database status**:
   ```bash
   curl https://your-app-name.vercel.app/api/init-db
   ```

3. **Expected response**:
   ```json
   {
     "database_connected": true,
     "database_type": "PostgreSQL",
     "tables_exist": true,
     "expected_tables": ["users", "ai_generated_content_history"]
   }
   ```

## Step 6: Test Your Deployment

1. Visit your Vercel URL: `https://your-app-name.vercel.app`
2. Click "Connect Twitter"
3. Complete OAuth flow
4. Test email and topics functionality
5. Verify data persists after redeployments

## Step 7: Verify Cron Jobs

### Automatic Scheduling:
- **Content generation runs daily at 12:30 UTC (6:00 PM IST)**
- Vercel automatically triggers the cron job
- No manual setup required

### Configure IST Timing:
**⚠️ Important**: Vercel Cron Jobs run in **UTC timezone**. To set IST time, convert to UTC first.

**IST = UTC + 5:30 hours**

| **Desired IST Time** | **UTC Time** | **Cron Schedule** |
|---------------------|--------------|-------------------|
| 6:00 AM IST | 12:30 AM UTC | `"30 0 * * *"` |
| 9:00 AM IST | 3:30 AM UTC | `"30 3 * * *"` |
| 12:00 PM IST | 6:30 AM UTC | `"30 6 * * *"` |
| 3:00 PM IST | 9:30 AM UTC | `"30 9 * * *"` |
| 6:00 PM IST | 12:30 PM UTC | `"30 12 * * *"` |
| 9:00 PM IST | 3:30 PM UTC | `"30 15 * * *"` |

**To change the time**: Edit `vercel.json` → `crons` → `schedule`

### Manual Testing:
```bash
# Test cron endpoint manually
curl -X POST https://your-app-name.vercel.app/api/cron/content-generation
```

### Monitor Cron Jobs:
1. Go to Vercel Dashboard → Your Project
2. Click **Functions** tab
3. Check logs for cron job executions

## Features Overview

### ✅ **Persistent Database (PostgreSQL)**
- **Data persists** between deployments
- **Automatic scaling** with Vercel Postgres
- **Backup and recovery** handled by Vercel

### ✅ **Automated Scheduling**
- **Daily content generation** at 4:27 PM UTC
- **Serverless cron jobs** via Vercel
- **Error handling and logging**

### ✅ **Production Ready**
- **Environment detection** (dev vs production)
- **Database abstraction** (SQLite dev, PostgreSQL prod)
- **Error monitoring** and health checks

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Main application dashboard |
| `/api/init-db` | POST | Initialize database schema |
| `/api/init-db` | GET | Check database status |
| `/api/cron/content-generation` | POST | Trigger content generation |
| `/api/cron/health` | GET | Health check for cron service |

## Troubleshooting

### Database Issues:
1. **Connection errors**: Check `POSTGRES_URL` in environment variables
2. **Table missing**: Run `POST /api/init-db` to initialize schema
3. **Data not persisting**: Ensure using PostgreSQL, not SQLite

### Cron Job Issues:
1. **Not running**: Check Vercel Dashboard → Functions tab for logs
2. **Timing**: Cron runs at 16:27 UTC daily (adjust in `vercel.json`)
3. **Errors**: Check function logs for detailed error messages

### OAuth Issues:
1. **503 Errors**: Check environment variables are set correctly
2. **Callback failures**: Verify Twitter callback URL matches exactly
3. **Token errors**: Ensure API keys are valid and have proper permissions

## Monitoring & Maintenance

### Database Monitoring:
- Check database status: `GET /api/init-db`
- Monitor storage usage in Vercel Dashboard
- Set up alerts for connection failures

### Cron Job Monitoring:
- Check function logs in Vercel Dashboard
- Monitor email delivery rates
- Track content generation success rates

### Performance:
- Monitor function execution times
- Check database query performance
- Scale Postgres if needed

## Cost Optimization

### Vercel Postgres Pricing:
- **Free tier**: 256MB storage, 1 million queries/month
- **Pro tier**: Scales with usage
- **Monitor usage** in Vercel Dashboard

### Function Limits:
- **Execution time**: 60 seconds max for cron jobs
- **Memory**: 1024MB default
- **Concurrent executions**: Based on plan

Your Twitter bot now has:
- ✅ **Persistent PostgreSQL database**
- ✅ **Automated daily content generation**
- ✅ **Production-ready infrastructure**
- ✅ **Monitoring and health checks** 