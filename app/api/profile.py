import logging
import uuid
import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..auth import get_current_user
from ..models import (
    Profile,
    AcademicProfile,
    StudyPreference,
    FinancialProfile,
    LanguagePreference,
    NotificationPreference,
    SecuritySetting,
    ConnectedAccount,
    StudentDocument,
    EligibilityRequest,
    DashboardActivity
)
from ..schemas import (
    ProfileResponse,
    MasterProfileUpdate,
    SettingsResponse,
    NotificationPreferenceSettingsUpdate,
    LanguagePreferenceSettingsUpdate,
    AppearanceSettingsUpdate,
    StudentDocumentResponse
)
from ..services.storage_service import upload_file_to_supabase, delete_file_from_supabase

logger = logging.getLogger(__name__)
router = APIRouter(tags=["profile_engine"])


def calculate_completion_scores(profile: Profile, db: Session) -> Dict[str, int]:
    """
    Calculates completion percentages dynamically for different sections of the master profile.
    """
    scores = {
        "personal": 0,
        "academic": 0,
        "financial": 0,
        "documents": 0,
        "journey": 0,
        "overall": 0
    }
    
    # 1. Personal completion (12 key fields)
    personal_fields = [
        profile.full_name,
        profile.email,
        profile.phone,
        profile.nationality,
        profile.country_residence,
        profile.city,
        profile.gender,
        profile.date_of_birth,
        profile.passport_number,
        profile.passport_expiry,
        profile.emergency_contact_name,
        profile.photo_url
    ]
    filled_personal = sum(1 for field in personal_fields if field is not None and str(field).strip() != "")
    scores["personal"] = int((filled_personal / 12) * 100)

    # 2. Academic completion (8 core fields)
    acad = profile.academic_profile
    if acad:
        academic_fields = [
            acad.highest_qualification,
            acad.gpa_10th,
            acad.gpa_12th,
            acad.cgpa_bachelors,
            acad.grad_year,
            acad.university,
            acad.college
        ]
        filled_acad = sum(1 for field in academic_fields if field is not None and str(field).strip() != "")
        # Check if at least one exam score is filled
        exams = [acad.ielts_score, acad.toefl_score, acad.pte_score, acad.duolingo_score, acad.gre_score, acad.gmat_score, acad.sat_score, acad.neet_score]
        if any(score is not None for score in exams):
            filled_acad += 1
        scores["academic"] = int((filled_acad / 8) * 100)

    # 3. Financial completion (5 core fields)
    fin = profile.financial_profile
    if fin:
        financial_fields = [
            fin.annual_family_income,
            fin.savings,
            fin.education_loan,
            fin.sponsor,
            fin.currency
        ]
        filled_fin = sum(1 for field in financial_fields if field is not None and str(field).strip() != "")
        scores["financial"] = int((filled_fin / 5) * 100)

    # 4. Documents completion (Passport, Academic, Financial, Visa, Certificates)
    docs = db.query(StudentDocument).filter(StudentDocument.user_id == profile.user_id).all()
    categories_uploaded = set(d.category for d in docs)
    # Give 20% weight per category up to 100%
    scores["documents"] = min(len(categories_uploaded) * 20, 100)

    # 5. Journey completion (calculated from activity log or matching progress)
    journey_score = 20  # Base score for profile initialization
    has_activity = db.query(DashboardActivity).filter(DashboardActivity.user_id == profile.user_id).first() is not None
    if has_activity:
        journey_score += 20
    
    # Check if they have matched universities
    from ..models import UniversityMatch, SOPDocument, VisaDocumentCheck
    has_matches = db.query(UniversityMatch).filter(UniversityMatch.user_id == profile.user_id).first() is not None
    if has_matches:
        journey_score += 20
    
    # Check if they have an SOP
    has_sop = db.query(SOPDocument).filter(SOPDocument.user_id == profile.user_id).first() is not None
    if has_sop:
        journey_score += 20
        
    # Check if they have checked visas
    has_visa = db.query(VisaDocumentCheck).filter(VisaDocumentCheck.user_id == profile.user_id).first() is not None
    if has_visa:
        journey_score += 20
        
    scores["journey"] = min(journey_score, 100)

    # 6. Overall Score
    scores["overall"] = int(
        (scores["personal"] * 0.25) +
        (scores["academic"] * 0.25) +
        (scores["financial"] * 0.20) +
        (scores["documents"] * 0.15) +
        (scores["journey"] * 0.15)
    )
    
    return scores


