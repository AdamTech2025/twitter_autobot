import sqlite3
import os
import logging
from datetime import datetime

# Database configuration for both development and production
# Check if we have a Neon database URL (for production/cloud deployment)
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL') or os.environ.get('NEON_DATABASE_URL')

if DATABASE_URL:
    # Production environment - use PostgreSQL (Neon or other)
    try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
        USE_POSTGRES = True
        logger = logging.getLogger(__name__)
        logger.info("Using PostgreSQL database (Neon) in production")
    except ImportError:
    logger = logging.getLogger(__name__)
        logger.error("psycopg2 not installed but DATABASE_URL provided. Install with: pip install psycopg2-binary")
        raise
else:
    # Development environment - use SQLite
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'twitter_bot.db')
    USE_POSTGRES = False
    logger = logging.getLogger(__name__)
    logger.info("Using SQLite database in development")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Get database connection - PostgreSQL for Neon, SQLite for development"""
    if USE_POSTGRES:
        # PostgreSQL connection for Neon database
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    else:
        # SQLite connection for development
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    """Initialize database with proper schema for both PostgreSQL and SQLite"""
    if USE_POSTGRES:
        logger.info("Initializing PostgreSQL database (Neon)")
        conn = get_db_connection()
        cursor = conn.cursor()

        # PostgreSQL schema
        cursor.execute("DROP TABLE IF EXISTS ai_generated_content_history CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS users CASCADE;")
        logger.info("Dropped existing tables (PostgreSQL).")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            twitter_id VARCHAR(50) UNIQUE NOT NULL,
            screen_name VARCHAR(100) NOT NULL,
            oauth_token TEXT NOT NULL,
            oauth_token_secret TEXT NOT NULL,
            email VARCHAR(255),
            topics TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        logger.info("Created users table (PostgreSQL).")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_generated_content_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            generated_content TEXT NOT NULL,
            status VARCHAR(50) NOT NULL,
            confirmation_token VARCHAR(100) UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            posted_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """)
        logger.info("Created ai_generated_content_history table (PostgreSQL).")
        
        # PostgreSQL trigger for updated_at
        cursor.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """)
        
        cursor.execute("""
        DROP TRIGGER IF EXISTS update_users_updated_at ON users;
        CREATE TRIGGER update_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """)
        logger.info("Created update_users_updated_at trigger (PostgreSQL).")

        conn.commit()
        conn.close()
        logger.info("PostgreSQL database initialization complete.")
    else:
        # SQLite initialization (existing code)
        logger.info(f"Initializing SQLite database at {DATABASE_PATH}")
        if not os.path.exists(os.path.dirname(DATABASE_PATH)):
            os.makedirs(os.path.dirname(DATABASE_PATH))
            logger.info(f"Created directory {os.path.dirname(DATABASE_PATH)}")
            
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DROP TABLE IF EXISTS tweet_history;")
        cursor.execute("DROP TABLE IF EXISTS ai_generated_content_history;")
        cursor.execute("DROP TABLE IF EXISTS users;") 
        logger.info("Dropped existing tables (SQLite).")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            twitter_id TEXT UNIQUE NOT NULL,
            screen_name TEXT NOT NULL,
            oauth_token TEXT NOT NULL,
            oauth_token_secret TEXT NOT NULL,
            email TEXT,
            topics TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)
        logger.info("Created users table (SQLite).")

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
        logger.info("Created ai_generated_content_history table (SQLite).")
        
        cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS update_users_updated_at
        AFTER UPDATE ON users
        FOR EACH ROW
        BEGIN
            UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END;
        """)
        logger.info("Created update_users_updated_at trigger (SQLite).")

        conn.commit()
        conn.close()
        logger.info("SQLite database initialization complete.")

