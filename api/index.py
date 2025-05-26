import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import the Flask app
from main import app

# Configure for production
app.config['ENV'] = 'production'
app.config['DEBUG'] = False

# Update server name for production
vercel_url = os.environ.get('VERCEL_URL') or os.environ.get('VERCEL_PROJECT_PRODUCTION_URL')
if vercel_url:
    # Remove https:// prefix if present
    if vercel_url.startswith('https://'):
        vercel_url = vercel_url[8:]
    app.config['SERVER_NAME'] = vercel_url
    app.config['PREFERRED_URL_SCHEME'] = 'https'

# Ensure proper template and static folder paths for production
app.template_folder = os.path.join(project_root, 'templates')
app.static_folder = os.path.join(project_root, 'static')

# Export the app for Vercel
# This is the main export that Vercel will use
# Vercel will automatically handle WSGI
app = app

# For local testing
if __name__ == '__main__':
    app.run(debug=True) 