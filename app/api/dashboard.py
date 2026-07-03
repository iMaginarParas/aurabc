import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Dict, Any

from ..database import get_db
from ..auth import get_current_user
from ..models import (
    EligibilityRequest,
    Order,
    Service,
    Payment,
    SOPDocument,
    VisaDocumentCheck,
    UploadedDocument,
    Notification,
    Appointment,
    DashboardActivity,
    UserSetting
)
from ..schemas import (
    NotificationResponse,
    AppointmentResponse,
    DashboardActivityResponse,
    UserSettingResponse,
    UserSettingUpdate,
    StudentProfileResponse,
    StudentProfileUpdate,
    DashboardOverviewResponse,
    UploadedDocumentResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Assembles overall statistics, active payments, notifications, and calendars.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    user_email = current_user.get("email")

    # 1. Profile completeness calculation
    profile = db.query(EligibilityRequest).filter(EligibilityRequest.email == user_email).first()
    completeness = 40  # Default fallback base score
    if profile:
        score = 0
        fields = [
            profile.full_name, profile.email, profile.phone,
            profile.country_residence, profile.nationality, profile.qualification,
            profile.preferred_country, profile.preferred_course,
            profile.preferred_intake, profile.budget_range
        ]
        for field in fields:
            if field:
                score += 10
        completeness = max(score, 40)

    # 2. Purchased premium services slugs
    paid_services = db.query(Service.slug).join(Order).filter(
        Order.payment_status == "paid",
        Order.user_id == user_id
    ).all()
    purchased_slugs = [item[0] for item in paid_services]

    # 3. Aggregates counts
    unread_notifications = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False
    ).count()

    sop_count = db.query(SOPDocument).filter(SOPDocument.user_id == user_id).count()
    visa_count = db.query(VisaDocumentCheck).filter(
        VisaDocumentCheck.user_id == user_id,
        VisaDocumentCheck.readiness_score > 0
    ).count()
    total_drafts = sop_count + visa_count

    total_payments = db.query(Payment).join(Order).filter(Order.user_id == user_id).count()

    # 4. Logs checklists
    recent_activities = db.query(DashboardActivity).filter(
        DashboardActivity.user_id == user_id
    ).order_by(desc(DashboardActivity.created_at)).limit(5).all()

    upcoming_appointments = db.query(Appointment).filter(
        Appointment.user_id == user_id,
        Appointment.status == "upcoming"
    ).order_by(Appointment.date_time).limit(5).all()

    return {
        "profile_completeness": completeness,
        "purchased_services": purchased_slugs,
        "recent_activities": recent_activities,
        "upcoming_appointments": upcoming_appointments,
        "unread_notifications_count": unread_notifications,
        "total_drafts_count": total_drafts,
        "total_payments_count": total_payments
    }