def get_or_create_master_profile(db: Session, user_id: str, email: str = None) -> Profile:
    """
    Retrieves the master profile for the user_id. If none exists, attempts to 
    onboard/migrate using historical EligibilityRequest data, otherwise initializes an empty profile.
    """
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if profile:
        return profile

    # Auto-migration fallback from historical EligibilityRequest
    fallback = None
    if email:
        fallback = db.query(EligibilityRequest).filter(EligibilityRequest.email == email).order_by(desc(EligibilityRequest.created_at)).first()

    if fallback:
        # Migrate existing eligibility request data
        profile = Profile(
            user_id=user_id,
            full_name=fallback.full_name,
            email=fallback.email,
            phone=fallback.phone,
            nationality=fallback.nationality,
            country_residence=fallback.country_residence,
            verification_status="Unverified"
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

        # Create academic profile
        acad = AcademicProfile(
            profile_id=profile.id,
            highest_qualification=fallback.qualification,
            gpa_10th=fallback.gpa_10th,
            gpa_12th=fallback.gpa_12th,
            cgpa_bachelors=fallback.cgpa_bachelors,
            cgpa_masters=fallback.cgpa_masters,
            grad_year=fallback.grad_year,
            university="Not Specified",
            college="Not Specified",
            backlogs=fallback.gap_years,
            work_experience=[{"role": "Intern/Employee", "years": fallback.work_experience}] if fallback.work_experience > 0 else []
        )
        # Add exam scores
        if fallback.english_exam != "None":
            exam = fallback.english_exam.lower()
            if "ielts" in exam:
                acad.ielts_score = fallback.english_score
            elif "toefl" in exam:
                acad.toefl_score = fallback.english_score
            elif "pte" in exam:
                acad.pte_score = fallback.english_score
            elif "duolingo" in exam:
                acad.duolingo_score = fallback.english_score

        if fallback.neet_score:
            acad.neet_score = float(fallback.neet_score)

        db.add(acad)

        # Create preferences
        pref = StudyPreference(
            profile_id=profile.id,
            preferred_countries=[fallback.preferred_country] if fallback.preferred_country else [],
            preferred_courses=[fallback.preferred_course] if fallback.preferred_course else [],
            target_intake=fallback.preferred_intake,
            budget=fallback.budget_range,
            scholarship_required=fallback.scholarship_required
        )
        db.add(pref)

        # Create financials
        fin = FinancialProfile(
            profile_id=profile.id,
            annual_family_income="Not Specified",
            savings=0.0,
            education_loan=0.0,
            sponsor="Self/Family",
            currency="INR"
        )
        db.add(fin)

    else:
        # Initialize brand new profile
        profile = Profile(
            user_id=user_id,
            email=email,
            verification_status="Unverified"
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

        # Initialize blank relationships
        acad = AcademicProfile(profile_id=profile.id)
        pref = StudyPreference(profile_id=profile.id)
        fin = FinancialProfile(profile_id=profile.id)
        db.add(acad)
        db.add(pref)
        db.add(fin)

    # Initialize preferences / settings defaults
    lang = db.query(LanguagePreference).filter(LanguagePreference.profile_id == profile.id).first()
    if not lang:
        lang = LanguagePreference(profile_id=profile.id, preferred_language="English", supported_languages=["English", "Hindi"])
        db.add(lang)

    notif = db.query(NotificationPreference).filter(NotificationPreference.profile_id == profile.id).first()
    if not notif:
        notif = NotificationPreference(
            profile_id=profile.id,
            email=True,
            whatsapp=True,
            sms=False,
            in_app=True,
            ai_updates=True,
            consultation=True,
            payments=True,
            scholarships=True,
            visa=True,
            application=True
        )
        db.add(notif)

    sec = db.query(SecuritySetting).filter(SecuritySetting.profile_id == profile.id).first()
    if not sec:
        sec = SecuritySetting(profile_id=profile.id, two_factor_enabled=False, two_factor_method="email")
        db.add(sec)

    db.commit()
    db.refresh(profile)
    return profile


# ============================================================
# PROFILE ENDPOINTS
# ============================================================

@router.get("/api/profile", response_model=ProfileResponse)
def get_student_profile(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Fetches the logged-in student's master profile, with auto-migration fallbacks.
    """
    user_id = current_user.get("sub")
    if user_id == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        
    email = current_user.get("email")
    profile = get_or_create_master_profile(db, user_id, email)
    
    # Prepare structured responses matching Schemas
    scores = calculate_completion_scores(profile, db)
    
    # Explicit mapping to build the schema payload
    personal_data = {
        "full_name": profile.full_name,
        "email": profile.email,
        "phone": profile.phone,
        "nationality": profile.nationality,
        "country_residence": profile.country_residence,
        "city": profile.city,
        "gender": profile.gender,
        "date_of_birth": profile.date_of_birth,
        "passport_number": profile.passport_number,
        "passport_expiry": profile.passport_expiry,
        "emergency_contact_name": profile.emergency_contact_name,
        "emergency_contact_relation": profile.emergency_contact_relation,
        "emergency_contact_phone": profile.emergency_contact_phone
    }
    
    acad = profile.academic_profile
    academic_data = {
        "highest_qualification": acad.highest_qualification if acad else None,
        "gpa_10th": acad.gpa_10th if acad else None,
        "gpa_12th": acad.gpa_12th if acad else None,
        "cgpa_bachelors": acad.cgpa_bachelors if acad else None,
        "cgpa_masters": acad.cgpa_masters if acad else None,
        "grad_year": acad.grad_year if acad else None,
        "university": acad.university if acad else None,
        "college": acad.college if acad else None,
        "backlogs": acad.backlogs if acad else 0,
        "research_papers": acad.research_papers if acad else [],
        "projects": acad.projects if acad else [],
        "work_experience": acad.work_experience if acad else [],
        "internships": acad.internships if acad else [],
        "certifications": acad.certifications if acad else [],
        "ielts_score": acad.ielts_score if acad else None,
        "ielts_expiry": acad.ielts_expiry if acad else None,
        "toefl_score": acad.toefl_score if acad else None,
        "toefl_expiry": acad.toefl_expiry if acad else None,
        "pte_score": acad.pte_score if acad else None,
        "pte_expiry": acad.pte_expiry if acad else None,
        "duolingo_score": acad.duolingo_score if acad else None,
        "duolingo_expiry": acad.duolingo_expiry if acad else None,
        "gre_score": acad.gre_score if acad else None,
        "gre_expiry": acad.gre_expiry if acad else None,
        "gmat_score": acad.gmat_score if acad else None,
        "gmat_expiry": acad.gmat_expiry if acad else None,
        "sat_score": acad.sat_score if acad else None,
        "sat_expiry": acad.sat_expiry if acad else None,
        "neet_score": acad.neet_score if acad else None,
        "neet_expiry": acad.neet_expiry if acad else None
    }
    
    pref = profile.study_preferences
    pref_data = {
        "preferred_countries": pref.preferred_countries if pref else [],
        "preferred_universities": pref.preferred_universities if pref else [],
        "preferred_courses": pref.preferred_courses if pref else [],
        "degree_level": pref.degree_level if pref else None,
        "budget": pref.budget if pref else None,
        "target_intake": pref.target_intake if pref else None,
        "scholarship_required": pref.scholarship_required if pref else False,
        "preferred_city": pref.preferred_city if pref else None,
        "preferred_language": pref.preferred_language if pref else None,
        "career_goals": pref.career_goals if pref else None
    }
    
    fin = profile.financial_profile
    fin_data = {
        "annual_family_income": fin.annual_family_income if fin else None,
        "savings": fin.savings if fin else 0.0,
        "education_loan": fin.education_loan if fin else 0.0,
        "sponsor": fin.sponsor if fin else None,
        "currency": fin.currency if fin else "INR"
    }

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "personal": personal_data,
        "academic": academic_data,
        "preferences": pref_data,
        "financial": fin_data,
        "verification_status": profile.verification_status,
        "completion_scores": scores,
        "photo_url": profile.photo_url,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at
    }


@router.put("/api/profile", response_model=ProfileResponse)
def update_student_profile(
    payload: MasterProfileUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Autosaves or batch-updates sections of the master student profile.
    """
    user_id = current_user.get("sub")
    if user_id == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        
    profile = get_or_create_master_profile(db, user_id, current_user.get("email"))
    
    # 1. Update Personal
    if payload.personal:
        p_dict = payload.personal.model_dump(exclude_unset=True)
        for key, val in p_dict.items():
            setattr(profile, key, val)

    # 2. Update Academic
    if payload.academic and profile.academic_profile:
        a_dict = payload.academic.model_dump(exclude_unset=True)
        for key, val in a_dict.items():
            setattr(profile.academic_profile, key, val)

    # 3. Update Preferences
    if payload.preferences and profile.study_preferences:
        pr_dict = payload.preferences.model_dump(exclude_unset=True)
        for key, val in pr_dict.items():
            setattr(profile.study_preferences, key, val)

    # 4. Update Financial
    if payload.financial and profile.financial_profile:
        f_dict = payload.financial.model_dump(exclude_unset=True)
        for key, val in f_dict.items():
            setattr(profile.financial_profile, key, val)

    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    
    return get_student_profile(db, current_user)


@router.post("/api/profile/photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Uploads user profile picture to Supabase storage.
    """
    user_id = current_user.get("sub")
    if user_id == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported photo format. Use PNG, JPG, or WebP.")

    profile = get_or_create_master_profile(db, user_id, current_user.get("email"))
    
    # Delete old photo if exists
    if profile.photo_url and "/simulated-storage/" not in profile.photo_url:
        try:
            old_name = profile.photo_url.split("/")[-1]
            delete_file_from_supabase("avatars", old_name)
        except Exception:
            pass

    try:
        unique_name = f"avatar-{user_id}-{uuid.uuid4().hex[:6]}{ext}"
        content = await file.read()
        file_size = len(content)

        # Security: Enforce 5MB limit
        if file_size > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File too large. Maximum size limit is 5MB."
            )
        
        # Upload
        photo_url = upload_file_to_supabase("avatars", unique_name, content, file.content_type)
        profile.photo_url = photo_url
        profile.updated_at = datetime.utcnow()
        db.commit()
        
        return {"status": "success", "photo_url": photo_url}
    except Exception as e:
        logger.error(f"Avatar upload failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save avatar image.")


@router.delete("/api/profile/photo")
def delete_profile_photo(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Removes profile picture.
    """
    user_id = current_user.get("sub")
    if user_id == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not profile or not profile.photo_url:
        return {"status": "success", "message": "No profile picture configured."}

    if "/simulated-storage/" not in profile.photo_url:
        try:
            filename = profile.photo_url.split("/")[-1]
            delete_file_from_supabase("avatars", filename)
        except Exception:
            pass

    profile.photo_url = None
    profile.updated_at = datetime.utcnow()
    db.commit()
    return {"status": "success", "message": "Profile picture deleted successfully."}


# ============================================================
# SETTINGS ENDPOINTS
# ============================================================

@router.get("/api/settings", response_model=SettingsResponse)
def get_user_settings(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Gathers notification preferences, connected accounts, security status, and theme appearance.
    """
    user_id = current_user.get("sub")
    if user_id == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        
    profile = get_or_create_master_profile(db, user_id, current_user.get("email"))

    # Connected accounts
    accounts = db.query(ConnectedAccount).filter(ConnectedAccount.profile_id == profile.id).all()
    accounts_data = [
        {
            "provider": acc.provider,
            "provider_user_id": acc.provider_user_id,
            "email": acc.email,
            "connected_at": acc.connected_at
        } for acc in accounts
    ]
    # Always include Google connected account as a default mock for development if nothing exists
    if not accounts_data:
        accounts_data = [
            {
                "provider": "google",
                "provider_user_id": current_user.get("sub") or "google-id-12345",
                "email": current_user.get("email") or "student@auraroutes.com",
                "connected_at": datetime.utcnow()
            }
        ]

    # Languages preference
    lang = profile.language_preferences
    lang_data = {
        "preferred_language": lang.preferred_language if lang else "English",
        "supported_languages": lang.supported_languages if lang else ["English", "Hindi"]
    }

    # Notification preferences
    notif = profile.notification_preferences
    notif_data = {
        "email": notif.email if notif else True,
        "whatsapp": notif.whatsapp if notif else True,
        "sms": notif.sms if notif else False,
        "in_app": notif.in_app if notif else True,
        "ai_updates": notif.ai_updates if notif else True,
        "consultation": notif.consultation if notif else True,
        "payments": notif.payments if notif else True,
        "scholarships": notif.scholarships if notif else True,
        "visa": notif.visa if notif else True,
        "application": notif.application if notif else True
    }

    # Security settings
    sec = profile.security_settings
    security_data = {
        "two_factor_enabled": sec.two_factor_enabled if sec else False,
        "two_factor_method": sec.two_factor_method if sec else "email",
        "login_history": sec.login_history if (sec and sec.login_history) else [
            {"timestamp": datetime.utcnow().isoformat(), "ip": "127.0.0.1", "device": "Chrome Desktop (Current Session)"}
        ],
        "active_sessions": sec.active_sessions if (sec and sec.active_sessions) else [
            {"session_id": "current", "ip": "127.0.0.1", "device": "Chrome Windows", "expires_at": "30 days"}
        ]
    }

    # Default Theme appearance settings
    from ..models import UserSetting
    user_setting = db.query(UserSetting).filter(UserSetting.user_id == user_id).first()
    theme_name = "dark"
    if user_setting and user_setting.language == "Dark":
        theme_name = "dark"
    elif user_setting and user_setting.language == "Light":
        theme_name = "light"
        
    appearance_data = {
        "theme": theme_name,
        "accent_color": "indigo"
    }

    return {
        "notifications": notif_data,
        "language": lang_data,
        "appearance": appearance_data,
        "connected_accounts": accounts_data,
        "security": security_data
    }


@router.put("/api/settings")
def update_user_settings(
    notifications: Optional[NotificationPreferenceSettingsUpdate] = None,
    appearance: Optional[AppearanceSettingsUpdate] = None,
    language: Optional[LanguagePreferenceSettingsUpdate] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Updates notification, theme appearance, or language settings.
    """
    user_id = current_user.get("sub")
    if user_id == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        
    profile = get_or_create_master_profile(db, user_id, current_user.get("email"))

    # Update Notifications
    if notifications and profile.notification_preferences:
        notif_dict = notifications.model_dump(exclude_unset=True)
        for key, val in notif_dict.items():
            setattr(profile.notification_preferences, key, val)

    # Update Language
    if language and profile.language_preferences:
        lang_dict = language.model_dump(exclude_unset=True)
        for key, val in lang_dict.items():
            setattr(profile.language_preferences, key, val)

    # Update Theme in legacy user_settings table
    if appearance:
        from ..models import UserSetting
        user_setting = db.query(UserSetting).filter(UserSetting.user_id == user_id).first()
        if not user_setting:
            user_setting = UserSetting(user_id=user_id, language=appearance.theme.capitalize())
            db.add(user_setting)
        else:
            user_setting.language = appearance.theme.capitalize()

    db.commit()
    return {"status": "success", "message": "Settings updated successfully."}


@router.post("/api/profile/export")
def export_profile_data(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Exports all personal, academic, preferences, financials, and files list in JSON format.
    """
    user_id = current_user.get("sub")
    if user_id == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    profile_data = get_student_profile(db, current_user)
    docs = db.query(StudentDocument).filter(StudentDocument.user_id == user_id).all()
    docs_list = [
        {
            "filename": d.filename,
            "category": d.category,
            "file_size": d.file_size,
            "file_path": d.file_path,
            "created_at": d.created_at.isoformat()
        } for d in docs
    ]

    # Save to Dashboard activity log
    activity = DashboardActivity(
        user_id=user_id,
        activity_type="Data Export",
        description="Downloaded master profile records export."
    )
    db.add(activity)
    db.commit()

    return {
        "export_metadata": {
            "exported_at": datetime.utcnow().isoformat(),
            "platform": "Aura Routes Master Profile Engine",
            "version": "1.0.0"
        },
        "profile": profile_data,
        "documents": docs_list
    }


@router.delete("/api/account")
def delete_student_account(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Cascade-deletes the student's entire profile, document vault metadata and storage records.
    """
    user_id = current_user.get("sub")
    if user_id == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    # Delete all documents in storage first
    docs = db.query(StudentDocument).filter(StudentDocument.user_id == user_id).all()
    for doc in docs:
        if "/simulated-storage/" not in doc.file_path:
            try:
                fname = doc.file_path.split("/")[-1]
                delete_file_from_supabase("documents", fname)
            except Exception:
                pass
        db.delete(doc)

    # Delete profile photo if any
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if profile and profile.photo_url and "/simulated-storage/" not in profile.photo_url:
        try:
            fname = profile.photo_url.split("/")[-1]
            delete_file_from_supabase("avatars", fname)
        except Exception:
            pass

    # Delete Profile which cascades to tables
    if profile:
        db.delete(profile)

    # Clean legacy dashboard activities & settings
    from ..models import UserSetting, DashboardActivity, SavedUniversity, SavedScholarship, SOPDocument
    db.query(UserSetting).filter(UserSetting.user_id == user_id).delete()
    db.query(DashboardActivity).filter(DashboardActivity.user_id == user_id).delete()
    db.query(SavedUniversity).filter(SavedUniversity.user_id == user_id).delete()
    db.query(SavedScholarship).filter(SavedScholarship.user_id == user_id).delete()
    db.query(SOPDocument).filter(SOPDocument.user_id == user_id).delete()
    
    db.commit()
    return {"status": "success", "message": "Account records deleted completely."}


# ============================================================
# DOCUMENT VAULT ENDPOINTS
# ============================================================

@router.get("/api/profile/documents", response_model=List[StudentDocumentResponse])
def list_vault_documents(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves metadata of all documents uploaded in the student vault.
    """
    user_id = current_user.get("sub")
    if user_id == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        
    return db.query(StudentDocument).filter(StudentDocument.user_id == user_id).order_by(desc(StudentDocument.created_at)).all()


@router.post("/api/profile/documents", response_model=StudentDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_vault_document(
    category: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Uploads a file to Supabase storage documents bucket and lists it in the vault.
    """
    user_id = current_user.get("sub")
    if user_id == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported format. Only PDF, Image (JPG/PNG), and Word files are supported."
        )

    try:
        unique_name = f"vault-{user_id}-{uuid.uuid4().hex[:8]}{ext}"
        content = await file.read()
        file_size = len(content)

        # Security: Enforce 5MB limit
        if file_size > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File too large. Maximum size limit is 5MB."
            )

        # Upload
        storage_url = upload_file_to_supabase("documents", unique_name, content, file.content_type)
        
        # Save document meta
        db_doc = StudentDocument(
            user_id=user_id,
            category=category,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            file_size=file_size,
            file_path=storage_url
        )
        db.add(db_doc)
        
        # Add to Dashboard activity log
        activity = DashboardActivity(
            user_id=user_id,
            activity_type="Document Upload",
            description=f"Uploaded '{file.filename}' to the {category} vault."
        )
        db.add(activity)
        
        db.commit()
        db.refresh(db_doc)
        
        return db_doc
    except Exception as e:
        logger.error(f"Document upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@router.put("/api/profile/documents/{doc_id}", response_model=StudentDocumentResponse)
def rename_vault_document(
    doc_id: str,
    new_filename: str = Form(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Updates the client-facing filename of a document vault record.
    """
    user_id = current_user.get("sub")
    if user_id == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    doc = db.query(StudentDocument).filter(StudentDocument.id == doc_id, StudentDocument.user_id == user_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault file not found.")

    # Retain file extension if they omitted it
    old_ext = os.path.splitext(doc.filename)[1].lower()
    new_ext = os.path.splitext(new_filename)[1].lower()
    if not new_ext and old_ext:
        new_filename = f"{new_filename}{old_ext}"

    doc.filename = new_filename
    doc.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/api/profile/documents/{doc_id}")
def delete_vault_document(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Deletes vault document from database meta and storage block.
    """
    user_id = current_user.get("sub")
    if user_id == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    doc = db.query(StudentDocument).filter(StudentDocument.id == doc_id, StudentDocument.user_id == user_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault file not found.")

    if "/simulated-storage/" not in doc.file_path:
        try:
            fname = doc.file_path.split("/")[-1]
            delete_file_from_supabase("documents", fname)
        except Exception as e:
            logger.warning(f"Failed to delete document block from Supabase: {str(e)}")

    db.delete(doc)
    db.commit()
    return {"status": "success", "message": f"Document '{doc.filename}' deleted successfully."}


@router.get("/api/profile/documents/{doc_id}/download")
def download_vault_document(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Exposes direct access URL for downloading/previewing the vault file.
    """
    user_id = current_user.get("sub")
    if user_id == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    doc = db.query(StudentDocument).filter(StudentDocument.id == doc_id, StudentDocument.user_id == user_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault file not found.")

    return {"download_url": doc.file_path, "filename": doc.filename}
