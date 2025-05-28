# Cron Job Testing Guide for Vercel

## Overview
This guide helps you test and debug the cron job functionality in your Vercel deployment at https://twitter-autobot.vercel.app/.

## How Vercel Cron Jobs Work
- Vercel makes **HTTP GET requests** to your production deployment URL
- User-Agent header will be `vercel-cron/1.0` for automated triggers
- Timezone is always **UTC**
- Requests go to: `https://twitter-autobot.vercel.app/api/cron/content-generation`

## Fixed Issues
1. **Import Problems**: Cron jobs now have self-contained imports and don't depend on the main Flask app
2. **Path Issues**: Proper path resolution for Vercel serverless environment
3. **Template Rendering**: Cron jobs can now render email templates independently
4. **Error Handling**: Better error reporting and logging
5. **Vercel Integration**: Proper user-agent detection and request handling

## Testing Endpoints

### 1. Health Check
```
GET https://twitter-autobot.vercel.app/api/cron/health
```
This should return:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "service": "twitter-bot-cron",
  "environment": "production"
}
```

### 2. Functionality Test
```
GET https://twitter-autobot.vercel.app/api/cron/test
```
This will test:
- Database connectivity
- AI content generation
- Email service configuration

Expected response:
```json
{
  "success": true,
  "timestamp": "2024-01-01T12:00:00Z",
  "environment": "production",
  "tests": {
    "database": "✅ Database connected - X active users",
    "ai_generation": "✅ AI generation working - Generated: ...",
    "email_service": "✅ Email service configured: true"
  }
}
```

### 3. Manual Cron Trigger
```
GET https://twitter-autobot.vercel.app/api/cron/content-generation
POST https://twitter-autobot.vercel.app/api/cron/content-generation
```
This manually triggers the content generation job.

Expected response:
```json
{
  "success": true,
  "message": "Content generation job completed",
  "timestamp": "2024-01-01T12:00:00Z",
  "triggered_by": "manual"
}
```

## Cron Schedule (IST - Indian Standard Time)
The cron jobs are configured to run at:
- **09:00 AM IST** (03:30 UTC)
- **02:55 PM IST** (09:25 UTC)  
- **06:00 PM IST** (12:30 UTC)
- **08:30 PM IST** (15:00 UTC)

## Environment Variables Required
Make sure these are set in your Vercel dashboard:

### Required for Cron Jobs:
- `DATABASE_URL` or `POSTGRES_URL` (for production database)
- `OPENAI_API_KEY` (for AI content generation)
- `TWITTER_CONSUMER_KEY`
- `TWITTER_CONSUMER_SECRET`
- `FLASK_SECRET_KEY`

### Email Service (if using):
- Email service configuration variables

### Optional:
- `CRON_SECRET` (for additional security on manual triggers)

## Debugging Steps

### Step 1: Test Health
Visit `/api/cron/health` to ensure the cron service is running.

### Step 2: Test Components  
Visit `/api/cron/test` to check each component:
- If database fails: Check `DATABASE_URL` environment variable
- If AI generation fails: Check `OPENAI_API_KEY` environment variable
- If email fails: Check email service configuration

### Step 3: Test Manual Trigger
Use `/api/cron/content-generation` to manually trigger the job and see logs.

### Step 4: Check Vercel Logs
In your Vercel dashboard:
1. Go to your project
2. Click on "Functions" tab
3. Look for logs from `api/cron.py`
4. Check for any error messages
5. Look for "CRON:" prefixed log messages

## Vercel-Specific Features

### User Agent Detection
- Automatic cron jobs: `vercel-cron/1.0`
- Manual triggers: Browser or curl user agent
- Logs will show: `"triggered_by": "vercel-cron"` or `"triggered_by": "manual"`

### Security
- Vercel cron requests are automatically trusted (user-agent verification)
- Manual requests can be secured with `CRON_SECRET` environment variable
- If `CRON_SECRET` is set, include it in manual requests:
  ```
  Authorization: Bearer YOUR_CRON_SECRET
  ```

## Common Issues and Solutions

### Issue: "Module not found" errors
**Solution**: The cron.py now includes all necessary imports and path setup.

### Issue: "Template not found" errors  
**Solution**: Template paths are now properly configured for the serverless environment.

### Issue: Database connection errors
**Solution**: Ensure `DATABASE_URL` is set correctly in Vercel environment variables.

### Issue: Cron jobs not triggering
**Solution**: 
1. Check Vercel cron logs in dashboard
2. Verify the cron schedule in `vercel.json`
3. Ensure the routes are properly configured
4. Check that the endpoint responds to GET requests

### Issue: "Unauthorized" errors
**Solution**: 
- For Vercel cron: Should work automatically (user-agent: vercel-cron/1.0)
- For manual testing: Remove `CRON_SECRET` or include proper Authorization header

## Monitoring
- Check Vercel function logs regularly
- Monitor the `/api/cron/health` endpoint
- Set up alerts for failed cron jobs if needed
- Look for "CRON:" prefixed messages in logs

## Testing Commands (PowerShell)
```powershell
# Health check
Invoke-WebRequest -Uri "https://twitter-autobot.vercel.app/api/cron/health"

# Manual trigger
Invoke-WebRequest -Uri "https://twitter-autobot.vercel.app/api/cron/content-generation"

# Component test (if working)
Invoke-WebRequest -Uri "https://twitter-autobot.vercel.app/api/cron/test"
``` 