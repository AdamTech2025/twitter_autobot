import os
import logging
import uuid
from datetime import datetime, timezone
import json
import re

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
if os.environ.get('VERCEL_ENV'):
    logger.info("Running in Vercel production environment")
else:
    dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    load_dotenv(dotenv_path=dotenv_path, override=True)
    logger.info("Running in development environment, loaded .env file")

# Local imports
try:
    import database as db
    import twitter_service
    import email_service 
    from crew import crew
    logger.info("Successfully imported all local modules")
except ImportError as e:
    logger.error(f"Failed to import local modules: {e}")
    raise

# Initialize Flask app
app = Flask(__name__, template_folder='./templates', static_folder='./static')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey_fixed_schedule")

# App configuration
if os.environ.get('VERCEL_ENV'):
    vercel_url = os.environ.get('VERCEL_URL') or os.environ.get('VERCEL_PROJECT_PRODUCTION_URL')
    app.config['PREFERRED_URL_SCHEME'] = 'https'
else:
    # Remove SERVER_NAME for local development to avoid DNS issues
    app.config['PREFERRED_URL_SCHEME'] = os.environ.get('FLASK_PREFERRED_URL_SCHEME', 'http')

app.config['APPLICATION_ROOT'] = os.environ.get('FLASK_APPLICATION_ROOT', '/')

TWITTER_CALLBACK_URL = os.environ.get("TWITTER_CALLBACK_URL")
if not TWITTER_CALLBACK_URL:
    logger.warning("TWITTER_CALLBACK_URL not set in environment")

# Helper Functions
def get_current_user_from_session():
    user_db_id = session.get("user_db_id")
    return db.get_user_by_id(user_db_id) if user_db_id else None

def parse_datetime(date_str):
    """Parse datetime string with multiple format support"""
    if not isinstance(date_str, str):
        return date_str if isinstance(date_str, datetime) else None
    
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        logger.warning(f"Could not parse date string: {date_str}")
        return None

def process_content_history(raw_history):
    """Process content history with proper datetime parsing"""
    processed = []
    for item in raw_history:
        item_copy = dict(item)
        item_copy['created_at'] = parse_datetime(item_copy.get('created_at'))
        item_copy['posted_at'] = parse_datetime(item_copy.get('posted_at'))
        processed.append(item_copy)
    return processed

# Routes
@app.route('/')
def index():
    logger.info("Serving index page")
    user = get_current_user_from_session()
    
    if user:
        logger.info(f"User found: @{user.get('screen_name')} (ID: {user['id']})")
        topics_raw = user.get('topics')
        topics = json.loads(topics_raw) if topics_raw else []
        content_history = process_content_history(db.get_history_by_user_id(user['id']))
        
        return render_template('index.html',
                             email=user.get('email'),
                             twitter_connected=True,
                             screen_name=user.get('screen_name'),
                             current_topics=topics,
                             tweet_history=content_history)
    else:
        logger.info("No active user in session")
        return render_template('index.html',
                             email=None,
                             twitter_connected=False,
                             screen_name=None,
                             current_topics=[],
                             tweet_history=[])

