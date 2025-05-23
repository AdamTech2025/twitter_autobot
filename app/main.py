import os
import logging
import uuid
from datetime import datetime, timezone
import json
import re

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
# We will not use flask_dance for Twitter OAuth anymore
# from flask_dance.contrib.twitter import make_twitter_blueprint, twitter as twitter_bp
from apscheduler.schedulers.background import BackgroundScheduler # Keep for later
from dotenv import load_dotenv

# Configure logging first, before using logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from the root directory
# In production (Vercel), environment variables are injected directly
# In development, load from .env file
if os.environ.get('VERCEL_ENV'):
    # Production environment - variables are already loaded
    logger.info("Running in Vercel production environment")
else:
    # Development environment - load from .env file
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(dotenv_path=dotenv_path, override=True)  # Force override system env vars
    logger.info("Running in development environment, loaded .env file")

# Local imports
try:
    from . import database as db
    # Assuming twitter_service will provide functions for manual OAuth
    from .services import twitter_service, email_service 
    from .crew import crew
except ImportError as e:
    logging.error(f"Failed to import local modules. Error: {e}. Ensure they are in the correct path and all dependencies are installed.")
    # Fallback for cases where the above might fail in certain execution contexts (though less likely with flask run)
    # Ensure these are also relative if the script is run as part of the package
    from . import database as db
    from .services import twitter_service, email_service
    from .crew import crew

# Initialize Flask app
app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey_fixed_schedule")

# Configuration for url_for with _external=True outside of request context
# Handle both development and production environments
if os.environ.get('VERCEL_ENV'):
    # Production on Vercel
    vercel_url = os.environ.get('VERCEL_URL') or os.environ.get('VERCEL_PROJECT_PRODUCTION_URL')
    if vercel_url:
        app.config['SERVER_NAME'] = vercel_url
        app.config['PREFERRED_URL_SCHEME'] = 'https'
    else:
        # Fallback - don't set SERVER_NAME, let Flask handle it dynamically
        app.config['PREFERRED_URL_SCHEME'] = 'https'
else:
    # Development environment
    app.config['SERVER_NAME'] = os.environ.get('FLASK_SERVER_NAME', 'localhost:5001')
    app.config['PREFERRED_URL_SCHEME'] = os.environ.get('FLASK_PREFERRED_URL_SCHEME', 'http')

app.config['APPLICATION_ROOT'] = os.environ.get('FLASK_APPLICATION_ROOT', '/')

# Ensure TWITTER_CALLBACK_URL is set in your .env or environment
# Example: TWITTER_CALLBACK_URL=http://localhost:5001/twitter/callback
TWITTER_CALLBACK_URL = os.environ.get("TWITTER_CALLBACK_URL")
if not TWITTER_CALLBACK_URL:
    logger.warning("TWITTER_CALLBACK_URL not set in environment. OAuth callback might fail.")
    # Fallback for local development, ensure your Twitter app callback is set to this

# db.init_db() # Commented out to prevent DB wipe on each restart. Run app/database.py manually if reset is needed.
scheduler = BackgroundScheduler()

# --- Helper Functions ---
def get_current_user_from_session():
    user_db_id = session.get("user_db_id")
    if user_db_id:
        return db.get_user_by_id(user_db_id)
    return None

