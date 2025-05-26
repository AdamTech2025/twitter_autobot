import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from flask import Flask, jsonify, request
import logging
from datetime import datetime, timezone
import json
import uuid

# Import the scheduled job function from main
from main import scheduled_content_generation_job, app

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create a simple Flask app for cron endpoints
cron_app = Flask(__name__)

@cron_app.route('/api/cron/content-generation', methods=['POST'])
def trigger_content_generation():
    """
    Vercel Cron Job endpoint for scheduled content generation
    This endpoint should be called by Vercel Cron Jobs at scheduled intervals
    """
    try:
        # Verify the request is from Vercel Cron (optional security)
        auth_header = request.headers.get('Authorization')
        cron_secret = os.environ.get('CRON_SECRET')
        
        if cron_secret and auth_header != f"Bearer {cron_secret}":
            logger.warning("Unauthorized cron job request")
            return jsonify({"error": "Unauthorized"}), 401
        
        logger.info("Starting scheduled content generation via Vercel Cron")
        
        # Run the content generation job within Flask app context
        with app.app_context():
            scheduled_content_generation_job()
        
        logger.info("Scheduled content generation completed successfully")
        return jsonify({
            "success": True, 
            "message": "Content generation job completed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in scheduled content generation: {e}", exc_info=True)
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
        "service": "twitter-bot-cron"
    })

# Export the app for Vercel
app = cron_app

if __name__ == '__main__':
    cron_app.run(debug=True, port=5002) 