@router.get("/api/profile", response_model=StudentProfileResponse)
def get_student_profile(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves student profile parameters from eligibility logs.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_email = current_user.get("email")

    profile = db.query(EligibilityRequest).filter(EligibilityRequest.email == user_email).first()
    if not profile:
        # Return fallback mock profile
        return {
            "full_name": "Priyan Bose",
            "email": "priyan.bose@gmail.com",
            "phone": "+91 9876543210",
            "country_residence": "India",
            "nationality": "Indian",
            "qualification": "Bachelor of Engineering",
            "preferred_country": "Canada",
            "preferred_course": "M.S. Computer Science",
            "preferred_intake": "Fall 2026"
        }
    
    return {
        "full_name": profile.full_name,
        "email": profile.email,
        "phone": profile.phone,
        "country_residence": profile.country_residence,
        "nationality": profile.nationality,
        "qualification": profile.qualification,
        "preferred_country": profile.preferred_country,
        "preferred_course": profile.preferred_course,
        "preferred_intake": profile.preferred_intake
    }


@router.put("/api/profile", response_model=StudentProfileResponse)
def update_student_profile(
    payload: StudentProfileUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Updates or inserts the student profile parameters in the database logs.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    user_email = current_user.get("email")

    profile = db.query(EligibilityRequest).filter(EligibilityRequest.email == user_email).first()
    if not profile:
        profile = EligibilityRequest(
            full_name=payload.full_name,
            email=user_email,
            phone=payload.phone,
            country_residence=payload.country_residence,
            nationality=payload.nationality,
            qualification=payload.qualification,
            gpa_10th=8.5,
            gpa_12th=8.5,
            grad_year=2024,
            english_exam="IELTS",
            preferred_country=payload.preferred_country,
            preferred_course=payload.preferred_course,
            preferred_intake=payload.preferred_intake,
            budget_range="30-40 Lakhs"
        )
        db.add(profile)
    else:
        profile.full_name = payload.full_name
        profile.phone = payload.phone
        profile.country_residence = payload.country_residence
        profile.nationality = payload.nationality
        profile.qualification = payload.qualification
        profile.preferred_country = payload.preferred_country
        profile.preferred_course = payload.preferred_course
        profile.preferred_intake = payload.preferred_intake

    # Log dashboard activity
    activity = DashboardActivity(
        user_id=user_id,
        activity_type="Profile",
        description="Updated profile information settings."
    )
    db.add(activity)

    db.commit()
    db.refresh(profile)
    return {
        "full_name": profile.full_name,
        "email": profile.email,
        "phone": profile.phone,
        "country_residence": profile.country_residence,
        "nationality": profile.nationality,
        "qualification": profile.qualification,
        "preferred_country": profile.preferred_country,
        "preferred_course": profile.preferred_course,
        "preferred_intake": profile.preferred_intake
    }


@router.get("/api/reports")
def get_compiled_ai_reports(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Aggregates Eligibility, SOP drafts, and Visa documents.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    sops = db.query(SOPDocument).filter(SOPDocument.user_id == user_id).order_by(desc(SOPDocument.updated_at)).all()
    visas = db.query(VisaDocumentCheck).filter(VisaDocumentCheck.user_id == user_id).order_by(desc(VisaDocumentCheck.updated_at)).all()

    sop_list = []
    for s in sops:
        sop_list.append({
            "id": s.id,
            "category": "SOPs",
            "title": s.title,
            "target": f"{s.target_university} - {s.target_course}",
            "updated_at": s.updated_at
        })

    visa_list = []
    for v in visas:
        visa_list.append({
            "id": v.id,
            "category": "Visa Reports",
            "title": f"{v.country} {v.visa_type} Report",
            "target": f"Readiness: {v.readiness_score}% ({v.status})",
            "updated_at": v.updated_at
        })

    return {
        "sops": sop_list,
        "visa_reports": visa_list
    }


@router.get("/api/payments")
def get_billing_history(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Lists payments and service slug details.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    payments = db.query(Payment).join(Order).filter(Order.user_id == user_id).order_by(desc(Payment.transaction_date)).all()
    invoice_list = []
    for p in payments:
        invoice_list.append({
            "id": p.id,
            "receipt_number": p.receipt_number,
            "service_title": p.order.service.title,
            "amount": p.amount,
            "payment_method": p.payment_method,
            "status": p.status,
            "date": p.transaction_date
        })
    return invoice_list


@router.get("/api/documents", response_model=List[UploadedDocumentResponse])
def get_documents_vault(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves all files logged under document checker.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    return db.query(UploadedDocument).join(VisaDocumentCheck).filter(VisaDocumentCheck.user_id == user_id).all()


@router.get("/api/appointments", response_model=List[AppointmentResponse])
def get_appointments_calendar(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves all consulting meetings.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    return db.query(Appointment).filter(Appointment.user_id == user_id).order_by(Appointment.date_time).all()


@router.get("/api/notifications", response_model=List[NotificationResponse])
def get_notifications(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves recent logs for notification updates.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    return db.query(Notification).filter(Notification.user_id == user_id).order_by(desc(Notification.created_at)).all()


@router.put("/api/notifications/read/{notif_id}", response_model=NotificationResponse)
def mark_notification_as_read(
    notif_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Updates the is_read state of a notification.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    notif = db.query(Notification).filter(
        Notification.id == notif_id,
        Notification.user_id == user_id
    ).first()
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found."
        )
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


@router.delete("/api/notifications/{notif_id}")
def delete_notification(
    notif_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Deletes the notification record from the DB logs.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    notif = db.query(Notification).filter(
        Notification.id == notif_id,
        Notification.user_id == user_id
    ).first()
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found."
        )
    db.delete(notif)
    db.commit()
    return {"message": "Notification deleted successfully."}


@router.get("/api/settings", response_model=UserSettingResponse)
def get_user_settings(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves notification settings.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    setting = db.query(UserSetting).filter(UserSetting.user_id == user_id).first()
    if not setting:
        # Create and return default setting
        setting = UserSetting(
            user_id=user_id,
            email_notifications=True,
            sms_notifications=False,
            marketing_emails=False,
            privacy_profile_public=False,
            language="English"
        )
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


@router.put("/api/settings", response_model=UserSettingResponse)
def update_user_settings(
    payload: UserSettingUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Updates notification settings in the DB.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    setting = db.query(UserSetting).filter(UserSetting.user_id == user_id).first()
    if not setting:
        setting = UserSetting(user_id=user_id)
        db.add(setting)

    setting.email_notifications = payload.email_notifications
    setting.sms_notifications = payload.sms_notifications
    setting.marketing_emails = payload.marketing_emails
    setting.privacy_profile_public = payload.privacy_profile_public
    setting.language = payload.language

    db.commit()
    db.refresh(setting)
    return setting
