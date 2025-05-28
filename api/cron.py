import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables first
from dotenv import load_dotenv
if not os.environ.get('VERCEL_ENV'):
    dotenv_path = os.path.join(project_root, '.env')
    load_dotenv(dotenv_path=dotenv_path, override=True)

from flask import Flask, jsonify, request
import logging
from datetime import datetime, timezone
import json
import uuid

# Import required modules
try:
    import database as db
    import twitter_service
    import email_service
    from crew import crew
except ImportError as e:
    logging.error(f"Failed to import required modules: {e}")
    raise

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create a simple Flask app for cron endpoints
cron_app = Flask(__name__, 
                 template_folder=os.path.join(project_root, 'templates'),
                 static_folder=os.path.join(project_root, 'static'))

# Configure app for production
cron_app.config['ENV'] = 'production'
cron_app.config['DEBUG'] = False
cron_app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey_fixed_schedule")

def scheduled_content_generation_job():
    """Generate and send content for active users - standalone version for cron"""
    logger.info("CRON: Running scheduled content generation job")
    
    try:
        active_users = db.get_active_users_with_topics()
        logger.info(f"CRON: Found {len(active_users)} active users with topics")

        for user in active_users:
            try:
                topics_raw = user.get('topics')
                topics_list = json.loads(topics_raw) if topics_raw else []
                if not topics_list:
                    continue
                
                logger.info(f"CRON: Generating content for @{user['screen_name']}")
                
                # Generate content
                generated_content = crew.kickoff(user_topics=topics_list)
                
                if generated_content:
                    confirmation_token = str(uuid.uuid4())
                    db.add_generated_content(user['id'], generated_content, 'pending_confirmation', confirmation_token)
                    
                    # Send confirmation email
                    if user.get('email'):
                        # Build URLs manually for cron context
                        base_url = os.environ.get('VERCEL_URL') or os.environ.get('VERCEL_PROJECT_PRODUCTION_URL')
                        if base_url and not base_url.startswith('http'):
                            base_url = f"https://{base_url}"
                        elif not base_url:
                            base_url = "https://twitter-autobot.vercel.app"  # actual live URL
                        
                        confirm_url = f"{base_url}/confirm-tweet/{confirmation_token}"
                        dashboard_url = f"{base_url}/"
                        
                        # Render email template
                        with cron_app.app_context():
                            from flask import render_template
                            email_html = render_template('email_confirmation.html',
                                screen_name=user['screen_name'],
                                generated_content=generated_content,
                                topics_used=', '.join(topics_list),
                                confirm_url=confirm_url,
                                dashboard_url=dashboard_url,
                                current_year=datetime.now(timezone.utc).year
                            )
                        
                        email_service.send_email(
                            recipient_email=user['email'], 
                            subject="🤖 Your AI Content is Ready for Review!",
                            body_html=email_html
                        )
                        logger.info(f"CRON: Confirmation email sent to {user['email']}")
                        
            except Exception as e:
                logger.error(f"CRON: Error processing user @{user.get('screen_name', 'Unknown')}: {e}", exc_info=True)
                
    except Exception as e:
        logger.error(f"CRON: Error in scheduled_content_generation_job: {e}", exc_info=True)
        raise

@cron_app.route('/api/cron/content-generation', methods=['GET', 'POST'])
def trigger_content_generation():
    """
    Vercel Cron Job endpoint for scheduled content generation
    This endpoint is called by Vercel Cron Jobs at scheduled intervals
    Vercel sends GET requests with user-agent: vercel-cron/1.0
    """
    try:
        # Log request details for debugging
        user_agent = request.headers.get('User-Agent', '')
        logger.info(f"CRON: Request received - User-Agent: {user_agent}, Method: {request.method}")
        
        # Verify the request is from Vercel Cron or manual trigger
        auth_header = request.headers.get('Authorization')
        cron_secret = os.environ.get('CRON_SECRET')
        is_vercel_cron = 'vercel-cron' in user_agent.lower()
        
        # Allow requests from:
        # 1. Vercel Cron (has vercel-cron user agent)
        # 2. Manual requests with correct secret (if CRON_SECRET is set)
        # 3. Manual requests without secret (if CRON_SECRET is not set)
        if cron_secret and not is_vercel_cron and auth_header != f"Bearer {cron_secret}":
            logger.warning(f"CRON: Unauthorized request - User-Agent: {user_agent}")
            return jsonify({"error": "Unauthorized"}), 401
        
        if is_vercel_cron:
            logger.info("CRON: Triggered by Vercel Cron Job")
        else:
            logger.info("CRON: Manual trigger")
        
        logger.info("CRON: Starting scheduled content generation")
        
        # Run the content generation job
        scheduled_content_generation_job()
        
        logger.info("CRON: Scheduled content generation completed successfully")
        return jsonify({
            "success": True, 
            "message": "Content generation job completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "triggered_by": "vercel-cron" if is_vercel_cron else "manual"
        })
        
    except Exception as e:
        logger.error(f"CRON: Error in scheduled content generation: {e}", exc_info=True)
        return jsonify({
            "success": False, 
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@cron_app.route('/api/cron/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "twitter-bot-cron",
        "environment": os.environ.get('VERCEL_ENV', 'development')
    })

@cron_app.route('/api/cron/test', methods=['GET'])
@cron_app.route('/test', methods=['GET'])  # Alternative route
def test_cron():
    """Test endpoint to verify cron functionality"""
    try:
        logger.info("CRON TEST: Testing cron functionality")
        
        # Test database connection
        try:
            active_users = db.get_active_users_with_topics()
            db_status = f"✅ Database connected - {len(active_users)} active users"
        except Exception as e:
            db_status = f"❌ Database error: {str(e)}"
        
        # Test crew/AI functionality
        try:
            test_content = crew.kickoff(["AI", "technology"])
            ai_status = f"✅ AI generation working - Generated: {test_content[:50]}..."
        except Exception as e:
            ai_status = f"❌ AI generation error: {str(e)}"
        
        # Test email service
        try:
            # Just test if email service can be imported and configured
            email_configured = hasattr(email_service, 'send_email')
            email_status = f"✅ Email service configured: {email_configured}"
        except Exception as e:
            email_status = f"❌ Email service error: {str(e)}"
        
        return jsonify({
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": os.environ.get('VERCEL_ENV', 'development'),
            "tests": {
                "database": db_status,
                "ai_generation": ai_status,
                "email_service": email_status
            }
        })
        
    except Exception as e:
        logger.error(f"CRON TEST: Error in test endpoint: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@cron_app.route('/', methods=['GET'])
@cron_app.route('/api/cron', methods=['GET'])
def cron_info():
    """Information about available cron endpoints"""
    return jsonify({
        "service": "twitter-bot-cron",
        "available_endpoints": [
            "/api/cron/health - Health check",
            "/api/cron/test - Component testing", 
            "/api/cron/content-generation - Manual trigger"
        ],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

# Export the app for Vercel
app = cron_app

if __name__ == '__main__':
    cron_app.run(debug=True, port=5002) 