import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load .env from the root directory
# Adjust the number of os.path.dirname calls based on the location of .env relative to this file
# Assuming .env is in the root of the 'twitter_bot' project, two levels up from app/services/
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(dotenv_path=dotenv_path)

EMAIL_SENDER_ADDRESS = os.getenv('EMAIL_SENDER_ADDRESS')
EMAIL_SENDER_PASSWORD = os.getenv('EMAIL_SENDER_PASSWORD')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = os.getenv('SMTP_PORT')

def send_email(recipient_email, subject, body_html):
    if not all([EMAIL_SENDER_ADDRESS, EMAIL_SENDER_PASSWORD, SMTP_SERVER, SMTP_PORT]):
        print("Email credentials or server info not fully configured in .env. Cannot send email.")
        return False
    
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = EMAIL_SENDER_ADDRESS
    message["To"] = recipient_email

    # Attach HTML content
    part = MIMEText(body_html, "html")
    message.attach(part)

    try:
        smtp_port_int = int(SMTP_PORT)
        with smtplib.SMTP(SMTP_SERVER, smtp_port_int) as server:
            if smtp_port_int == 587: # Standard port for TLS
                server.starttls() 
            server.login(EMAIL_SENDER_ADDRESS, EMAIL_SENDER_PASSWORD)
            server.sendmail(EMAIL_SENDER_ADDRESS, recipient_email, message.as_string())
        print(f"Email sent successfully to {recipient_email} with subject '{subject}'.")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

if __name__ == '__main__':
    # Test email sending (ensure .env is configured)
    print("Testing email service...")
    if all([EMAIL_SENDER_ADDRESS, EMAIL_SENDER_PASSWORD, SMTP_SERVER, SMTP_PORT]):
        test_receiver = EMAIL_SENDER_ADDRESS # Send to self for testing
        subject = "Test Email from Tweet Bot"
        html_body = """
        <html>
            <body>
                <p>Hello,</p>
                <p>This is a <b>test email</b> from the Automated Tweet Generator application.</p>
                <p>If you received this, the email service is working!</p>
                <p>To confirm a tweet (this is just a test link pattern): 
                    <a href=\"http://127.0.0.1:5001/confirm-tweet/TEST_TOKEN\">Confirm Tweet</a>
                </p>
            </body>
        </html>
        """
        send_email(test_receiver, subject, html_body)
    else:
        print("Email sending credentials not configured in .env file. Skipping test.") 