# --- Routes ---
@app.route('/')
def index():
    logger.info("Serving index page.")
    user = get_current_user_from_session()
    email_display = None
    twitter_connected_status = False
    screen_name_display = None
    topics_display_str = ""
    content_history_display = []
    
    if user:
        logger.info(f"User found: ID {user['id']}, Twitter ID {user['twitter_id']}, Email: {user.get('email')}")
        email_display = user.get('email')
        # 'is_active' in DB now represents if they are generally active,
        # actual connection status is determined by having a session.
        twitter_connected_status = True 
        screen_name_display = user.get('screen_name')
        if user.get('topics'):
            try:
                topics_list = json.loads(user['topics'])
                topics_display_str = ", ".join(topics_list) # For display in a simplified way
            except json.JSONDecodeError:
                logger.error(f"Error decoding topics JSON for user ID {user['id']}. Topics: {user['topics']}")
                topics_display_str = user['topics'] # Show raw if not parsable
        
        raw_content_history = db.get_history_by_user_id(user['id'])
        processed_content_history = []
        for item_data in raw_content_history:
            item_copy = dict(item_data) # Ensure mutable copy
            created_at_val = item_copy.get('created_at')

            if isinstance(created_at_val, str):
                parsed_dt = None
                # Attempt to parse common datetime string formats
                for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
                    try:
                        parsed_dt = datetime.strptime(created_at_val, fmt)
                        break
                    except ValueError:
                        continue
                
                if parsed_dt:
                    item_copy['created_at'] = parsed_dt
                else:
                    # Fallback to fromisoformat for other ISO 8601 compliant strings
                    try:
                        item_copy['created_at'] = datetime.fromisoformat(created_at_val)
                    except ValueError:
                        logger.warning(f"Could not parse date string '{created_at_val}' for history item ID {item_copy.get('id')}. Setting to None.")
                        item_copy['created_at'] = None # Ensure template handles None correctly
            elif not isinstance(created_at_val, datetime) and created_at_val is not None:
                logger.warning(f"Unexpected type for 'created_at' ({type(created_at_val)}) for history item ID {item_copy.get('id')}. Setting to None.")
                item_copy['created_at'] = None

            # Process 'posted_at'
            posted_at_val = item_copy.get('posted_at')
            if isinstance(posted_at_val, str):
                parsed_dt_posted = None
                for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
                    try:
                        parsed_dt_posted = datetime.strptime(posted_at_val, fmt)
                        break
                    except ValueError:
                        continue
                
                if parsed_dt_posted:
                    item_copy['posted_at'] = parsed_dt_posted
                else:
                    try:
                        item_copy['posted_at'] = datetime.fromisoformat(posted_at_val)
                    except ValueError:
                        logger.warning(f"Could not parse date string '{posted_at_val}' for 'posted_at' of history item ID {item_copy.get('id')}. Setting to None.")
                        item_copy['posted_at'] = None
            elif not isinstance(posted_at_val, datetime) and posted_at_val is not None:
                logger.warning(f"Unexpected type for 'posted_at' ({type(posted_at_val)}) for history item ID {item_copy.get('id')}. Setting to None.")
                item_copy['posted_at'] = None
            
            processed_content_history.append(item_copy)
        content_history_display = processed_content_history
    else:
        logger.info("No active user in session.")
        
    return render_template('index.html',
                           email=email_display,
                           twitter_connected=twitter_connected_status,
                           screen_name=screen_name_display,
                           # 'schedules' var previously held times+topics, now we only have topics for the UI directly
                           # The JS will load topics from a data structure if needed, or we pass them here.
                           # For simplicity, index.html will now directly use user.topics for display in JS part
                           current_topics=json.loads(user['topics']) if user and user.get('topics') else [],
                           tweet_history=content_history_display)

@app.route('/login/twitter')
def twitter_login():
    """Initiate Twitter OAuth login"""
    logger.info("Initiating Twitter login.")
    
    if not TWITTER_CALLBACK_URL:
        flash("Twitter login is not properly configured.", "error")
        return redirect(url_for('index'))

    try:
        result = twitter_service.get_request_token_and_auth_url(TWITTER_CALLBACK_URL)
        logger.info(f"Twitter service result: {result}")  # Debug logging
        
        if not result:
            flash("Could not connect to Twitter. Please try again later.", "error")
            return redirect(url_for('index'))
        
        # Handle error responses
        if 'error' in result:
            logger.info(f"Twitter error detected: {result['error']}")  # Debug logging
            error_messages = {
                'service_unavailable': "Twitter is temporarily unavailable. Please try again in a few minutes.",
                'auth_failed': "Twitter authentication failed. Please contact support.",
                'rate_limit': "Too many login attempts. Please wait before trying again.",
                'config': "Twitter login is not properly configured."
            }
            message = error_messages.get(result['error'], result.get('message', 'Unknown error'))
            logger.info(f"Flashing message: {message}")  # Debug logging
            flash(message, 'warning' if result['error'] in ['service_unavailable', 'rate_limit'] else 'error')
            return redirect(url_for('index'))
        
        # Success - store tokens and redirect
        if 'authorization_url' in result:
            session['oauth_request_token'] = result['oauth_token']
            session['oauth_request_token_secret'] = result['oauth_token_secret']
            logger.info("Redirecting to Twitter for authorization")
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
    
    # Check for user denial
    if request.args.get('denied'):
        flash("Twitter authorization was cancelled.", "info")
        return redirect(url_for('index'))

    oauth_verifier = request.args.get('oauth_verifier')
    if not oauth_verifier:
        flash("Invalid Twitter callback. Please try again.", "error")
        return redirect(url_for('index'))

    # Get stored tokens from session
    request_token = session.pop('oauth_request_token', None)
    request_token_secret = session.pop('oauth_request_token_secret', None)

    if not request_token or not request_token_secret:
        flash("Session expired. Please try connecting again.", "warning")
        return redirect(url_for('twitter_login'))

    try:
        # Exchange request token for access token
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

        # Save user to database
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
            logger.info(f"User @{user_profile['screen_name']} connected successfully")
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
        db.set_user_active_status(user['id'], False) # Mark as inactive in DB
        flash(f"Twitter account @{user['screen_name']} disconnected.", "info")
        logger.info(f"Disconnected Twitter for user ID {user['id']}.")
    else:
        flash("No active user session to disconnect Twitter from.", "warning")
        logger.warning("Attempted to disconnect Twitter with no active user in session.")
    
    # Clear all session data related to the user
    session.pop('user_db_id', None)
    session.pop('oauth_request_token', None) # Should be gone anyway
    session.pop('oauth_request_token_secret', None) # Should be gone anyway
    # Add any other session keys specific to your app if needed
    
    logger.info("Cleared Twitter-related session variables.")
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
        
        # Basic email validation
        if email and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return jsonify({"success": False, "message": "Please enter a valid email address"}), 400

        messages = []
        
        # Handle email
        if email or email == '':  # Allow clearing email with empty string
            if user:
                if db.update_user_email(user['id'], email or None):
                    messages.append("Email updated")
                else:
                    return jsonify({"success": False, "message": "Failed to update email"}), 500
            else:
                session['pending_email'] = email
                messages.append("Email will be saved when you connect Twitter")
        
        # Handle topics
        if topics is not None:  # Allow empty list to clear topics
            if user:
                topics_json = json.dumps(topics)
                if db.update_user_topics(user['id'], topics_json):
                    messages.append("Topics updated")
                else:
                    return jsonify({"success": False, "message": "Failed to update topics"}), 500
            elif topics:  # Only warn if topics were provided but user not logged in
                messages.append("Connect Twitter to save topics")

        if not messages:
            messages.append("No changes made")
            
        return jsonify({"success": True, "message": ". ".join(messages)})
            
    except Exception as e:
        logger.error(f"Error saving settings: {e}", exc_info=True)
        return jsonify({"success": False, "message": "Server error occurred"}), 500