# --- User Functions ---
def create_or_update_user(twitter_id, screen_name, oauth_token, oauth_token_secret, email=None, topics=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Use appropriate parameter placeholder for database type
        param_placeholder = "%s" if USE_POSTGRES else "?"
        
        cursor.execute(f"SELECT id, topics FROM users WHERE twitter_id = {param_placeholder}", (twitter_id,))
        user_row = cursor.fetchone()

        final_topics = topics

        if user_row:
            user_id = user_row['id']
            logger.info(f"Updating existing user for twitter_id {twitter_id} (Internal ID: {user_id}).")
            if topics is None:
                final_topics = user_row['topics'] 

            if USE_POSTGRES:
                # PostgreSQL update
                cursor.execute("""
                    UPDATE users 
                    SET screen_name = %s, oauth_token = %s, oauth_token_secret = %s, 
                        email = %s, topics = %s, is_active = TRUE, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (screen_name, oauth_token, oauth_token_secret, email, final_topics, user_id))
            else:
                # SQLite update
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
            if USE_POSTGRES:
                # PostgreSQL insert
                cursor.execute("""
                    INSERT INTO users (twitter_id, screen_name, oauth_token, oauth_token_secret, email, topics, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE) RETURNING id
                """, (twitter_id, screen_name, oauth_token, oauth_token_secret, email, final_topics))
                user_id = cursor.fetchone()['id']
            else:
                # SQLite insert
                cursor.execute("""
                    INSERT INTO users (twitter_id, screen_name, oauth_token, oauth_token_secret, email, topics, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, TRUE)
                """, (twitter_id, screen_name, oauth_token, oauth_token_secret, email, final_topics))
                user_id = cursor.lastrowid
        
        conn.commit()
        logger.info(f"Successfully created/updated user: Twitter ID {twitter_id}, Internal ID {user_id}")
        return get_user_by_id(user_id)
    except Exception as e:
        logger.error(f"Database error in create_or_update_user for twitter_id {twitter_id}: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

def get_user_by_id(user_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        param_placeholder = "%s" if USE_POSTGRES else "?"
        cursor.execute(f"SELECT * FROM users WHERE id = {param_placeholder}", (user_id,))
        user = cursor.fetchone()
        return dict(user) if user else None
    finally:
        conn.close()

def get_user_by_twitter_id(twitter_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        param_placeholder = "%s" if USE_POSTGRES else "?"
        cursor.execute(f"SELECT * FROM users WHERE twitter_id = {param_placeholder}", (twitter_id,))
        user = cursor.fetchone()
        return dict(user) if user else None
    finally:
        conn.close()

def update_user_email(user_id, email):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        email_to_store = email if email and email.strip() else None
        
        if USE_POSTGRES:
            cursor.execute("UPDATE users SET email = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (email_to_store, user_id))
        else:
            cursor.execute("UPDATE users SET email = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (email_to_store, user_id))
        
        conn.commit()
        logger.info(f"Updated email for user ID {user_id} to '{email_to_store}'")
        return True
    except Exception as e:
        logger.error(f"Database error in update_user_email for user ID {user_id}: {e}")
        return False
    finally:
        conn.close()

# Renamed from update_user_schedule to update_user_topics as schedule_times is removed
def update_user_topics(user_id, topics_json):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if USE_POSTGRES:
            cursor.execute("UPDATE users SET topics = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (topics_json, user_id))
        else:
            cursor.execute("UPDATE users SET topics = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (topics_json, user_id))
        
        conn.commit()
        logger.info(f"Updated topics for user ID {user_id}.")
        return True
    except Exception as e:
        logger.error(f"Database error in update_user_topics for user ID {user_id}: {e}")
        return False
    finally:
        conn.close()

def set_user_active_status(user_id, is_active):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if USE_POSTGRES:
            cursor.execute("UPDATE users SET is_active = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (is_active, user_id))
        else:
            cursor.execute("UPDATE users SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (is_active, user_id))
        
        conn.commit()
        logger.info(f"Set active status for user ID {user_id} to {is_active}")
        return True
    except Exception as e:
        logger.error(f"Database error in set_user_active_status for user ID {user_id}: {e}")
        return False
    finally:
        conn.close()

# Renamed from get_active_users_with_schedules to get_active_users_with_topics
def get_active_users_with_topics():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM users 
            WHERE is_active = TRUE AND topics IS NOT NULL AND topics != '' AND topics != '[]'
        """)
        users = [dict(row) for row in cursor.fetchall()]
        logger.info(f"Found {len(users)} active users with topics.")
        return users
    except Exception as e:
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
        if USE_POSTGRES:
            # PostgreSQL
            cursor.execute("""
                INSERT INTO ai_generated_content_history (user_id, generated_content, status, confirmation_token)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (user_id, generated_content, status, confirmation_token))
            content_id = cursor.fetchone()['id']
        else:
            # SQLite
            cursor.execute("""
                INSERT INTO ai_generated_content_history (user_id, generated_content, status, confirmation_token)
                VALUES (?, ?, ?, ?)
            """, (user_id, generated_content, status, confirmation_token))
            content_id = cursor.lastrowid
        
        conn.commit()
        logger.info(f"Added generated content to history for user ID {user_id}. Content ID: {content_id}, Status: {status}")
        return content_id
    except Exception as e:
        logger.error(f"Database error in add_generated_content for user ID {user_id}: {e}")
        return None
    finally:
        conn.close()

def get_history_by_user_id(user_id, limit=20):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        param_placeholder = "%s" if USE_POSTGRES else "?"
        cursor.execute(f"""
            SELECT h.*, u.screen_name FROM ai_generated_content_history h
            JOIN users u ON h.user_id = u.id
            WHERE h.user_id = {param_placeholder}
            ORDER BY h.created_at DESC 
            LIMIT {param_placeholder}
        """, (user_id, limit))
        history = [dict(row) for row in cursor.fetchall()]
        return history
    except Exception as e:
        logger.error(f"Database error in get_history_by_user_id for user_id {user_id}: {e}")
        return []
    finally:
        conn.close()

def get_content_by_confirmation_token(confirmation_token):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        param_placeholder = "%s" if USE_POSTGRES else "?"
        cursor.execute(f"""
            SELECT h.*, u.screen_name, u.oauth_token, u.oauth_token_secret, u.email as user_email, u.is_active as user_is_active
            FROM ai_generated_content_history h
            JOIN users u ON h.user_id = u.id
            WHERE h.confirmation_token = {param_placeholder}
        """, (confirmation_token,))
        content = cursor.fetchone()
        return dict(content) if content else None
    except Exception as e:
        logger.error(f"Database error in get_content_by_confirmation_token for token {confirmation_token}: {e}")
        return None
    finally:
        conn.close()

def update_content_status(content_id, status, posted_at=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if USE_POSTGRES:
            # PostgreSQL
            if posted_at:
                cursor.execute("UPDATE ai_generated_content_history SET status = %s, posted_at = %s WHERE id = %s", (status, posted_at, content_id))
            else:
                cursor.execute("UPDATE ai_generated_content_history SET status = %s WHERE id = %s", (status, content_id))
        else:
            # SQLite
            if posted_at:
                cursor.execute("UPDATE ai_generated_content_history SET status = ?, posted_at = ? WHERE id = ?", (status, posted_at, content_id))
            else:
                cursor.execute("UPDATE ai_generated_content_history SET status = ? WHERE id = ?", (status, content_id))
        
        conn.commit()
        logger.info(f"Updated status for content ID {content_id} to {status}")
        return True
    except Exception as e:
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