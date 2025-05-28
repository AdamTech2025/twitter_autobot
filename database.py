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
            logger.info(f"Creating new user for twitter_id {twitter_id}.")
            if USE_POSTGRES:
                # PostgreSQL insert
                cursor.execute("""
                    INSERT INTO users (twitter_id, screen_name, oauth_token, oauth_token_secret, email, topics, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                    RETURNING id
                """, (twitter_id, screen_name, oauth_token, oauth_token_secret, email, final_topics))
                user_id = cursor.fetchone()['id']
            else:
                # SQLite insert
                cursor.execute("""
                    INSERT INTO users (twitter_id, screen_name, oauth_token, oauth_token_secret, email, topics, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                """, (twitter_id, screen_name, oauth_token, oauth_token_secret, email, final_topics))
                user_id = cursor.lastrowid

        conn.commit()
        
        # Return the user record
        cursor.execute(f"SELECT * FROM users WHERE id = {param_placeholder}", (user_id,))
        user_record = cursor.fetchone()
        return dict(user_record) if user_record else None

    except Exception as e:
        logger.error(f"Error in create_or_update_user: {e}", exc_info=True)
        conn.rollback()
        return None
    finally:
        conn.close()

def get_user_by_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        param_placeholder = "%s" if USE_POSTGRES else "?"
        cursor.execute(f"SELECT * FROM users WHERE id = {param_placeholder}", (user_id,))
        user_row = cursor.fetchone()
        return dict(user_row) if user_row else None
    except Exception as e:
        logger.error(f"Error getting user by ID {user_id}: {e}", exc_info=True)
        return None
    finally:
        conn.close()

def get_user_by_twitter_id(twitter_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        param_placeholder = "%s" if USE_POSTGRES else "?"
        cursor.execute(f"SELECT * FROM users WHERE twitter_id = {param_placeholder}", (twitter_id,))
        user_row = cursor.fetchone()
        return dict(user_row) if user_row else None
    except Exception as e:
        logger.error(f"Error getting user by Twitter ID {twitter_id}: {e}", exc_info=True)
        return None
    finally:
        conn.close()

def update_user_email(user_id, email):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if USE_POSTGRES:
            cursor.execute("""
                UPDATE users 
                SET email = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (email, user_id))
        else:
            cursor.execute("""
                UPDATE users 
                SET email = ?, updated_at = ? 
                WHERE id = ?
            """, (email, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating email for user {user_id}: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        conn.close()

def update_user_topics(user_id, topics_json):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if USE_POSTGRES:
            cursor.execute("""
                UPDATE users 
                SET topics = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (topics_json, user_id))
        else:
            cursor.execute("""
                UPDATE users 
                SET topics = ?, updated_at = ? 
                WHERE id = ?
            """, (topics_json, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating topics for user {user_id}: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        conn.close()

def set_user_active_status(user_id, is_active):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if USE_POSTGRES:
            cursor.execute("""
                UPDATE users 
                SET is_active = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (is_active, user_id))
        else:
            cursor.execute("""
                UPDATE users 
                SET is_active = ?, updated_at = ? 
                WHERE id = ?
            """, (is_active, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating active status for user {user_id}: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        conn.close()

def get_active_users_with_topics():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM users 
            WHERE is_active = TRUE 
            AND topics IS NOT NULL 
            AND topics != '' 
            AND topics != '[]'
        """)
        users = cursor.fetchall()
        return [dict(user) for user in users]
    except Exception as e:
        logger.error(f"Error getting active users with topics: {e}", exc_info=True)
        return []
    finally:
        conn.close()

def add_generated_content(user_id, generated_content, status, confirmation_token=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if USE_POSTGRES:
            cursor.execute("""
                INSERT INTO ai_generated_content_history 
                (user_id, generated_content, status, confirmation_token)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (user_id, generated_content, status, confirmation_token))
            content_id = cursor.fetchone()['id']
        else:
            cursor.execute("""
                INSERT INTO ai_generated_content_history 
                (user_id, generated_content, status, confirmation_token)
                VALUES (?, ?, ?, ?)
            """, (user_id, generated_content, status, confirmation_token))
            content_id = cursor.lastrowid
        
        conn.commit()
        logger.info(f"Added generated content to history for user ID {user_id}. Content ID: {content_id}, Status: {status}")
        return content_id
    except Exception as e:
        logger.error(f"Error adding generated content for user {user_id}: {e}", exc_info=True)
        conn.rollback()
        return None
    finally:
        conn.close()

def get_history_by_user_id(user_id, limit=20):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        param_placeholder = "%s" if USE_POSTGRES else "?"
        cursor.execute(f"""
            SELECT * FROM ai_generated_content_history 
            WHERE user_id = {param_placeholder}
            ORDER BY created_at DESC 
            LIMIT {param_placeholder}
        """, (user_id, limit))
        history = cursor.fetchall()
        return [dict(item) for item in history]
    except Exception as e:
        logger.error(f"Error getting history for user {user_id}: {e}", exc_info=True)
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
        logger.error(f"Error getting content by token {confirmation_token}: {e}", exc_info=True)
        return None
    finally:
        conn.close()

def update_content_status(content_id, status, posted_at=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if USE_POSTGRES:
            if posted_at:
                cursor.execute("""
                    UPDATE ai_generated_content_history 
                    SET status = %s, posted_at = %s 
                    WHERE id = %s
                """, (status, posted_at, content_id))
            else:
                cursor.execute("""
                    UPDATE ai_generated_content_history 
                    SET status = %s 
                    WHERE id = %s
                """, (status, content_id))
        else:
            if posted_at:
                cursor.execute("""
                    UPDATE ai_generated_content_history 
                    SET status = ?, posted_at = ? 
                    WHERE id = ?
                """, (status, posted_at.strftime("%Y-%m-%d %H:%M:%S") if posted_at else None, content_id))
            else:
                cursor.execute("""
                    UPDATE ai_generated_content_history 
                    SET status = ? 
                    WHERE id = ?
                """, (status, content_id))
        
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating content status for ID {content_id}: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        conn.close()

# Initialize database on import (for development)
if not USE_POSTGRES and not os.path.exists(DATABASE_PATH):
    logger.info("Database file doesn't exist, initializing...")
    init_db() 