@app.route('/confirm-tweet/<token>')
def confirm_content_route(token):
    # This route's logic remains largely the same as before
    # ... (ensure it uses twitter_service.post_tweet correctly)
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
        logger.info(f"Posting content ID {content_record['id']} for @{content_record['screen_name']}.")
        success, post_data = twitter_service.post_tweet(
            tweet_content=content_record['generated_content'],
            user_oauth_token=content_record['oauth_token'],
            user_oauth_token_secret=content_record['oauth_token_secret']
        )
        if success:
            db.update_content_status(content_record['id'], 'posted', datetime.now(timezone.utc))
            flash("Content posted to Twitter!", "success")
            if content_record.get('user_email'):
                dashboard_url = url_for('index', _external=True)
                current_year = datetime.now(timezone.utc).year
                
                # Use email template instead of inline HTML
                email_html = render_template('email_posted.html',
                    screen_name=content_record['screen_name'],
                    tweet_content=content_record['generated_content'],
                    dashboard_url=dashboard_url,
                    current_year=current_year
                )
                
                email_service.send_email(
                    recipient_email=content_record['user_email'],
                    subject="Your AI Tweet Has Been Posted! 🎉",
                    body_html=email_html
                )
                logger.info(f"Successfully sent posted notification to {content_record['user_email']}")
        else:
            db.update_content_status(content_record['id'], 'failed_to_post')
            error_msg_str = str(post_data) # post_data is the error message from twitter_service
            if "403 Forbidden" in error_msg_str or "You are not permitted to perform this action" in error_msg_str:
                detailed_error_message = (
                    f"Failed to post content: {error_msg_str}. "
                    "This often indicates an issue with your Twitter App's permissions. "
                    "Please go to the Twitter Developer Portal (developer.twitter.com), "
                    "select your App, and ensure it has 'Read and Write' permissions enabled. "
                    "If you recently changed permissions, you might need to regenerate and update your "
                    "Access Token and Secret in the app's settings."
                )
                flash(detailed_error_message, "error")
            else:
                flash(f"Failed to post content: {error_msg_str}", "error")
    except Exception as e:
        logger.error(f"Error posting content ID {content_record['id']}: {e}", exc_info=True)
        db.update_content_status(content_record['id'], 'failed_to_post')
        flash(f"Failed to post: {e}", "error")
    return redirect(url_for('index'))

