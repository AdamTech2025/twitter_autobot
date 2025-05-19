import sqlite3
import os
import logging
from datetime import datetime

DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', 'twitter_bot.db')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    logger.info(f"Initializing database with new schema (no schedule_times) at {DATABASE_PATH}")
    if not os.path.exists(os.path.dirname(DATABASE_PATH)):
        os.makedirs(os.path.dirname(DATABASE_PATH))
        logger.info(f"Created directory {os.path.dirname(DATABASE_PATH)}")
        
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS tweet_history;") # Old, potentially, ensure clean up
    cursor.execute("DROP TABLE IF EXISTS ai_generated_content_history;")
    cursor.execute("DROP TABLE IF EXISTS users;") 
    logger.info("Dropped existing tables (users, ai_generated_content_history, tweet_history).")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        twitter_id TEXT UNIQUE NOT NULL,
        screen_name TEXT NOT NULL,
        oauth_token TEXT NOT NULL,
        oauth_token_secret TEXT NOT NULL,
        email TEXT,
        topics TEXT, -- JSON string for topics
        -- schedule_times TEXT, -- REMOVED
        is_active BOOLEAN DEFAULT TRUE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    logger.info("Created users table (without schedule_times).")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_generated_content_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        generated_content TEXT NOT NULL,
        status TEXT NOT NULL,
        confirmation_token TEXT UNIQUE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        posted_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)
    logger.info("Created ai_generated_content_history table.")
    
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS update_users_updated_at
    AFTER UPDATE ON users
    FOR EACH ROW
    BEGIN
        UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
    END;
    """)
    logger.info("Created update_users_updated_at trigger.")

    conn.commit()
    conn.close()
    logger.info("Database initialization (no schedule_times) complete.")

# --- User Functions ---
def create_or_update_user(twitter_id, screen_name, oauth_token, oauth_token_secret, email=None, topics=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, topics FROM users WHERE twitter_id = ?", (twitter_id,))
        user_row = cursor.fetchone()

        # Preserve existing topics if not explicitly passed during an update for a new login
        # Topics are now managed via save_schedule_route primarily
        final_topics = topics

        if user_row:
            user_id = user_row['id']
            logger.info(f"Updating existing user for twitter_id {twitter_id} (Internal ID: {user_id}).")
            if topics is None: # If topics not provided during this call, keep existing ones
                final_topics = user_row['topics'] 

            update_fields = {
                'screen_name': screen_name,
                'oauth_token': oauth_token,
                'oauth_token_secret': oauth_token_secret,
                'is_active': True,
                'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            if email is not None: update_fields['email'] = email
            if final_topics is not None: update_fields['topics'] = final_topics
            
            set_clause = ", ".join([f"{key} = ?" for key in update_fields.keys()])
            values = list(update_fields.values()) + [user_id]
            
            cursor.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
        else:
            logger.info(f"Creating new user for twitter_id {twitter_id}. Topics: {final_topics}")
            cursor.execute("""
                INSERT INTO users (twitter_id, screen_name, oauth_token, oauth_token_secret, email, topics, is_active)
                VALUES (?, ?, ?, ?, ?, ?, TRUE)
            """, (twitter_id, screen_name, oauth_token, oauth_token_secret, email, final_topics))
            user_id = cursor.lastrowid
        
        conn.commit()
        logger.info(f"Successfully created/updated user: Twitter ID {twitter_id}, Internal ID {user_id}")
        return get_user_by_id(user_id)
    except sqlite3.Error as e:
        logger.error(f"Database error in create_or_update_user for twitter_id {twitter_id}: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

def get_user_by_id(user_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        return dict(user) if user else None
    finally:
        conn.close()

def get_user_by_twitter_id(twitter_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE twitter_id = ?", (twitter_id,))
        user = cursor.fetchone()
        return dict(user) if user else None
    finally:
        conn.close()

def update_user_email(user_id, email):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # If email is empty string or None, store NULL in database
        email_to_store = email if email and email.strip() else None
        cursor.execute("UPDATE users SET email = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (email_to_store, user_id))
        conn.commit()
        logger.info(f"Updated email for user ID {user_id} to '{email_to_store}'")
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error in update_user_email for user ID {user_id}: {e}")
        return False
    finally:
        conn.close()

# Renamed from update_user_schedule to update_user_topics as schedule_times is removed
def update_user_topics(user_id, topics_json):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE users 
            SET topics = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (topics_json, user_id))
        conn.commit()
        logger.info(f"Updated topics for user ID {user_id}.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error in update_user_topics for user ID {user_id}: {e}")
        return False
    finally:
        conn.close()

def set_user_active_status(user_id, is_active):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (is_active, user_id))
        conn.commit()
        logger.info(f"Set active status for user ID {user_id} to {is_active}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error in set_user_active_status for user ID {user_id}: {e}")
        return False
    finally:
        conn.close()

# Renamed from get_active_users_with_schedules to get_active_users_with_topics
def get_active_users_with_topics():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Now only checks for active status and if topics are set (not empty or null)
        # Assumes topics are stored as JSON array, so '[]' means no topics.
        cursor.execute("""
            SELECT * FROM users 
            WHERE is_active = TRUE AND topics IS NOT NULL AND topics != '' AND topics != '[]'
        """)
        users = [dict(row) for row in cursor.fetchall()]
        logger.info(f"Found {len(users)} active users with topics.")
        return users
    except sqlite3.Error as e:
        logger.error(f"Database error in get_active_users_with_topics: {e}")
        return []
    finally:
        conn.close()

# --- AI Generated Content History Functions (largely unchanged) ---
# ... (rest of the functions: add_generated_content, get_history_by_user_id, etc. remain the same)
# ... except ensuring they are still compatible if user object structure changes slightly (it doesn't much here)

def add_generated_content(user_id, generated_content, status, confirmation_token=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO ai_generated_content_history (user_id, generated_content, status, confirmation_token)
            VALUES (?, ?, ?, ?)
        """, (user_id, generated_content, status, confirmation_token))
        conn.commit()
        content_id = cursor.lastrowid
        logger.info(f"Added generated content to history for user ID {user_id}. Content ID: {content_id}, Status: {status}")
        return content_id
    except sqlite3.Error as e:
        logger.error(f"Database error in add_generated_content for user ID {user_id}: {e}")
        return None
    finally:
        conn.close()

