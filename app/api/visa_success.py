import logging
import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List

from ..database import get_db
from ..auth import get_current_user
from ..models import (
    VisaProfile,
    VisaReadinessReport,
    VisaChecklist,
    VisaTask,
    VisaInterview,
    VisaFinancial,
    VisaTimelineItem,
    VisaRecommendation,
    DashboardActivity
)
from ..schemas import (
    VisaProfileResponse,
    VisaReadinessRequest,
    VisaReadinessResponse,
    VisaChecklistResponse,
    VisaTaskResponse,
    VisaInterviewRequest,
    VisaInterviewResponse,
    VisaFinancialRequest,
    VisaFinancialResponse,
    VisaTimelineItemResponse,
    VisaRecommendationResponse,
    VisaDashboardResponse
)
from ..services.visa_success_service import evaluate_visa_readiness_ai, analyze_visa_interview_answer_ai

logger = logging.getLogger(__name__)
router = APIRouter(tags=["visa_success"])


def get_or_create_visa_profile(db: Session, user_id: str, country: str = "Canada") -> VisaProfile:
    """
    Helper utility to locate or spin up the user's specific visa preparation workspace profile.
    """
    prof = db.query(VisaProfile).filter(
        VisaProfile.user_id == user_id,
        VisaProfile.country == country
    ).first()

    if not prof:
        logger.info(f"Creating a new Visa Profile for country: {country} and user: {user_id}")
        prof = VisaProfile(
            user_id=user_id,
            country=country,
            visa_type="Student Visa",
            current_stage="Documents"
        )
        db.add(prof)
        db.commit()
        db.refresh(prof)

        # Populate Default Checklist items
        checklist_defaults = [
            "Valid Passport scan copy",
            "Official University Offer Letter",
            "GIC account certificate / Sponsor letters",
            "Upfront Medical clearance certificate",
            "Certified Academic transcripts",
            "Personal SOP statement",
            "LOR referrals"
        ]
        for item in checklist_defaults:
            db.add(VisaChecklist(profile_id=prof.id, item_name=item, status="Pending"))

        # Populate default Timeline tasks
        timeline_defaults = [
            {"title": "Receive University Offer Letter", "date": "2025-10-15"},
            {"title": "Open block account or GIC savings", "date": "2025-11-20"},
            {"title": "Complete upfront visa medical clearance", "date": "2026-02-10"},
            {"title": "Schedule Biometrics and submit visa files", "date": "2026-04-05"}
        ]
        for t in timeline_defaults:
            db.add(VisaTimelineItem(profile_id=prof.id, event_title=t["title"], event_date=t["date"], status="Pending"))

        # Add initial recommendation cards
        recs = [
            {"title": "Pre-arrange Biometrics", "msg": "Schedule biometrics appointment slots early as regional slots fill fast."},
            {"title": "Passport validity audit", "msg": "Ensure your passport is valid for at least 6 months beyond the targeted travel date."}
        ]
        for r in recs:
            db.add(VisaRecommendation(profile_id=prof.id, title=r["title"], message=r["msg"], actionable=True))

        db.commit()
        db.refresh(prof)

    return prof


