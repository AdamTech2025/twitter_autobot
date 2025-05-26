# Twitter API service for OAuth and tweet posting
import os
import tweepy
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(dotenv_path=dotenv_path, override=True)  # Force override system env vars

TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET_KEY = os.getenv("TWITTER_API_SECRET_KEY")

# Debug logging for environment loading
logger.info(f"Loading .env from: {dotenv_path}")
logger.info(f"API Key loaded: {TWITTER_API_KEY[:10] + '...' if TWITTER_API_KEY else 'None'}")
logger.info(f"API Secret loaded: {TWITTER_API_SECRET_KEY[:10] + '...' if TWITTER_API_SECRET_KEY else 'None'}")

def _check_api_keys():
    """Check if API keys are available"""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET_KEY]):
        logger.error("TWITTER_API_KEY or TWITTER_API_SECRET_KEY not found in environment.")
        return False
    return True

def _handle_twitter_error(e):
    """Handle Twitter API errors and return user-friendly messages"""
    error_msg = str(e).lower()
    
    # Check for 503 service unavailable errors (including the specific tweepy format)
    if ("503" in error_msg or "service unavailable" in error_msg or 
        "this page is down" in error_msg or "token request failed with code 503" in error_msg):
        return {
            "error": "service_unavailable", 
            "message": "Twitter/X is temporarily unavailable. Please try again later."
        }
    elif "401" in error_msg or "unauthorized" in error_msg:
        return {
            "error": "auth_failed", 
            "message": "Authentication failed. Please check your Twitter API credentials."
        }
    elif "429" in error_msg or "rate limit" in error_msg:
        return {
            "error": "rate_limit", 
            "message": "Rate limit exceeded. Please try again later."
        }
    else:
        return {
            "error": "unknown", 
            "message": f"Twitter authentication failed: {str(e)}"
        }

def get_request_token_and_auth_url(callback_url):
    """
    Step 1 of OAuth: Get request token and authorization URL
    Returns: dict with oauth_token, oauth_token_secret, authorization_url OR error dict
    """
    if not _check_api_keys():
        return {"error": "config", "message": "Twitter API credentials not configured."}
    
    logger.info(f"Starting OAuth with callback URL: {callback_url}")
    logger.info(f"Using API key: {TWITTER_API_KEY[:10]}...") # Log first 10 chars for debugging
    
    try:
        auth = tweepy.OAuth1UserHandler(
            TWITTER_API_KEY, 
            TWITTER_API_SECRET_KEY, 
            callback=callback_url
        )
        
        logger.info("Getting authorization URL...")
        auth_url = auth.get_authorization_url(signin_with_twitter=True)
        
        if not auth.request_token or 'oauth_token' not in auth.request_token:
            logger.error("Failed to retrieve valid request token from Twitter.")
            return {"error": "token_failed", "message": "Failed to get authorization token from Twitter."}

        logger.info("OAuth request token obtained successfully.")
        return {
            'oauth_token': auth.request_token['oauth_token'],
            'oauth_token_secret': auth.request_token['oauth_token_secret'],
            'authorization_url': auth_url
        }
        
    except tweepy.TweepyException as e:
        logger.error(f"Twitter OAuth error: {e}")
        return _handle_twitter_error(e)
    except Exception as e:
        logger.error(f"Unexpected OAuth error: {e}", exc_info=True)
        return {"error": "unexpected", "message": "An unexpected error occurred."}

def get_access_token(request_token, request_token_secret, oauth_verifier):
    """
    Step 2 of OAuth: Exchange request token for access token
    Returns: dict with oauth_token, oauth_token_secret OR None on error
    """
    if not _check_api_keys():
        return None
        
    try:
        auth = tweepy.OAuth1UserHandler(TWITTER_API_KEY, TWITTER_API_SECRET_KEY)
        auth.request_token = {
            'oauth_token': request_token,
            'oauth_token_secret': request_token_secret
        }
        
        access_token, access_token_secret = auth.get_access_token(oauth_verifier)
        
        if not access_token or not access_token_secret:
            logger.error("Failed to obtain access token from Twitter.")
            return None

        logger.info("OAuth access token obtained successfully.")
        return {
            'oauth_token': access_token,
            'oauth_token_secret': access_token_secret
        }
        
    except tweepy.TweepyException as e:
        logger.error(f"Error obtaining access token: {e}")
        return None

def get_me(access_token, access_token_secret):
    """
    Get authenticated user's profile information
    Returns: dict with id_str, screen_name OR None on error
    """
    if not _check_api_keys():
        return None
        
    try:
        auth = tweepy.OAuth1UserHandler(TWITTER_API_KEY, TWITTER_API_SECRET_KEY)
        auth.set_access_token(access_token, access_token_secret)
        api = tweepy.API(auth)
        
        user = api.verify_credentials()
        if user:
            logger.info(f"Successfully fetched user details: @{user.screen_name}")
            return {
                'id_str': user.id_str,
                'screen_name': user.screen_name
            }
        else:
            logger.error("Failed to verify credentials.")
            return None
            
    except tweepy.TweepyException as e:
        logger.error(f"Error in get_me: {e}")
        return None

def post_tweet(tweet_content, user_oauth_token, user_oauth_token_secret):
    """
    Post a tweet using user's OAuth tokens
    Returns: (success_bool, result_data_or_error_message)
    """
    if not _check_api_keys():
        return False, "Twitter API credentials not configured."
        
    if not user_oauth_token or not user_oauth_token_secret:
        return False, "User OAuth tokens are required."

    try:
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET_KEY,
            access_token=user_oauth_token,
            access_token_secret=user_oauth_token_secret,
            wait_on_rate_limit=True
        )
        
        logger.info("Attempting to post tweet...")
        response = client.create_tweet(text=tweet_content)

        if response.data and response.data.get("id"):
            logger.info(f"Tweet posted successfully! ID: {response.data['id']}")
            return True, response.data
        else:
            error_msg = response.errors if hasattr(response, 'errors') else "Unknown error"
            logger.error(f"Failed to post tweet: {error_msg}")
            return False, str(error_msg)
           
    except tweepy.TweepyException as e:
        logger.error(f"Twitter API error while posting: {e}")
        return False, f"Twitter error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error posting tweet: {e}", exc_info=True)
        return False, f"An unexpected error occurred: {str(e)}"
