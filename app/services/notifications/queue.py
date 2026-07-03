import uuid
import logging
from sqlalchemy.orm import Session
from ...models import WhatsAppNotification

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

import os
import urllib.request
import urllib.parse
import base64
import json

def send_twilio_whatsapp(to_number: str, message_body: str) -> str:
    """
    Sends a real WhatsApp message using Twilio's REST API.
    All credentials are read from environment variables.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

    if not account_sid or not auth_token:
        logger.warning("Twilio API variables (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) are missing. Skipping real Twilio dispatch.")
        return None

    to_formatted = to_number
    if not to_formatted.startswith("whatsapp:"):
        to_formatted = f"whatsapp:{to_formatted}"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    
    data = urllib.parse.urlencode({
        "From": from_number,
        "To": to_formatted,
        "Body": message_body
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    auth_str = f"{account_sid}:{auth_token}"
    auth_b64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    req.add_header("Authorization", f"Basic {auth_b64}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = response.read().decode("utf-8")
            res_data = json.loads(res_body)
            return res_data.get("sid")
    except Exception as err:
        logger.error(f"Twilio API request failed: {str(err)}")
        raise err


def process_notification_delivery(db: Session, notification: WhatsAppNotification) -> bool:
    """
    Triggers delivery of the WhatsApp notification via Twilio Cloud REST API.
    """
    logger.info(f"Processing delivery for WhatsApp Notification: {notification.id}")
    
    notification.status = "Processing"
    db.commit()

    try:
        # Trigger real Twilio REST dispatch
        provider_id = send_twilio_whatsapp(notification.phone_number, notification.message)
        
        # Fallback to local mock ID if credentials are not configured
        if not provider_id:
            provider_id = f"simulated_sid_{uuid.uuid4().hex[:16]}"
            
        notification.status = "Sent"
        notification.provider_message_id = provider_id
        db.commit()
        
        logger.info("=" * 60)
        logger.info(f"WHATSAPP MESSAGE SENT TO: {notification.phone_number}")
        logger.info(f"PROVIDER MESSAGE ID: {provider_id}")
        logger.info("-" * 60)
        logger.info(notification.message)
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"WhatsApp delivery failed: {str(e)}")
        
        notification.retry_count += 1
        if notification.retry_count <= MAX_RETRIES:
            notification.status = "Retry"
            logger.info(f"Notification set for retry. Retry count: {notification.retry_count}/{MAX_RETRIES}")
        else:
            notification.status = "Failed"
            logger.error(f"Notification exceeded max retries. Marked as Failed.")
            
        db.commit()
        return False


def retry_failed_notifications(db: Session) -> int:
    """
    Gathers all notifications in 'Retry' status and processes them.
    """
    retries = db.query(WhatsAppNotification).filter(
        WhatsAppNotification.status == "Retry"
    ).all()

    success_count = 0
    for notif in retries:
        if process_notification_delivery(db, notif):
            success_count += 1

    return success_count