def get_history_by_user_id(user_id, limit=20):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT h.*, u.screen_name FROM ai_generated_content_history h
            JOIN users u ON h.user_id = u.id
            WHERE h.user_id = ? 
            ORDER BY h.created_at DESC 
            LIMIT ?
        """, (user_id, limit))
        history = [dict(row) for row in cursor.fetchall()]
        return history
    except sqlite3.Error as e:
        logger.error(f"Database error in get_history_by_user_id for user_id {user_id}: {e}")
        return []
    finally:
        conn.close()

def get_content_by_confirmation_token(confirmation_token):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT h.*, u.screen_name, u.oauth_token, u.oauth_token_secret, u.email as user_email, u.is_active as user_is_active
            FROM ai_generated_content_history h
            JOIN users u ON h.user_id = u.id
            WHERE h.confirmation_token = ?
        """, (confirmation_token,))
        content = cursor.fetchone()
        return dict(content) if content else None
    except sqlite3.Error as e:
        logger.error(f"Database error in get_content_by_confirmation_token for token {confirmation_token}: {e}")
        return None
    finally:
        conn.close()

def update_content_status(content_id, status, posted_at=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if posted_at:
            cursor.execute("UPDATE ai_generated_content_history SET status = ?, posted_at = ? WHERE id = ?", (status, posted_at, content_id))
        else:
            cursor.execute("UPDATE ai_generated_content_history SET status = ? WHERE id = ?", (status, content_id))
        conn.commit()
        logger.info(f"Updated status for content ID {content_id} to {status}")
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error in update_content_status for content ID {content_id}: {e}")
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    logger.info("Running init_db() directly for setup/reset (no schedule_times).")
    init_db()
    logger.info("Manual init_db() run complete (no schedule_times).")

    # Example Usage (for testing - normally called by the app)
    # test_user = create_or_update_user(twitter_id="test_twitter_123", screen_name="TestUser", oauth_token="test_oauth", oauth_token_secret="test_secret", email="test@example.com", topics='["AI", "Testing"]')
    # if test_user:
    #     logger.info(f"Test user created/updated: {test_user}")
    #     retrieved_user_by_tid = get_user_by_twitter_id("test_twitter_123")
    #     logger.info(f"Retrieved user by twitter_id: {retrieved_user_by_tid}")
    #     retrieved_user_by_id = get_user_by_id(test_user['id'])
    #     logger.info(f"Retrieved user by internal id: {retrieved_user_by_id}")

    #     update_user_email(test_user['id'], "updated_test@example.com")
    #     update_user_topics(test_user['id'], '["Flask", "Python"]')
    #     logger.info(f"Updated user details: {get_user_by_id(test_user['id'])}")
        
    #     content_id = add_generated_content(test_user['id'], "This is a test AI generated content.", "pending_confirmation", "test_confirm_token_xyz")
    #     if content_id:
    #         logger.info(f"Test content added with ID: {content_id}")
    #         history = get_history_by_user_id(test_user['id'])
    #         logger.info(f"Content history for user {test_user['id']}: {history}")
            
    #         retrieved_content = get_content_by_confirmation_token("test_confirm_token_xyz")
    #         logger.info(f"Retrieved content by token: {retrieved_content}")
    #         if retrieved_content:
    #             update_content_status(retrieved_content['id'], "posted", datetime.now())
    #             logger.info(f"Updated content status for ID {retrieved_content['id']}")
        
    #     active_users = get_active_users_with_topics()
    #     logger.info(f"Active users with topics: {active_users}")
        
    #     set_user_active_status(test_user['id'], False)
    #     logger.info(f"Set user inactive: {get_user_by_id(test_user['id'])}") 