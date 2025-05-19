import os
import logging
import uuid
from datetime import datetime, timezone
import json

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
# We will not use flask_dance for Twitter OAuth anymore
# from flask_dance.contrib.twitter import make_twitter_blueprint, twitter as twitter_bp
from apscheduler.schedulers.background import BackgroundScheduler # Keep for later
from dotenv import load_dotenv

# Load environment variables from the root directory
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path=dotenv_path)

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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "supersecretkey_fixed_schedule")

# Configuration for url_for with _external=True outside of request context
app.config['SERVER_NAME'] = os.environ.get('FLASK_SERVER_NAME', 'localhost:5001')
app.config['APPLICATION_ROOT'] = os.environ.get('FLASK_APPLICATION_ROOT', '/')
app.config['PREFERRED_URL_SCHEME'] = os.environ.get('FLASK_PREFERRED_URL_SCHEME', 'http')

# Ensure TWITTER_CALLBACK_URL is set in your .env or environment
# Example: TWITTER_CALLBACK_URL=http://localhost:5001/twitter/callback
TWITTER_CALLBACK_URL = os.environ.get("TWITTER_CALLBACK_URL")
if not TWITTER_CALLBACK_URL:
    logger.warning("TWITTER_CALLBACK_URL not set in environment. OAuth callback might fail.")
    # Fallback for local development, ensure your Twitter app callback is set to this
    TWITTER_CALLBACK_URL = "http://localhost:5001/twitter/callback" 

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
    """
    Step 1 of OAuth 1.0a: Get a request token and redirect user to Twitter for authorization.
    """
    logger.info("Initiating Twitter login.")
    if not TWITTER_CALLBACK_URL:
        flash("Application callback URL is not configured. Cannot initiate Twitter login.", "error")
        return redirect(url_for('index'))

    try:
        # This function in twitter_service should handle getting the request token
        # and constructing the authorization URL.
        # It should return (request_token, request_token_secret, authorization_url)
        # or raise an exception.
        request_token_data = twitter_service.get_request_token_and_auth_url(TWITTER_CALLBACK_URL)
        
        if not request_token_data or 'authorization_url' not in request_token_data:
            logger.error("Failed to get request token or authorization URL from twitter_service.")
            flash("Could not initiate Twitter login. Please try again later.", "error")
            return redirect(url_for('index'))

        # Store the request token and secret in session to verify in callback
        session['oauth_request_token'] = request_token_data['oauth_token']
        session['oauth_request_token_secret'] = request_token_data['oauth_token_secret']
        
        logger.info(f"Redirecting user to Twitter authorization URL: {request_token_data['authorization_url']}")
        return redirect(request_token_data['authorization_url'])

    except Exception as e:
        logger.error(f"Error during Twitter login initiation: {e}", exc_info=True)
        flash(f"An error occurred while trying to connect to Twitter: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/twitter/callback')
def twitter_callback():
    """
    Step 2 of OAuth 1.0a: Handle callback from Twitter, exchange request token for access token,
    fetch user profile, and save to DB.
    """
    logger.info("Received callback from Twitter.")
    oauth_verifier = request.args.get('oauth_verifier')
    denied = request.args.get('denied')

    if denied:
        logger.warning(f"User denied Twitter authorization. Token: {denied}")
        flash("You denied the Twitter authorization request.", "warning")
        return redirect(url_for('index'))

    if not oauth_verifier:
        logger.error("OAuth verifier not found in Twitter callback.")
        flash("Failed to get authorization from Twitter. Verifier missing.", "error")
        return redirect(url_for('index'))

    # Retrieve request token from session
    request_token = session.pop('oauth_request_token', None)
    request_token_secret = session.pop('oauth_request_token_secret', None)

    if not request_token or not request_token_secret:
        logger.error("Request token not found in session during callback. Session might have expired.")
        flash("Your session expired or request token was missing. Please try logging in again.", "error")
        return redirect(url_for('twitter_login')) # Redirect to login again

    try:
        # This function in twitter_service should exchange request token + verifier for access token
        # It should return {'oauth_token': ..., 'oauth_token_secret': ..., 'user_id': ..., 'screen_name': ...}
        # Some OAuth libraries might give user_id and screen_name directly with access token, others require a separate call.
        # For simplicity, let's assume get_access_token might also fetch basic user identifiers if common.
        access_token_data = twitter_service.get_access_token(
            request_token,
            request_token_secret,
            oauth_verifier
        )

        if not access_token_data or 'oauth_token' not in access_token_data:
            logger.error(f"Failed to get access token from Twitter: {access_token_data}")
            flash("Could not authenticate with Twitter. Please try again.", "error")
            return redirect(url_for('index'))

        oauth_token = access_token_data['oauth_token']
        oauth_token_secret = access_token_data['oauth_token_secret']
        
        # Fetch user profile information using the access token
        # This function in twitter_service uses the access token to get user details
        # It should return {'id_str': ..., 'screen_name': ...} or similar
        user_profile = twitter_service.get_me(oauth_token, oauth_token_secret)

        if not user_profile or 'id_str' not in user_profile or 'screen_name' not in user_profile:
            logger.error(f"Failed to fetch user profile from Twitter: {user_profile}")
            flash("Connected to Twitter, but could not fetch your profile information.", "error")
            return redirect(url_for('index'))

        twitter_user_id_str = user_profile['id_str']
        screen_name_str = user_profile['screen_name']
        logger.info(f"Successfully fetched Twitter info: ID {twitter_user_id_str}, Username {screen_name_str}")
        
        # At this point, we have user's Twitter ID, screen name, and OAuth tokens.
        # We need to save or update this in our database.
        # The 'email' is not part of standard Twitter OAuth data.
        # We can retrieve pending email if we implement that flow separately.
        pending_email = session.pop('pending_email', None) 
        
        user_record = db.create_or_update_user(
            twitter_id=twitter_user_id_str,
            screen_name=screen_name_str,
            oauth_token=oauth_token,
            oauth_token_secret=oauth_token_secret,
            email=pending_email,
            topics=None # Topics are not set at login, existing ones are preserved by db func
        )

        if user_record and user_record.get('id'):
            session["user_db_id"] = user_record['id'] # Store internal DB ID in session
            logger.info(f"User @{screen_name_str} (Internal ID: {user_record['id']}) connected and session created.")
            flash(f"Successfully connected Twitter account: @{screen_name_str}", "success")
        else:
            logger.error("Failed to save user/Twitter connection to database.")
            flash("Could not save your user profile after Twitter connection. Please try again.", "error")
            
        return redirect(url_for('index'))

    except Exception as e:
        logger.error(f"Error during Twitter callback processing: {e}", exc_info=True)
        flash(f"An error occurred after Twitter authorization: {str(e)}", "error")
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
def save_settings_route(): # Renamed for clarity
    logger.info("Received request to /save-settings (formerly /save-schedule)")
    user = get_current_user_from_session()
    response_messages = []
    overall_success = True

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Invalid request: No data."}), 400
            
        email_to_save = data.get('email')
        topics_list = data.get('topics', []) # User-selected topics
        
        logger.info(f"/save-settings: Data - Email: '{email_to_save}', Topics: {topics_list}")

        if email_to_save is not None: # Allow empty string to clear email
            if user:
                if db.update_user_email(user['id'], email_to_save if email_to_save.strip() else None):
                    response_messages.append("Email updated.")
                else:
                    response_messages.append("Failed to update email.")
                    overall_success = False
            else:
                session['pending_email'] = email_to_save
                response_messages.append("Email will be associated upon Twitter connection.")
        
        if user: # Topics can only be saved for a logged-in user
            if 'topics' in data: # Check if topics key was sent, even if empty list
                topics_json_str = json.dumps(topics_list)
                if db.update_user_topics(user['id'], topics_json_str):
                    response_messages.append("Topics updated.")
                else:
                    response_messages.append("Failed to update topics.")
                    overall_success = False
        elif topics_list: # Topics provided but no user logged in
            response_messages.append("Please connect Twitter to save topics.")
            # overall_success = False # Don't mark as failure if email was pending successfully

        if not response_messages:
            response_messages.append("No changes were submitted.")
            flash(" ".join(response_messages), "info")
            return jsonify({"success": True, "message": " ".join(response_messages)})

        final_message = " ".join(response_messages)
        flash(final_message, "success" if overall_success else "error")
        return jsonify({"success": overall_success, "message": final_message}), 200 if overall_success else 400
            
    except Exception as e:
        logger.error(f"Error saving settings: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Server error: {e}"}), 500

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
                body_html_posted = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your Content Has Been Posted!</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f4f4; }}
        .container {{ max-width: 600px; margin: 20px auto; padding: 20px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        .header {{ background-color: #28a745; color: #ffffff; padding: 10px 20px; text-align: center; border-top-left-radius: 8px; border-top-right-radius: 8px; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .content {{ padding: 20px; color: #333333; line-height: 1.6; }}
        .content p {{ margin: 10px 0; }}
        .tweet-posted {{ background-color: #e9ecef; padding: 15px; border-radius: 5px; margin: 15px 0; font-style: italic; }}
        .button-container {{ text-align: center; margin: 20px 0; }}
        .button {{ background-color: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-size: 16px; display: inline-block; }}
        .footer {{ text-align: center; padding: 10px; font-size: 12px; color: #777777; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Content Successfully Posted!</h1>
        </div>
        <div class="content">
            <p>Hello {content_record['screen_name']},</p>
            <p>Great news! Your AI-generated content has been successfully posted to your Twitter account:</p>
            <div class="tweet-posted">
                <p>"{content_record['generated_content']}"</p>
            </div>
            <p>You can view it on your profile or visit your dashboard for more options.</p>
            <div class="button-container">
                <a href="{dashboard_url}" class="button">Go to Dashboard</a>
            </div>
            <p>Thanks for using our service,<br>The AutoTweet Bot Team</p>
        </div>
        <div class="footer">
            <p>&copy; {current_year} AutoTweet Bot. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
'''
                email_service.send_email(
                    recipient_email=content_record['user_email'],
                    subject="Your AI Content Has Been Posted!",
                    body_html=body_html_posted
                )
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
                        email_body_confirmation = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Confirm Your AI-Generated Content</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f4f4; }}
        .container {{ max-width: 600px; margin: 20px auto; padding: 20px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        .header {{ background-color: #007bff; color: #ffffff; padding: 10px 20px; text-align: center; border-top-left-radius: 8px; border-top-right-radius: 8px; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .content {{ padding: 20px; color: #333333; line-height: 1.6; }}
        .content p {{ margin: 10px 0; }}
        .tweet-preview {{ background-color: #e9ecef; padding: 15px; border-radius: 5px; margin: 15px 0; font-style: italic; }}
        .button-container {{ text-align: center; margin: 20px 0; }}
        .button {{ background-color: #28a745; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-size: 16px; display: inline-block; }}
        .footer {{ text-align: center; padding: 10px; font-size: 12px; color: #777777; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Your AI Content is Ready!</h1>
        </div>
        <div class="content">
            <p>Hello {user['screen_name']},</p>
            <p>We've generated new content for you based on your selected topics ({topics_str}). Please review it below:</p>
            <div class="tweet-preview">
                <p>"{generated_text_to_confirm}"</p>
            </div>
            <p>If you're happy with it, please click the button below to post it to your Twitter profile.</p>
            <div class="button-container">
                <a href="{confirm_url}" class="button">Confirm and Post to Twitter</a>
            </div>
            <p>If you don't want to post this, you can simply ignore this email.</p>
            <p>Thanks,<br>The AutoTweet Bot Team</p>
        </div>
        <div class="footer">
            <p>&copy; {current_year} AutoTweet Bot. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
'''
                        email_service.send_email(user['email'], "Confirm Your AI Generated Content", email_body_confirmation)
                        logger.info(f"SCHEDULER: Confirmation email sent to {user['email']}.")
                else: 
                    logger.warning(f"SCHEDULER: Crew execution for @{user['screen_name']} did not yield a usable text output for confirmation. Raw output: {results}")
            except Exception as e:
                logger.error(f"SCHEDULER: Error processing user @{user.get('screen_name', 'Unknown')} in job: {e}", exc_info=True)

# Configure and start scheduler
if not scheduler.running:
    # Fixed schedule: Daily at 11:55 AM server time.
    # Ensure server timezone is what you expect (e.g., UTC for cloud deployments)
    scheduler.add_job(scheduled_content_generation_job, 'cron', hour=16, minute=27, id='content_gen_job_1627pm')
    logger.info("Scheduled content generation job daily at 16:27 PM (server time).")
    
    # You can add more fixed schedules here, e.g.:
    # scheduler.add_job(scheduled_content_generation_job, 'cron', hour=13, minute=12, id='content_gen_job_1312pm')
    # logger.info("Also scheduled content generation job daily at 13:12 PM (server time).")

    try:
        scheduler.start()
        logger.info("APScheduler started.")
    except Exception as e:
        logger.error(f"Error starting APScheduler: {e}", exc_info=True)

if __name__ == '__main__':
    logger.info("Starting Flask app in development mode.")
    # Ensure TWITTER_CALLBACK_URL is set in your Twitter App settings to match http://localhost:5001/twitter/callback (or as configured)
    app.run(debug=True, port=5001)