@app.route('/login/twitter')
def twitter_login():
    """Initiate Twitter OAuth login"""
    logger.info("Initiating Twitter login")
    
    if not TWITTER_CALLBACK_URL:
        flash("Twitter login is not properly configured.", "error")
        return redirect(url_for('index'))

    try:
        result = twitter_service.get_request_token_and_auth_url(TWITTER_CALLBACK_URL)
        
        if not result or 'error' in result:
            error_messages = {
                'service_unavailable': "Twitter is temporarily unavailable. Please try again in a few minutes.",
                'auth_failed': "Twitter authentication failed. Please contact support.",
                'rate_limit': "Too many login attempts. Please wait before trying again.",
                'config': "Twitter login is not properly configured."
            }
            
            if result and 'error' in result:
                message = error_messages.get(result['error'], result.get('message', 'Unknown error'))
                flash_type = 'warning' if result['error'] in ['service_unavailable', 'rate_limit'] else 'error'
                flash(message, flash_type)
            else:
                flash("Could not connect to Twitter. Please try again later.", "error")
            
            return redirect(url_for('index'))
        
        if 'authorization_url' in result:
            session['oauth_request_token'] = result['oauth_token']
            session['oauth_request_token_secret'] = result['oauth_token_secret']
            return redirect(result['authorization_url'])
        
        flash("Could not initiate Twitter login. Please try again.", "error")
        return redirect(url_for('index'))

    except Exception as e:
        logger.error(f"Error during Twitter login: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "error")
        return redirect(url_for('index'))

@app.route('/twitter/callback')
def twitter_callback():
    """Handle Twitter OAuth callback"""
    logger.info("Processing Twitter callback")
    
    if request.args.get('denied'):
        flash("Twitter authorization was cancelled.", "info")
        return redirect(url_for('index'))

    oauth_verifier = request.args.get('oauth_verifier')
    if not oauth_verifier:
        flash("Invalid Twitter callback. Please try again.", "error")
        return redirect(url_for('index'))

    request_token = session.pop('oauth_request_token', None)
    request_token_secret = session.pop('oauth_request_token_secret', None)

    if not request_token or not request_token_secret:
        flash("Session expired. Please try connecting again.", "warning")
        return redirect(url_for('twitter_login'))

    try:
        # Get access token
        access_token_data = twitter_service.get_access_token(
            request_token, request_token_secret, oauth_verifier
        )

        if not access_token_data or 'oauth_token' not in access_token_data:
            flash("Failed to authenticate with Twitter. Please try again.", "error")
            return redirect(url_for('index'))

        # Get user profile
        user_profile = twitter_service.get_me(
            access_token_data['oauth_token'], 
            access_token_data['oauth_token_secret']
        )

        if not user_profile or 'id_str' not in user_profile:
            flash("Could not fetch your Twitter profile. Please try again.", "error")
            return redirect(url_for('index'))

        # Save user
        pending_email = session.pop('pending_email', None)
        user_record = db.create_or_update_user(
            twitter_id=user_profile['id_str'],
            screen_name=user_profile['screen_name'],
            oauth_token=access_token_data['oauth_token'],
            oauth_token_secret=access_token_data['oauth_token_secret'],
            email=pending_email,
            topics=None
        )

        if user_record and user_record.get('id'):
            session["user_db_id"] = user_record['id']
            flash(f"Successfully connected Twitter account: @{user_profile['screen_name']}", "success")
        else:
            flash("Could not save your profile. Please try again.", "error")

        return redirect(url_for('index'))

    except Exception as e:
        logger.error(f"Error processing Twitter callback: {e}", exc_info=True)
        flash("An error occurred during Twitter authentication.", "error")
        return redirect(url_for('index'))

@app.route('/disconnect-twitter')
def disconnect_twitter_route():
    user = get_current_user_from_session()
    if user:
        db.set_user_active_status(user['id'], False)
        flash(f"Twitter account @{user['screen_name']} disconnected.", "info")
        logger.info(f"Disconnected Twitter for user ID {user['id']}")
    else:
        flash("No active user session to disconnect Twitter from.", "warning")
    
    # Clear session
    session.clear()
    return redirect(url_for('index'))

@app.route('/save-schedule', methods=['POST'])
def save_settings_route():
    """Save user email and topic preferences"""
    logger.info("Saving user settings")
    user = get_current_user_from_session()

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400
            
        email = data.get('email', '').strip()
        topics = data.get('topics', [])
        
        # Email validation
        if email and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return jsonify({"success": False, "message": "Please enter a valid email address"}), 400

        messages = []
        
        # Handle email
        if email or email == '':
            if user:
                if db.update_user_email(user['id'], email or None):
                    messages.append("Email updated")
                else:
                    return jsonify({"success": False, "message": "Failed to update email"}), 500
            else:
                session['pending_email'] = email
                messages.append("Email will be saved when you connect Twitter")
        
        # Handle topics
        if topics is not None:
            if user:
                topics_json = json.dumps(topics)
                if db.update_user_topics(user['id'], topics_json):
                    messages.append("Topics updated")
                else:
                    return jsonify({"success": False, "message": "Failed to update topics"}), 500
            elif topics:
                messages.append("Connect Twitter to save topics")

        return jsonify({"success": True, "message": ". ".join(messages) or "No changes made"})
            
    except Exception as e:
        logger.error(f"Error saving settings: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Server error occurred"}), 500

@app.route('/confirm-tweet/<token>')
def confirm_content_route(token):
    """Confirm and post tweet content"""
    logger.info(f"Received content confirmation for token: {token}")
    content_record = db.get_content_by_confirmation_token(token)

    if not content_record:
        flash("Invalid or expired confirmation link.", "error")
        return redirect(url_for('index'))
    
    if content_record['status'] != 'pending_confirmation':
        flash(f"This content has already been {content_record['status']}.", "info")
        return redirect(url_for('index'))
    
    if not content_record.get('user_is_active'):
        flash("Associated Twitter user is not active.", "error")
        db.update_content_status(content_record['id'], 'failed_user_inactive')
        return redirect(url_for('index'))

    try:
        success, post_data = twitter_service.post_tweet(
            tweet_content=content_record['generated_content'],
            user_oauth_token=content_record['oauth_token'],
            user_oauth_token_secret=content_record['oauth_token_secret']
        )
        
        if success:
            db.update_content_status(content_record['id'], 'posted', datetime.now(timezone.utc))
            flash("Content posted to Twitter!", "success")
            
            # Send success email
            if content_record.get('user_email'):
                email_html = render_template('email_posted.html',
                    screen_name=content_record['screen_name'],
                    tweet_content=content_record['generated_content'],
                    dashboard_url=url_for('index', _external=True),
                    current_year=datetime.now(timezone.utc).year
                )
                
                email_service.send_email(
                    recipient_email=content_record['user_email'],
                    subject="Your AI Tweet Has Been Posted! 🎉",
                    body_html=email_html
                )
        else:
            db.update_content_status(content_record['id'], 'failed_to_post')
            error_msg = str(post_data)
            
            if "403 Forbidden" in error_msg or "You are not permitted to perform this action" in error_msg:
                flash(f"Failed to post: {error_msg}. Check your Twitter App permissions in the Developer Portal.", "error")
            else:
                flash(f"Failed to post content: {error_msg}", "error")
                
    except Exception as e:
        logger.error(f"Error posting content ID {content_record['id']}: {e}", exc_info=True)
        db.update_content_status(content_record['id'], 'failed_to_post')
        flash(f"Failed to post: {e}", "error")
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    logger.info("Starting Flask app in development mode")
    app.run(debug=True, host='127.0.0.1', port=5001)  # Fixed getaddrinfo error
