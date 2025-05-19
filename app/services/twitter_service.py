# Placeholder for Twitter API interactions
import os
import tweepy # You'll need to install tweepy: pip install tweepy
from dotenv import load_dotenv
import logging
from urllib.parse import parse_qsl

logger = logging.getLogger(__name__)

# Load environment variables for API keys
# Assumes .env is two levels up from this file (e.g., in project root)
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(dotenv_path=dotenv_path)

TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET_KEY = os.getenv("TWITTER_API_SECRET_KEY")
# User-specific access tokens from .env are not directly used for the OAuth flow initiation for new users
# They might be app owner's tokens for other purposes.
# TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
# TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
# TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN") # For v2 API


# --- OAuth 1.0a Functions for main.py ---

def get_request_token_and_auth_url(callback_url):
    """
    Step 1 of OAuth 1.0a: Get a request token and the authorization URL.
    Returns a dictionary: {'oauth_token': ..., 'oauth_token_secret': ..., 'authorization_url': ...}
    or None if an error occurs.
    """
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET_KEY]):
        logger.error("TWITTER_API_KEY or TWITTER_API_SECRET_KEY not found in environment.")
        return None
    try:
        auth = tweepy.OAuth1UserHandler(
            TWITTER_API_KEY, TWITTER_API_SECRET_KEY,
            callback=callback_url
        )
        auth_url = auth.get_authorization_url(signin_with_twitter=True) # signin_with_twitter is a good practice
        
        # auth.request_token is like {'oauth_token': 'TOKEN', 'oauth_token_secret': 'SECRET', 'oauth_callback_confirmed': 'true'}
        if not auth.request_token or 'oauth_token' not in auth.request_token or 'oauth_token_secret' not in auth.request_token:
            logger.error("Failed to retrieve valid request token from Twitter.")
            return None

        logger.info(f"OAuth: Generated authorization URL. Request token obtained.")
        return {
            'oauth_token': auth.request_token['oauth_token'],
            'oauth_token_secret': auth.request_token['oauth_token_secret'],
            'authorization_url': auth_url
        }
    except tweepy.TweepyException as e:
        logger.error(f"Error during OAuth get_request_token_and_auth_url: {e}")
        return None

def get_access_token(request_oauth_token_str, request_oauth_token_secret_str, oauth_verifier_str):
    """
    Step 2 of OAuth 1.0a: Exchange request token and verifier for an access token and secret.
    Returns a dictionary: {'oauth_token': ..., 'oauth_token_secret': ...}
    or None if an error occurs.
    """
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET_KEY]):
        logger.error("TWITTER_API_KEY or TWITTER_API_SECRET_KEY not found for OAuth completion.")
        return None
    try:
        auth = tweepy.OAuth1UserHandler(
            TWITTER_API_KEY, TWITTER_API_SECRET_KEY,
            callback=None # Callback not strictly needed here for token fetching stage
        )
        # Manually set the request token for the handler
        auth.request_token = {
            'oauth_token': request_oauth_token_str,
            'oauth_token_secret': request_oauth_token_secret_str
        }
        
        logger.info(f"OAuth: Completing with verifier for token: {request_oauth_token_str}")
        # The get_access_token method in tweepy.OAuth1UserHandler directly returns a tuple:
        # (access_token_str, access_token_secret_str)
        # It no longer returns the full response text that needs parsing for user_id/screen_name.
        access_token_val, access_token_secret_val = auth.get_access_token(oauth_verifier_str)
        
        if not access_token_val or not access_token_secret_val:
            logger.error("Failed to obtain access token and secret from Twitter.")
            return None

        logger.info("OAuth: Access token and secret obtained successfully.")
        return {
            'oauth_token': access_token_val,
            'oauth_token_secret': access_token_secret_val
            # Note: user_id and screen_name are NOT part of this response from tweepy's method.
            # They need to be fetched in a separate call (get_me).
        }
    except tweepy.TweepyException as e:
        logger.error(f"Error obtaining access token in get_access_token: {e}")
        return None

def get_me(user_access_token, user_access_token_secret):
    """
    Fetches authenticated user's profile information (ID and screen name) using their access tokens.
    Uses API v1.1 verify_credentials.
    Returns a dictionary: {'id_str': ..., 'screen_name': ...} or None.
    """
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET_KEY, user_access_token, user_access_token_secret]):
        logger.error("Missing API keys or user access tokens for get_me.")
        return None
    try:
        auth = tweepy.OAuth1UserHandler(TWITTER_API_KEY, TWITTER_API_SECRET_KEY)
        auth.set_access_token(user_access_token, user_access_token_secret)
        api_v1 = tweepy.API(auth)
        
        user_obj = api_v1.verify_credentials() # Returns a User object
        if user_obj:
            logger.info(f"Successfully fetched user details: @{user_obj.screen_name}")
            return {
                'id_str': user_obj.id_str,
                'screen_name': user_obj.screen_name
                # Add other fields if needed, e.g., user_obj.name for display name
            }
        else:
            logger.error("Failed to verify credentials and fetch user details.")
            return None
    except tweepy.TweepyException as e:
        logger.error(f"Error in get_me (verify_credentials): {e}")
        return None

# --- Other Service Functions (Keep existing ones if needed, or adapt/remove) ---