# --- Background Job ---
def scheduled_content_generation_job():
    with app.app_context(): 
        logger.info("SCHEDULER: Running scheduled content generation job.")
        active_users = db.get_active_users_with_topics() # Updated DB function name
        logger.info(f"SCHEDULER: Found {len(active_users)} active users with topics.")

        for user in active_users:
            try:
                logger.info(f"SCHEDULER: Processing user @{user['screen_name']} (ID: {user['id']})")
                topics_list = json.loads(user.get('topics', '[]'))
                if not topics_list:
                    logger.warning(f"SCHEDULER: No topics for user {user['id']}. Skipping.")
                    continue
                
                logger.info(f"SCHEDULER: Generating content for @{user['screen_name']} with user-selected topics: {topics_list}. The crew will identify broader trending topics.")
                
                # TODO: Decide how to pass user_topics to the crew if needed.
                # For now, the crew defined in crew.py starts with its own trending_agent.
                # We are calling kickoff() without specific inputs related to the user's topics here.
                # The crew.py would need modification to accept and use these user_topics.
                results = crew.kickoff() # Call kickoff() on the imported crew object

                logger.info(f"SCHEDULER: Crew kickoff for @{user['screen_name']} completed. Raw results: {results}")

                # TODO: Process 'results' to extract individual tweets and adapt the following logic.
                # The 'results' will be the output of the last task in crew.py (notification_task).
                # We need to find the output of 'validation_task' within the crew's execution or modify crew.py
                # to make this more accessible.

                # For now, let's assume 'results' is a placeholder and this part needs complete rework:
                generated_text_to_confirm = None # Placeholder
                if results: # This condition needs to be more specific based on actual crew output
                    # This is a placeholder for extracting ONE tweet. 
                    # If results contain multiple tweets, this logic needs to loop or be rethought.
                    if isinstance(results, str): # Simplistic check, likely needs to be more robust
                        generated_text_to_confirm = results 
                    else:
                        # Attempt to find a string representation if results is complex
                        # This part is highly dependent on the actual structure of 'results'
                        # from your specific crew's final task.
                        logger.warning(f"SCHEDULER: Crew results are not a simple string: {type(results)}. Trying to stringify. Needs proper parsing.")
                        generated_text_to_confirm = str(results) # Fallback, likely not a usable tweet

                if generated_text_to_confirm:
                    confirmation_token = str(uuid.uuid4())
                    db.add_generated_content(user['id'], generated_text_to_confirm, 'pending_confirmation', confirmation_token)
                    logger.info(f"SCHEDULER: Content for @{user['screen_name']} stored. Token: {confirmation_token}")
                    if user.get('email'):
                        confirm_url = url_for('confirm_content_route', token=confirmation_token, _external=True)
                        topics_str = ', '.join(topics_list) if topics_list else "your selected preferences"
                        current_year = datetime.now(timezone.utc).year
                        
                        # Use email template instead of inline HTML
                        email_html = render_template('email_confirmation.html',
                            screen_name=user['screen_name'],
                            generated_content=generated_text_to_confirm,
                            topics_used=topics_str,
                            confirm_url=confirm_url,
                            current_year=current_year
                        )
                        
                        email_service.send_email(
                            recipient_email=user['email'], 
                            subject="🤖 Your AI Content is Ready for Review!",
                            body_html=email_html
                        )
                        logger.info(f"SCHEDULER: Confirmation email sent to {user['email']}.")
                else: 
                    logger.warning(f"SCHEDULER: Crew execution for @{user['screen_name']} did not yield a usable text output for confirmation. Raw output: {results}")
            except Exception as e:
                logger.error(f"SCHEDULER: Error processing user @{user.get('screen_name', 'Unknown')} in job: {e}", exc_info=True)

# Configure and start scheduler
# Only run scheduler in development - Vercel serverless functions are stateless
if not os.environ.get('VERCEL_ENV') and not scheduler.running:
    # Fixed schedule: Daily at 14:00 (2:00 PM) server time for local testing.
    # Ensure server timezone is what you expect (e.g., UTC for cloud deployments)
    scheduler.add_job(scheduled_content_generation_job, 'cron', hour=14, minute=0, id='content_gen_job_1400')
    logger.info("Scheduled content generation job daily at 14:00 (2:00 PM) server time for local testing.")
    
    # You can add more fixed schedules here, e.g.:
    # scheduler.add_job(scheduled_content_generation_job, 'cron', hour=13, minute=12, id='content_gen_job_1312')
    # logger.info("Also scheduled content generation job daily at 13:12 (1:12 PM) server time.")

    try:
        scheduler.start()
        logger.info("APScheduler started.")
    except Exception as e:
        logger.error(f"Error starting APScheduler: {e}", exc_info=True)
else:
    if os.environ.get('VERCEL_ENV'):
        logger.info("Scheduler disabled in production (Vercel). Use Vercel Cron Jobs for scheduled tasks.")

if __name__ == '__main__':
    logger.info("Starting Flask app in development mode.")
    # Ensure TWITTER_CALLBACK_URL is set in your Twitter App settings to match http://localhost:5001/twitter/callback (or as configured)
    app.run(debug=True, port=5001)
