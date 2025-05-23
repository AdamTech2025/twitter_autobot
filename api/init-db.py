import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from flask import Flask, jsonify
import logging

# Import database functions
from app.database import init_db

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create a simple Flask app for database initialization
init_app = Flask(__name__)

@init_app.route('/api/init-db', methods=['POST'])
def initialize_database():
    """
    Initialize the database schema
    This should be called once after deployment to set up the PostgreSQL database
    """
    try:
        # Security check - only allow in production with proper environment
        if not os.environ.get('VERCEL_ENV'):
            return jsonify({
                "error": "Database initialization only allowed in production environment"
            }), 403
        
        # Check if PostgreSQL URL is available
        if not os.environ.get('POSTGRES_URL'):
            return jsonify({
                "error": "POSTGRES_URL environment variable is required"
            }), 500
        
        logger.info("Starting database initialization in production")
        
        # Initialize the database
        init_db()
        
        logger.info("Database initialization completed successfully")
        return jsonify({
            "success": True,
            "message": "Database initialized successfully",
            "database_type": "PostgreSQL"
        })
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@init_app.route('/api/init-db', methods=['GET'])
def check_database_status():
    """Check database connection and basic status"""
    try:
        from app.database import get_db_connection
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if os.environ.get('VERCEL_ENV'):
            # PostgreSQL status check
            cursor.execute("SELECT version();")
            db_version = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name IN ('users', 'ai_generated_content_history');")
            table_count = cursor.fetchone()[0]
        else:
            # SQLite status check
            cursor.execute("SELECT sqlite_version();")
            db_version = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name IN ('users', 'ai_generated_content_history');")
            table_count = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            "database_connected": True,
            "database_type": "PostgreSQL" if os.environ.get('VERCEL_ENV') else "SQLite",
            "database_version": db_version,
            "tables_exist": table_count == 2,
            "expected_tables": ["users", "ai_generated_content_history"]
        })
        
    except Exception as e:
        logger.error(f"Database status check failed: {e}")
        return jsonify({
            "database_connected": False,
            "error": str(e)
        }), 500

# Export the app for Vercel
app = init_app

if __name__ == '__main__':
    init_app.run(debug=True, port=5003) 