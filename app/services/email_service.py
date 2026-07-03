import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Sends a real production-ready email using standard SMTP.
    Fallback values are read from environment variables.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    sender_email = os.getenv("SUPPORT_EMAIL", "support@auraroutes.com")

    if not all([smtp_host, smtp_port, smtp_user, smtp_pass]):
        logger.warning("SMTP configuration is incomplete. Skipping actual email delivery.")
        # Print for development visibility
        logger.info(f"Simulated email details:\nTo: {to_email}\nSubject: {subject}\nSender: {sender_email}")
        return False

    try:
        # Create message container
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = to_email

        # Attach HTML body content
        msg.attach(MIMEText(html_content, "html"))

        # Setup secure SMTP connection
        port = int(smtp_port)
        logger.info(f"Connecting to SMTP server {smtp_host}:{port}...")
        
        server = smtplib.SMTP(smtp_host, port)
        server.ehlo()
        server.starttls()  # Upgrade connection to secure TLS encryption
        server.ehlo()
        
        server.login(smtp_user, smtp_pass)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        
        logger.info(f"Email successfully delivered to: {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to deliver SMTP email to {to_email}: {str(e)}")
        return False
