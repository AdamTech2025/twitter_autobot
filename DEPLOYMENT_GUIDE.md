# Vercel Deployment Guide for Twitter Bot

This guide will help you deploy your Twitter bot application to Vercel.

## Prerequisites

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **GitHub Repository**: Your code should be in a GitHub repository
3. **Twitter Developer Account**: Get API keys from [developer.twitter.com](https://developer.twitter.com)
4. **Email Account**: For sending notifications (Gmail recommended)

## Step 1: Prepare Your Environment Variables

You'll need to set these environment variables in Vercel:

### Required Environment Variables

#### Twitter API (Required)
```
TWITTER_API_KEY=your_twitter_api_key
TWITTER_API_SECRET_KEY=your_twitter_api_secret_key
TWITTER_CALLBACK_URL=https://your-app-name.vercel.app/twitter/callback
```

#### Database (Vercel will provide)
```
POSTGRES_URL=postgresql://username:password@host:port/database
```

#### Flask Configuration
```
FLASK_SECRET_KEY=your_super_secret_key_here
VERCEL_ENV=production
```

#### Email Service (Required for notifications)
```
EMAIL_SENDER_ADDRESS=your-email@gmail.com
EMAIL_SENDER_PASSWORD=your-app-password
```

#### AI Content Generation (Optional but recommended)
```
OPENAI_API_KEY=your_openai_api_key
```

#### Optional Security
```
CRON_SECRET=your_cron_secret_key
```

## Step 2: Set Up Twitter Developer App

1. Go to [developer.twitter.com](https://developer.twitter.com)
2. Create a new app or use existing one
3. Set app permissions to "Read and Write"
4. Add callback URL: `https://your-app-name.vercel.app/twitter/callback`
5. Get your API Key and API Secret Key

## Step 3: Set Up Email Service (Gmail)

1. Enable 2-factor authentication on your Gmail account
2. Generate an App Password:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate password for "Mail"
3. Use your Gmail address and the app password

## Step 4: Deploy to Vercel

### Option A: Deploy via Vercel Dashboard

1. Go to [vercel.com/dashboard](https://vercel.com/dashboard)
2. Click "New Project"
3. Import your GitHub repository
4. Vercel will auto-detect it as a Python project
5. Configure environment variables (see Step 5)
6. Click "Deploy"

### Option B: Deploy via Vercel CLI

1. Install Vercel CLI:
   ```bash
   npm i -g vercel
   ```

2. Login to Vercel:
   ```bash
   vercel login
   ```

3. Deploy from your project directory:
   ```bash
   vercel
   ```

4. Follow the prompts and set up environment variables

## Step 5: Configure Environment Variables in Vercel

1. Go to your project dashboard on Vercel
2. Click "Settings" → "Environment Variables"
3. Add all the environment variables listed in Step 1
4. Make sure to set them for "Production" environment

### Important Notes:
- **TWITTER_CALLBACK_URL**: Must match exactly what you set in Twitter Developer Console
- **POSTGRES_URL**: Vercel will provide this when you add a PostgreSQL database
- **EMAIL_SENDER_PASSWORD**: Use App Password, not your regular Gmail password

## Step 6: Add PostgreSQL Database

1. In your Vercel project dashboard
2. Go to "Storage" tab
3. Click "Create Database" → "PostgreSQL"
4. Follow the setup process
5. Vercel will automatically add `POSTGRES_URL` to your environment variables

## Step 7: Initialize Database

After deployment, initialize your database:

1. Visit: `https://your-app-name.vercel.app/api/init-db`
2. This will create the necessary database tables

## Step 8: Test Your Deployment

1. Visit your app: `https://your-app-name.vercel.app`
2. Try connecting your Twitter account
3. Add some topics and email
4. Check if the cron job is working (runs daily at 2 PM UTC)

## Troubleshooting

### Common Issues:

1. **Twitter OAuth Errors**:
   - Check callback URL matches exactly
   - Ensure app has "Read and Write" permissions
   - Verify API keys are correct

2. **Email Not Sending**:
   - Use App Password, not regular password
   - Enable 2-factor authentication first
   - Check EMAIL_SENDER_ADDRESS format

3. **Database Errors**:
   - Ensure PostgreSQL database is created
   - Check POSTGRES_URL is set correctly
   - Run `/api/init-db` to initialize tables

4. **Cron Job Not Running**:
   - Check CRON_SECRET is set (optional but recommended)
   - Verify cron schedule in vercel.json
   - Check function logs in Vercel dashboard

### Checking Logs:

1. Go to Vercel dashboard
2. Select your project
3. Click "Functions" tab
4. View logs for each function

## Environment Variables Summary

Copy this template and fill in your values:

```env
# Twitter API
TWITTER_API_KEY=
TWITTER_API_SECRET_KEY=
TWITTER_CALLBACK_URL=https://your-app-name.vercel.app/twitter/callback

# Flask
FLASK_SECRET_KEY=
VERCEL_ENV=production

# Email
EMAIL_SENDER_ADDRESS=
EMAIL_SENDER_PASSWORD=

# Database (Vercel provides)
POSTGRES_URL=

# Optional
CRON_SECRET=
```

## Post-Deployment

1. **Test all functionality**:
   - Twitter login/logout
   - Email notifications
   - Content generation (manual trigger)

2. **Monitor the application**:
   - Check Vercel function logs
   - Monitor database usage
   - Watch for any errors

3. **Set up monitoring** (optional):
   - Use Vercel Analytics
   - Set up error tracking
   - Monitor function execution times

## Support

If you encounter issues:
1. Check Vercel function logs
2. Verify all environment variables are set
3. Test Twitter API credentials separately
4. Check email service configuration

Your Twitter bot should now be live and running on Vercel! 🚀 