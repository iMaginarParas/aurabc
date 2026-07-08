import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Dict, Any

from ..database import get_db
from ..models import (
    NotificationTemplate,
    WhatsAppNotification,
    UserNotificationPreference
)
from ..schemas import (
    WhatsAppNotificationResponse,
    NotificationTemplateResponse,
    NotificationTemplateUpdate,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate
)
from ..services.notifications.dispatcher import dispatch_whatsapp_event
from ..services.notifications.queue import process_notification_delivery, retry_failed_notifications

logger = logging.getLogger(__name__)
router = APIRouter(tags=["notifications"])


@router.post("/api/notifications/event", status_code=status.HTTP_202_ACCEPTED)
def trigger_notification_event(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Triggers a platform notification event, variable interpolator compile, and queues message.
    Payload keys:
      - "event_type": ELIGIBILITY_COMPLETED, PAYMENT_SUCCESS, SOP_GENERATED, etc.
      - "phone_number": e.g., "+919891263337"
      - "variables": Dict of keys/values (e.g. {"student_name": "John", "amount": "₹999"})
    """
    event_type = payload.get("event_type")
    phone = payload.get("phone_number", "+919891263337")
    variables = payload.get("variables", {})

    if not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing event_type parameter."
        )

    # Compile student_name fallback if missing
    if "student_name" not in variables:
        variables["student_name"] = "Student Partner"

    notif = dispatch_whatsapp_event(
        db,
        user_id="guest_user",
        event_type=event_type,
        payload=variables,
        phone_number=phone
    )

    if not notif:
        return {"status": "bypassed", "detail": "Opted out or active template missing."}

    return {"status": "queued", "notification_id": notif.id, "delivery_status": notif.status}


@router.post("/api/notifications/send", response_model=WhatsAppNotificationResponse, status_code=status.HTTP_201_CREATED)
def direct_send_message(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Sends a direct message bypassing preferences filters (admin/direct alerts tool).
    """
    phone = payload.get("phone_number")
    msg_content = payload.get("message")
    event = payload.get("event_type", "DIRECT_ALERT")

    if not phone or not msg_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number and message content required."
        )

    notif = WhatsAppNotification(
        user_id="guest_user",
        event_type=event,
        phone_number=phone,
        template_name="Direct Override",
        message=msg_content,
        status="Pending"
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)

    # Process immediately
    process_notification_delivery(db, notif)
    return notif


@router.get("/api/notifications/history", response_model=List[WhatsAppNotificationResponse])
def get_notifications_history(db: Session = Depends(get_db)):
    """
    Fetches the WhatsApp notification log history for the current user.
    """
    return db.query(WhatsAppNotification).filter(
        WhatsAppNotification.user_id == "guest_user"
    ).order_by(desc(WhatsAppNotification.created_at)).all()


@router.get("/api/notifications/templates", response_model=List[NotificationTemplateResponse])
def get_notification_templates(db: Session = Depends(get_db)):
    """
    Lists all seeded WhatsApp notification templates (for admin configs).
    """
    return db.query(NotificationTemplate).all()


@router.put("/api/notifications/template/{tmpl_id}", response_model=NotificationTemplateResponse)
def update_notification_template(
    tmpl_id: str,
    payload: NotificationTemplateUpdate,
    db: Session = Depends(get_db)
):
    """
    Edits a template variable body content or toggles active status.
    """
    tmpl = db.query(NotificationTemplate).filter(NotificationTemplate.id == tmpl_id).first()
    if not tmpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification template not found."
        )

    tmpl.template = payload.template
    tmpl.active = payload.active
    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.post("/api/notifications/retry")
def trigger_retry_queue(db: Session = Depends(get_db)):
    """
    Manually triggers process loop retries for failed 'Retry' messages.
    """
    retry_count = retry_failed_notifications(db)
    return {"message": "Retry queue processed.", "successful_retries": retry_count}


@router.post("/api/notifications/retry/{notif_id}", response_model=WhatsAppNotificationResponse)
def retry_single_notification(notif_id: str, db: Session = Depends(get_db)):
    """
    Manually retries a specific failed notification logs.
    """
    notif = db.query(WhatsAppNotification).filter(WhatsAppNotification.id == notif_id).first()
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification log entry not found."
        )

    # Force status reset
    notif.status = "Pending"
    db.commit()

    process_notification_delivery(db, notif)
    return notif


# OPT-IN USER PREFERENCES ENDPOINTS
@router.get("/api/notifications/preferences", response_model=NotificationPreferenceResponse)
def get_notification_preferences(db: Session = Depends(get_db)):
    """
    Fetches the notification preference settings for the current user.
    """
    pref = db.query(UserNotificationPreference).filter(
        UserNotificationPreference.user_id == "guest_user"
    ).first()

    if not pref:
        # Spin up defaults
        pref = UserNotificationPreference(
            user_id="guest_user",
            enable_whatsapp=True,
            categories=["eligibility", "payments", "sop", "documents", "consultations", "account", "general"]
        )
        db.add(pref)
        db.commit()
        db.refresh(pref)

    return pref


@router.put("/api/notifications/preferences", response_model=NotificationPreferenceResponse)
def update_notification_preferences(
    payload: NotificationPreferenceUpdate,
    db: Session = Depends(get_db)
):
    """
    Updates WhatsApp enable flags and category categories list.
    """
    pref = db.query(UserNotificationPreference).filter(
        UserNotificationPreference.user_id == "guest_user"
    ).first()

    if not pref:
        pref = UserNotificationPreference(user_id="guest_user")
        db.add(pref)

    pref.enable_whatsapp = payload.enable_whatsapp
    pref.categories = payload.categories
    db.commit()
    db.refresh(pref)
    return pref