@router.get("/api/visa/dashboard", response_model=VisaDashboardResponse)
def get_visa_dashboard(
    country: str = "Canada",
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Consolidates the active visa profile checklist, timelines, readiness metrics, and recommendation feeds.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    try:
        prof = get_or_create_visa_profile(db, user_id, country)
        
        readiness = db.query(VisaReadinessReport).filter(
            VisaReadinessReport.profile_id == prof.id
        ).order_by(desc(VisaReadinessReport.created_at)).first()

        checklist = db.query(VisaChecklist).filter(VisaChecklist.profile_id == prof.id).all()
        tasks = db.query(VisaTask).filter(VisaTask.profile_id == prof.id).all()
        financial = db.query(VisaFinancial).filter(VisaFinancial.profile_id == prof.id).order_by(desc(VisaFinancial.created_at)).first()
        timeline = db.query(VisaTimelineItem).filter(VisaTimelineItem.profile_id == prof.id).order_by(VisaTimelineItem.event_date).all()
        recommendations = db.query(VisaRecommendation).filter(VisaRecommendation.profile_id == prof.id).all()

        return {
            "profile": prof,
            "readiness": readiness,
            "checklist": checklist,
            "tasks": tasks,
            "financial": financial,
            "timeline": timeline,
            "recommendations": recommendations
        }
    except Exception as e:
        logger.error(f"Failed to compile visa dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load Visa Success Center metrics."
        )


@router.post("/api/visa/readiness", response_model=VisaReadinessResponse)
def evaluate_visa_readiness(
    payload: VisaReadinessRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Evaluates questionnaire responses via OpenAI and logs readiness risk scores.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    try:
        prof = get_or_create_visa_profile(db, user_id, payload.country)
        
        # Run AI auditor
        ai_res = evaluate_visa_readiness_ai(
            payload.country,
            payload.academic_readiness,
            payload.financial_readiness,
            payload.document_readiness,
            payload.travel_readiness,
            payload.interview_readiness
        )

        db_report = VisaReadinessReport(
            profile_id=prof.id,
            overall_score=ai_res.get("overall_score", 50),
            risk_level=ai_res.get("risk_level", "Medium"),
            critical_issues=ai_res.get("critical_issues", []),
            suggested_improvements=ai_res.get("suggested_improvements", [])
        )
        db.add(db_report)
        
        # Log Dashboard Activity for the authenticated user
        db.add(DashboardActivity(
            user_id=user_id,
            activity_type="Visa Readiness",
            description=f"Generated AI readiness report for {payload.country} (Score: {db_report.overall_score}%)."
        ))

        db.commit()
        db.refresh(db_report)
        return db_report
    except Exception as e:
        logger.error(f"Readiness evaluation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate visa readiness profile."
        )


@router.post("/api/visa/financial", response_model=VisaFinancialResponse)
def calculate_financial_readiness(
    payload: VisaFinancialRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Computes funding targets, calculated gaps, and records recommendations.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    try:
        prof = get_or_create_visa_profile(db, user_id, payload.country)

        # Calculate funds bounds
        required = payload.tuition_fee + payload.living_expenses
        available = payload.scholarship_amount + payload.education_loan + payload.savings
        gap = max(0.0, required - available)

        # Score calculations
        score = 100
        if required > 0:
            score = int((available / required) * 100)
            score = min(100, max(10, score))
            if gap > 0:
                score = max(10, score - 15) # Deduct penalty for gaps

        db_fin = VisaFinancial(
            profile_id=prof.id,
            tuition_fee=payload.tuition_fee,
            living_expenses=payload.living_expenses,
            scholarship_amount=payload.scholarship_amount,
            education_loan=payload.education_loan,
            savings=payload.savings,
            required_funds=required,
            available_funds=available,
            funding_gap=gap,
            readiness_score=score
        )
        db.add(db_fin)

        # Log timeline and warnings if gap is significant
        if gap > 0:
            db.add(VisaRecommendation(
                profile_id=prof.id,
                title="Funding Deficit Alerts",
                message=f"You have a calculated funding deficit of {gap:.2f}. Consider securing add-on sponsors or showing additional proof.",
                actionable=True
            ))

        db.commit()
        db.refresh(db_fin)
        return db_fin
    except Exception as e:
        logger.error(f"Financial calculator failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute financial preparedness parameters."
        )


@router.post("/api/visa/interview", response_model=VisaInterviewResponse)
def submit_visa_interview_answer(
    payload: VisaInterviewRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Submits visa officer mock questions answers to ChatGPT for rating and critique feedback logs.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    try:
        prof = get_or_create_visa_profile(db, user_id, payload.country)

        # Analyze answer using OpenAI ChatGPT
        critique = analyze_visa_interview_answer_ai(
            payload.country,
            payload.question,
            payload.student_answer
        )

        new_entry = {
            "question": payload.question,
            "answer": payload.student_answer,
            "feedback": critique.get("feedback", "No feedback available."),
            "score": critique.get("score", 50),
            "rating": critique.get("rating", "Needs Improvement"),
            "suggestions": critique.get("suggestions", "Practice speaking clearly.")
        }

        # Check for existing interview logs list
        db_int = db.query(VisaInterview).filter(VisaInterview.profile_id == prof.id).first()
        if not db_int:
            db_int = VisaInterview(
                profile_id=prof.id,
                questions=[new_entry]
            )
            db.add(db_int)
        else:
            # Append question entry
            updated_questions = list(db_int.questions)
            updated_questions.append(new_entry)
            db_int.questions = updated_questions

        db.commit()
        db.refresh(db_int)
        return db_int
    except Exception as e:
        logger.error(f"Interview grading failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate mock interview answer."
        )


@router.post("/api/visa/checklist", response_model=VisaChecklistResponse)
def update_checklist_status(
    checklist_id: str,
    status: str,
    notes: str = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Modifies status flags on specific checklist slots, checking authorization ownership.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    # Secure BOLA verification
    item = db.query(VisaChecklist).join(VisaProfile).filter(
        VisaChecklist.id == checklist_id,
        VisaProfile.user_id == user_id
    ).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Checklist item not found or access denied."
        )

    item.status = status
    if notes:
        item.notes = notes

    db.commit()
    db.refresh(item)
    return item


@router.post("/api/visa/timeline", response_model=VisaTimelineItemResponse)
def update_timeline_item_status(
    timeline_id: str,
    status: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Modifies status on timeline checkpoints, checking authorization ownership.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    # Secure BOLA verification
    item = db.query(VisaTimelineItem).join(VisaProfile).filter(
        VisaTimelineItem.id == timeline_id,
        VisaProfile.user_id == user_id
    ).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timeline item not found or access denied."
        )

    item.status = status
    db.commit()
    db.refresh(item)
    return item


@router.get("/api/visa/history", response_model=List[VisaReadinessResponse])
def get_visa_readiness_history(
    country: str = "Canada",
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Lists previous visa readiness assessment metrics.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    prof = get_or_create_visa_profile(db, user_id, country)
    return db.query(VisaReadinessReport).filter(
        VisaReadinessReport.profile_id == prof.id
    ).order_by(desc(VisaReadinessReport.created_at)).all()
