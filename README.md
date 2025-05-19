# AI-Powered Twitter Content Automation Bot

This project is a Flask-based web application that automates Twitter content generation and posting using AI, specifically leveraging the CrewAI framework. Users can connect their Twitter accounts, define topics of interest, and the bot will periodically generate relevant tweet suggestions. Users receive these suggestions via email and can approve them to be posted to their Twitter profile.

## Features

*   **Twitter OAuth 1.0a Integration:** Securely connect and authenticate users via their Twitter accounts.
*   **AI Content Generation:** Utilizes CrewAI to generate tweets based on user-defined topics and broader trending topics.
*   **Email Confirmation:** Sends email notifications to users with generated content, allowing them to review and approve tweets before posting.
*   **Scheduled Content Pipeline:** Uses APScheduler to run content generation jobs at predefined times.
*   **User-Friendly Web Interface:** Allows users to manage their connected Twitter account, email, and topics of interest.
*   **Tweet History:** Keeps a record of generated and posted content for each user.
*   **Environment-Based Configuration:** Securely manages API keys and settings using a `.env` file.

## Prerequisites

Before you begin, ensure you have the following installed and configured:

*   **Python 3.9+:** [Download Python](https://www.python.org/downloads/)
*   **pip:** Python package installer (usually comes with Python).
*   **Git:** For cloning the repository.
*   **Twitter Developer Account:** You\'ll need a Twitter App with API Key and Secret, and User Authentication (OAuth 1.0a) enabled.
    *   Ensure your Twitter App has **Read and Write permissions**.
    *   Set the **Callback URI / Redirect URL** in your Twitter App settings (e.g., `http://localhost:5001/twitter/callback` for local development).
*   **Email Account (SMTP):** For sending email notifications (e.g., Gmail, SendGrid, etc.). You\'ll need SMTP server details, port, sender email, and password.

## Setup Instructions

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd twitter_bot
    ```

2.  **Create and Activate a Virtual Environment:**
    *   **Windows:**
        ```bash
        python -m venv .venv
        .venv\\Scripts\\activate
        ```
    *   **macOS/Linux:**
        ```bash
        python3 -m venv .venv
        source .venv/bin/activate
        ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

The application uses a `.env` file to manage environment variables.

1.  **Create a `.env` file** in the root directory of the project (`twitter_bot/.env`).

2.  **Populate `.env` with your credentials and settings:**
    ```env
    # Flask Settings
    FLASK_SECRET_KEY="your_very_secret_flask_key_here" # Change this to a random string
    FLASK_SERVER_NAME="localhost:5001" # Or your domain if deploying
    FLASK_APPLICATION_ROOT="/"
    FLASK_PREFERRED_URL_SCHEME="http" # Use "https" if deploying with SSL

    # Twitter API Credentials (from your Twitter Developer App)
    TWITTER_API_KEY="your_twitter_api_key"
    TWITTER_API_SECRET_KEY="your_twitter_api_secret_key"
    # ACCESS_TOKEN and ACCESS_SECRET are typically for the app owner's context, not directly used for user OAuth flow in this bot.
    # However, some API endpoints might use them if the twitter_service.py is adapted.
    # ACCESS_TOKEN="your_app_owner_twitter_access_token" (Optional)
    # ACCESS_SECRET="your_app_owner_twitter_access_token_secret" (Optional)

    # IMPORTANT: Twitter Callback URL
    # This MUST match the callback URL set in your Twitter Developer App settings.
    # For local development, this is usually http://localhost:5001/twitter/callback
    TWITTER_CALLBACK_URL="http://localhost:5001/twitter/callback"

    # Email Service Configuration (e.g., for Gmail)
    EMAIL_SENDER_ADDRESS="your_email@example.com"
    EMAIL_SENDER_PASSWORD="your_email_password_or_app_password" # For Gmail, use an App Password
    SMTP_SERVER="smtp.gmail.com"
    SMTP_PORT="587" # Usually 587 for TLS or 465 for SSL

    # CrewAI/LLM API Keys (if your crew uses specific LLMs requiring API keys)
    # Example for OpenAI:
    OPENAI_API_KEY="sk-your_openai_api_key"
    # Add other LLM provider API keys as needed by your CrewAI setup, e.g.:
    # GROQ_API_KEY="your_groq_api_key"
    # ANTHROPIC_API_KEY="your_anthropic_api_key"

    # CrewAI Configuration (Optional - if you want to override defaults in crew.py)
    # Example: OPENAI_MODEL_NAME="gpt-4-turbo-preview"

    # Database path (default is twitter_bot.db in the root)
    DATABASE_URL="twitter_bot.db"
    ```

    **Important Notes:**
    *   Replace placeholder values with your actual credentials.
    *   **`FLASK_SECRET_KEY`**: Generate a strong, random secret key.
    *   **`TWITTER_CALLBACK_URL`**: This is critical for the OAuth flow. It must exactly match one of the URLs you configured in your Twitter App settings on the Twitter Developer Portal.
    *   **`EMAIL_SENDER_PASSWORD`**: If using Gmail, it\'s highly recommended to use an "App Password" instead of your main account password for security.
    *   Ensure your Twitter App on the developer portal has **"Read and Write"** permissions for posting tweets.

## Database Initialization

The application uses SQLite as its database. You need to initialize the database schema before running the app for the first time.

1.  Make sure your virtual environment is activated.
2.  Run the following command from the `twitter_bot` root directory:
    ```bash
    python -m app.database
    ```
    This will create a `twitter_bot.db` file (or the name specified in `DATABASE_URL`) in the project root with the necessary tables.

## Running the Application

1.  Ensure your virtual environment is activated and all configurations in `.env` are correct.
2.  Start the Flask development server:
    ```bash
    flask run --port 5001
    ```
    (The `--port 5001` is optional if `FLASK_SERVER_NAME` in your `.env` file already specifies the port and you want to use that default).

3.  Open your web browser and navigate to `http://localhost:5001` (or the URL configured).

## Usage

1.  **Connect Twitter:** On the homepage, click "Connect Twitter". You will be redirected to Twitter to authorize the application.
2.  **Set Preferences:**
    *   Once connected, you can enter your email address to receive notifications.
    *   Add topics of interest (comma-separated) that the AI will use to generate content.
    *   Click "Save Settings".
3.  **Content Generation & Confirmation:**
    *   The scheduler (`scheduled_content_generation_job` in `app/main.py`) runs at configured times (e.g., daily).
    *   It uses CrewAI to generate tweets based on your topics.
    *   If an email is configured, you\'ll receive an email with the generated tweet and a confirmation link.
    *   Clicking the confirmation link will post the tweet to your connected Twitter account.
4.  **View Tweet History:** The dashboard displays a history of your generated and posted tweets.
5.  **Disconnect Twitter:** You can disconnect your Twitter account from the application via the dashboard.

## Project Structure

\`\`\`
twitter_bot/
├── .venv/                  # Virtual environment files
├── app/                    # Core application logic
│   ├── services/           # Services (twitter_service.py, email_service.py)
│   ├── __init__.py
│   ├── crew.py             # CrewAI agent and task definitions
│   ├── database.py         # Database models and initialization
│   └── main.py             # Flask routes and main application logic
├── templates/              # HTML templates for the web interface
├── static/                 # Static files (CSS, JS, images - if any)
├── .env                    # Environment variables (Needs to be created manually)
├── requirements.txt        # Python package dependencies
├── twitter_bot.db          # SQLite database file (created after initialization)
└── README.md               # This file
\`\`\`

## Troubleshooting

*   **`jinja2.exceptions.UndefinedError: 'str object' has no attribute 'strftime'`**:
    This usually means a date field from the database wasn\'t properly converted to a datetime object before being passed to the template. Check the routes in `app/main.py` that render templates with date fields.
*   **Twitter API `403 Forbidden` error when posting:**
    *   Ensure your Twitter App in the Developer Portal has **"Read and Write"** permissions.
    *   If you recently changed permissions, you might need to disconnect and reconnect your Twitter account in the bot to refresh the OAuth tokens.
    *   Verify that the user whose tokens are being used has not had their access revoked or their account suspended.
*   **Emails not sending:**
    *   Double-check `EMAIL_SENDER_ADDRESS`, `EMAIL_SENDER_PASSWORD`, `SMTP_SERVER`, and `SMTP_PORT` in your `.env` file.
    *   For Gmail, ensure "Less secure app access" is enabled OR use an "App Password".
    *   Check your email provider\'s SMTP limits and security settings.
*   **OAuth Callback Issues:**
    *   Ensure `TWITTER_CALLBACK_URL` in `.env` exactly matches the URL registered in your Twitter App settings.
    *   Ensure `FLASK_SERVER_NAME` and `FLASK_PREFERRED_URL_SCHEME` are correctly set for `url_for` to generate absolute URLs when needed (especially for `_external=True`).

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue.

(Optional: Add sections on Deployment, Testing, etc., as your project evolves.) 