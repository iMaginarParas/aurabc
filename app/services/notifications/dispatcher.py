import logging
import re
from sqlalchemy.orm import Session

from ...models import NotificationTemplate, WhatsAppNotification, UserNotificationPreference

logger = logging.getLogger(__name__)

# Configurable opt-in category mapping
EVENT_CATEGORY_MAP = {
    "ELIGIBILITY_COMPLETED": "eligibility",
    "PAYMENT_SUCCESS": "payments",
    "PAYMENT_FAILED": "payments",
    "SOP_GENERATED": "sop",
    "DOCUMENT_CHECK_COMPLETED": "documents",
    "CONSULTATION_BOOKED": "consultations",
    "CONSULTATION_REMINDER": "consultations",
    "STUDENT_REGISTERED": "account"
}

def dispatch_whatsapp_event(
    db: Session,
    user_id: str,
    event_type: str,
    payload: dict,
    phone_number: str = "+919891263337"
) -> WhatsAppNotification:
    """
    Checks user opt-in preferences, fetches active template, interpolates
    variables, logs the notification, and submits it to the processor queue.
    """
    logger.info(f"Dispatching event: {event_type} for user: {user_id}")

    # 1. Check user notifications preferences
    pref = db.query(UserNotificationPreference).filter(
        UserNotificationPreference.user_id == user_id
    ).first()

    category = EVENT_CATEGORY_MAP.get(event_type, "general")
    if pref:
        if not pref.enable_whatsapp:
            logger.info(f"Bypassing dispatch. WhatsApp notifications disabled globally for user {user_id}")
            return None
        if category not in pref.categories:
            logger.info(f"Bypassing dispatch. User opted out of category: {category}")
            return None

    # 2. Load the template
    tmpl = db.query(NotificationTemplate).filter(
        NotificationTemplate.event == event_type,
        NotificationTemplate.active == True
    ).first()

    if not tmpl:
        logger.warning(f"Active notification template for event {event_type} not found.")
        return None

    # 3. Interpolate parameters
    message = tmpl.template
    for key, val in payload.items():
        placeholder = f"{{{{{key}}}}}"
        message = message.replace(placeholder, str(val))

    # Clean any leftover un-interpolated placeholders
    message = re.sub(r"\{\{.*?\}\}", "", message)

    # 4. Insert pending database entry
    notif = WhatsAppNotification(
        user_id=user_id,
        event_type=event_type,
        phone_number=phone_number,
        template_name=tmpl.name,
        message=message,
        status="Pending",
        retry_count=0
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)

    # 5. Push to processor queue
    from .queue import process_notification_delivery
    process_notification_delivery(db, notif)

    return notif
