import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import the Flask app
from app.main import app

# Configure for production
app.config['ENV'] = 'production'
app.config['DEBUG'] = False

# Update server name for production
if os.environ.get('VERCEL_URL'):
    app.config['SERVER_NAME'] = os.environ.get('VERCEL_URL')
elif os.environ.get('VERCEL_PROJECT_PRODUCTION_URL'):
    app.config['SERVER_NAME'] = os.environ.get('VERCEL_PROJECT_PRODUCTION_URL')

# Export the app for Vercel
# Vercel expects either 'app' or 'handler' function
def handler(event, context):
    """AWS Lambda/Vercel compatible handler"""
    return app

# Direct app export for Vercel
# This is the main export that Vercel will use
app = app

# For local testing
if __name__ == '__main__':
    app.run(debug=True) 