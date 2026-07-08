from fastapi import APIRouter, Depends, HTTPException, Query, status
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from typing import List, Optional, Dict, Any
from ..database import SessionLocal
from ..auth import get_current_user
from ..models import (
    Notification, Appointment, WhatsAppNotification, EmailLog,
    SupportTicket, TicketMessage, Announcement, DownloadItem, CommunicationActivity
)

router = APIRouter(prefix="/api", tags=["Communication Center"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/inbox")
def get_unified_inbox(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieve the aggregated chronological activity feed of all inbox items."""
    user_id = user.get("sub") if user else "guest_user"
    
    # Grab latest activities
    activities = db.query(CommunicationActivity).filter(
        CommunicationActivity.user_id == user_id
    ).order_by(desc(CommunicationActivity.created_at)).limit(30).all()
    
    # Grab active announcements
    announcements = db.query(Announcement).filter(Announcement.is_active == True).order_by(desc(Announcement.created_at)).limit(5).all()
    
    # Unread notifications count
    unread_notifications = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False
    ).count()

    # Open support tickets count
    open_tickets = db.query(SupportTicket).filter(
        SupportTicket.user_id == user_id,
        SupportTicket.status.in_(["Open", "InProgress"])
    ).count()

    return {
        "activities": activities,
        "announcements": announcements,
        "unread_notifications_count": unread_notifications,
        "open_tickets_count": open_tickets
    }

@router.get("/notifications")
def get_notifications(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all notifications."""
    user_id = user.get("sub") if user else "guest_user"
    return db.query(Notification).filter(Notification.user_id == user_id).order_by(desc(Notification.created_at)).all()

@router.put("/notifications/read")
def mark_notifications_read(payload: Optional[Dict[str, Any]] = None, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Mark all or specific notifications as read."""
    user_id = user.get("sub") if user else "guest_user"
    notif_id = payload.get("notification_id") if payload else None

    if notif_id:
        n = db.query(Notification).filter(Notification.id == notif_id, Notification.user_id == user_id).first()
        if n:
            n.is_read = True
            db.commit()
    else:
        db.query(Notification).filter(Notification.user_id == user_id).update({Notification.is_read: True})
        db.commit()

    return {"status": "success"}

@router.get("/emails")
def get_emails(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """List transactional email history log."""
    user_id = user.get("sub") if user else "guest_user"
    return db.query(EmailLog).filter(EmailLog.user_id == user_id).order_by(desc(EmailLog.created_at)).all()

@router.get("/whatsapp")
def get_whatsapp(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """List WhatsApp message logs."""
    user_id = user.get("sub") if user else "guest_user"
    return db.query(WhatsAppNotification).filter(WhatsAppNotification.user_id == user_id).order_by(desc(WhatsAppNotification.created_at)).all()

@router.post("/whatsapp/{id}/retry")
def retry_failed_whatsapp(id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retry sending a failed WhatsApp message by resetting status to 'Sent'."""
    user_id = user.get("sub") if user else "guest_user"
    wa = db.query(WhatsAppNotification).filter(WhatsAppNotification.id == id, WhatsAppNotification.user_id == user_id).first()
    
    if not wa:
        raise HTTPException(status_code=404, detail="WhatsApp message log not found")
        
    if wa.status != "Failed":
        raise HTTPException(status_code=400, detail="Only failed messages can be retried")
        
    # Reset status and increment retry count
    wa.status = "Sent"
    wa.retry_count = (wa.retry_count or 0) + 1
    wa.updated_at = datetime.utcnow()
    db.commit()
    
    return {"status": "success", "message": "Message retry logged successfully", "data": wa}

@router.get("/support")
def get_support_tickets(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """List user support tickets."""
    user_id = user.get("sub") if user else "guest_user"
    return db.query(SupportTicket).filter(SupportTicket.user_id == user_id).order_by(desc(SupportTicket.created_at)).all()

@router.post("/support")
def create_support_ticket(payload: Dict[str, Any], user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Open a new support ticket."""
    user_id = user.get("sub") if user else "guest_user"
    title = payload.get("title")
    category = payload.get("category", "General")
    priority = payload.get("priority", "Medium")
    initial_message = payload.get("message")

    if not title or not initial_message:
        raise HTTPException(status_code=400, detail="Missing title or message body")

    ticket = SupportTicket(
        user_id=user_id,
        title=title,
        category=category,
        priority=priority,
        status="Open"
    )
    db.add(ticket)
    db.flush()

    msg = TicketMessage(
        ticket_id=ticket.id,
        sender_id=user_id,
        sender_role="student",
        message=initial_message
    )
    db.add(msg)
    db.commit()
    db.refresh(ticket)

    # Log to activities
    try:
        from ..services.communication_service import log_activity
        log_activity(db, user_id, "ticket", f"New Ticket: {title}", ticket.id)
    except Exception as e:
        db.rollback()

    return ticket

@router.get("/support/{id}")
def get_support_ticket_details(id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """View support ticket messages thread."""
    user_id = user.get("sub") if user else "guest_user"
    ticket = db.query(SupportTicket).filter(SupportTicket.id == id, SupportTicket.user_id == user_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")
        
    messages = db.query(TicketMessage).filter(TicketMessage.ticket_id == id).order_by(TicketMessage.created_at).all()
    
    return {
        "ticket": ticket,
        "messages": messages
    }

@router.post("/support/{id}/message")
def reply_to_ticket(id: str, payload: Dict[str, Any], user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Send reply message on support ticket."""
    user_id = user.get("sub") if user else "guest_user"
    message_text = payload.get("message")
    
    if not message_text:
        raise HTTPException(status_code=400, detail="Message body is required")
        
    ticket = db.query(SupportTicket).filter(SupportTicket.id == id, SupportTicket.user_id == user_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")
        
    # Reopen ticket if closed
    if ticket.status == "Closed":
        ticket.status = "Open"
        
    msg = TicketMessage(
        ticket_id=id,
        sender_id=user_id,
        sender_role="student",
        message=message_text
    )
    db.add(msg)
    ticket.updated_at = datetime.utcnow()
    db.commit()
    
    return msg

@router.put("/support/{id}")
def update_ticket_status(id: str, payload: Dict[str, Any], user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Close or resolve support ticket status."""
    user_id = user.get("sub") if user else "guest_user"
    status_val = payload.get("status")

    if status_val not in ["Resolved", "Closed"]:
        raise HTTPException(status_code=400, detail="Invalid status transition")

    ticket = db.query(SupportTicket).filter(SupportTicket.id == id, SupportTicket.user_id == user_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.status = status_val
    ticket.updated_at = datetime.utcnow()
    db.commit()
    
    return ticket

@router.get("/downloads")
def get_downloadable_files(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieve downloadable reports/invoices catalog."""
    user_id = user.get("sub") if user else "guest_user"
    return db.query(DownloadItem).filter(DownloadItem.user_id == user_id).order_by(desc(DownloadItem.created_at)).all()

@router.get("/appointments")
def get_appointments(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieve the consultations schedule bookings."""
    user_id = user.get("sub") if user else "guest_user"
    return db.query(Appointment).filter(Appointment.user_id == user_id).order_by(desc(Appointment.date_time)).all()

@router.get("/announcements")
def get_global_announcements(db: Session = Depends(get_db)):
    """List active announcements."""
    return db.query(Announcement).filter(Announcement.is_active == True).order_by(desc(Announcement.created_at)).all()