# Example: Keeping post_tweet, but ensuring it can use user-specific tokens
def post_tweet(tweet_content, user_oauth_token=None, user_oauth_token_secret=None):
    """Posts a tweet. Uses user-specific tokens if provided, otherwise tries app's context (if set up)."""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET_KEY]):
        logger.error("Consumer key/secret not available for posting tweet.")
        return False, "Consumer key/secret not configured."

    if not user_oauth_token or not user_oauth_token_secret:
        # This part would require the app itself to have its own access tokens (e.g. app owner's)
        # if you want to post tweets without a specific user's context from an OAuth flow.
        # For this bot, tweets are usually on behalf of a user who has connected.
        logger.warning("Attempting to post tweet without user-specific tokens. This might require app-level access tokens if supported by your setup.")
        # Fallback to app owner's tokens if they were loaded and intended for this.
        # However, for a user-centric bot, always use user's tokens obtained via OAuth.
        # For now, let's assume we always need user tokens for posting.
        return False, "User OAuth token and secret are required to post."


    try:
        # Use API v2 client for posting if preferred and tokens are compatible
        # Note: tweepy.Client needs all four: consumer_key, consumer_secret, access_token, access_token_secret for user context
        client_v2_user_context = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET_KEY,
            access_token=user_oauth_token,
            access_token_secret=user_oauth_token_secret,
            wait_on_rate_limit=True
        )
        logger.info(f"Attempting to post tweet with user tokens for user associated with token: {user_oauth_token[:5]}...")
        response = client_v2_user_context.create_tweet(text=tweet_content)

        if response.data and response.data.get("id"):
           logger.info(f"Tweet posted successfully! ID: {response.data['id']}")
           return True, response.data
        else:
           error_message = response.errors if hasattr(response, 'errors') and response.errors else "Unknown error during tweet creation"
           logger.error(f"Failed to post tweet. Response: {error_message}")
           return False, error_message
           
    except tweepy.TweepyException as e:
        logger.error(f"TweepyException while posting tweet: {e}")
        # Try to extract more specific error from e.api_codes, e.api_errors, e.response
        # For example, if e.response is not None and e.response.text might have JSON error.
        error_detail = str(e)
        if e.response is not None and hasattr(e.response, 'text'):
            try:
                error_json = e.response.json()
                if 'errors' in error_json:
                    error_detail = error_json['errors']
                elif 'detail' in error_json: # V2 error format
                    error_detail = error_json['detail']
            except ValueError: # Not JSON
                error_detail = e.response.text

        return False, f"TweepyException: {error_detail}"
    except Exception as e:
        logger.error(f"Generic error posting tweet: {e}", exc_info=True)
        return False, f"An unexpected error occurred: {str(e)}"


# --- Legacy or general client initializations (can be refactored or removed if not used elsewhere) ---
# These global clients using .env fixed tokens are less relevant for per-user OAuth flow,
# but might be used for app-level data fetching if needed (e.g., app owner's context).

_api_v1_app_context = None
def get_twitter_api_v1_app_context():
    # This would use app-owner tokens if set in .env, NOT for individual users.
    global _api_v1_app_context
    if _api_v1_app_context is None:
        app_access_token = os.getenv("ACCESS_TOKEN") # Corrected: Uses ACCESS_TOKEN from .env
        app_access_token_secret = os.getenv("ACCESS_SECRET") # Corrected: Uses ACCESS_SECRET from .env
        if not all([TWITTER_API_KEY, TWITTER_API_SECRET_KEY, app_access_token, app_access_token_secret]):
            logger.warning("App-level Twitter API v1.1 credentials (TWITTER_API_KEY, TWITTER_API_SECRET_KEY, ACCESS_TOKEN, ACCESS_SECRET) not fully set in .env for app context.")
            return None
        try:
            auth = tweepy.OAuthHandler(TWITTER_API_KEY, TWITTER_API_SECRET_KEY)
            auth.set_access_token(app_access_token, app_access_token_secret)
            _api_v1_app_context = tweepy.API(auth, wait_on_rate_limit=True)
            logger.info("App-context Twitter API V1.1 client initialized.")
        except Exception as e:
            logger.error(f"Error initializing app-context Twitter V1.1 API: {e}")
            return None
    return _api_v1_app_context

# --- Placeholder for other service functions like email if they belong here ---
# from . import email_service # If email_service is also in this directory

if __name__ == '__main__':
    # Test functions (requires .env to be set up correctly)
    # Ensure your .env is in the project root, and this script is run from a context where that path is valid.
    print("Testing twitter_service.py functions...")
    # Note: OAuth flow cannot be fully tested from CLI without a running web server for callback.
    
    # To test get_me or post_tweet, you'd need valid user_access_token and secret
    # test_user_token = "USER_TOKEN_HERE"
    # test_user_secret = "USER_SECRET_HERE"
    # if test_user_token != "USER_TOKEN_HERE":
    #     user_details = get_me(test_user_token, test_user_secret)
    #     if user_details:
    #         print(f"Get Me Test Successful: {user_details}")
    #         # post_tweet("Test tweet from twitter_service.py script!", test_user_token, test_user_secret)
    #     else:
    #         print("Get Me Test Failed.")
    # else:
    #     print("Skipping get_me/post_tweet tests as no user tokens provided for testing.")

    # Test app-context client if .env has app owner's tokens
    # api_v1_app = get_twitter_api_v1_app_context()
    # if api_v1_app:
    #     try:
    #         app_creds = api_v1_app.verify_credentials()
    #         print(f"App context client verified for @{app_creds.screen_name}")
    #     except Exception as e:
    #         print(f"Could not verify app context client: {e}")
    pass
