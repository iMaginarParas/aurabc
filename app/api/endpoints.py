import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from datetime import datetime
from typing import Optional, List

from ..database import get_db
from ..models import EligibilityRequest, EligibilityResult
from ..schemas import (
    EligibilityRequestCreate,
    EligibilityCheckResponse,
    EligibilityRequestResponse,
    EligibilityResultResponse,
    PaginatedHistoryResponse
)
from ..services.openai_service import evaluate_student_profile
from ..services.analytics_service import get_eligibility_analytics_report

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/eligibility", tags=["eligibility"])

@router.post("/check", response_model=EligibilityCheckResponse, status_code=status.HTTP_201_CREATED)
async def check_eligibility(
    payload: EligibilityRequestCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Submits a student's profile assessment, processes it using OpenAI ChatGPT,
    and stores the request and evaluation results in the PostgreSQL database.
    """
    client_ip = request.client.host if request.client else None
    
    # 1. Store the request in DB (Initial status: pending)
    db_request = EligibilityRequest(
        full_name=payload.personal_info.full_name,
        email=payload.personal_info.email,
        phone=payload.personal_info.phone,
        country_residence=payload.personal_info.country_residence,
        nationality=payload.personal_info.nationality,
        qualification=payload.academic_profile.qualification,
        gpa_10th=payload.academic_profile.gpa_10th,
        gpa_12th=payload.academic_profile.gpa_12th,
        cgpa_bachelors=payload.academic_profile.cgpa_bachelors,
        cgpa_masters=payload.academic_profile.cgpa_masters,
        grad_year=payload.academic_profile.grad_year,
        english_exam=payload.english_proficiency.english_exam,
        english_score=payload.english_proficiency.english_score,
        preferred_country=payload.study_preferences.preferred_country,
        preferred_course=payload.study_preferences.preferred_course,
        preferred_intake=payload.study_preferences.preferred_intake,
        budget_range=payload.study_preferences.budget_range,
        scholarship_required=payload.study_preferences.scholarship_required,
        work_experience=payload.additional_info.work_experience,
        gap_years=payload.additional_info.gap_years,
        neet_score=payload.additional_info.neet_score,
        passport_available=payload.additional_info.passport_available,
        ip_address=client_ip,
        status="pending"
    )
    
    db.add(db_request)
    db.commit()
    db.refresh(db_request)

    # 2. Gather profile dict for AI evaluator
    profile_dict = {
        "full_name": db_request.full_name,
        "email": db_request.email,
        "phone": db_request.phone,
        "country_residence": db_request.country_residence,
        "nationality": db_request.nationality,
        "qualification": db_request.qualification,
        "gpa_10th": db_request.gpa_10th,
        "gpa_12th": db_request.gpa_12th,
        "cgpa_bachelors": db_request.cgpa_bachelors,
        "cgpa_masters": db_request.cgpa_masters,
        "grad_year": db_request.grad_year,
        "english_exam": db_request.english_exam,
        "english_score": db_request.english_score,
        "preferred_country": db_request.preferred_country,
        "preferred_course": db_request.preferred_course,
        "preferred_intake": db_request.preferred_intake,
        "budget_range": db_request.budget_range,
        "scholarship_required": db_request.scholarship_required,
        "work_experience": db_request.work_experience,
        "gap_years": db_request.gap_years,
        "neet_score": db_request.neet_score,
        "passport_available": db_request.passport_available
    }

    # 3. Call AI Service
    try:
        ai_evaluation = evaluate_student_profile(profile_dict)
        
        # Save evaluation result to DB
        db_result = EligibilityResult(
            request_id=db_request.id,
            overall_score=ai_evaluation.overall_score,
            admission_probability=ai_evaluation.admission_probability,
            scholarship_potential=ai_evaluation.scholarship_potential,
            visa_readiness=ai_evaluation.visa_readiness,
            strengths=ai_evaluation.strengths,
            weaknesses=ai_evaluation.weaknesses,
            suggested_improvements=ai_evaluation.suggested_improvements,
            recommended_countries=ai_evaluation.recommended_countries,
            recommended_universities=[u.model_dump() for u in ai_evaluation.recommended_universities],
            suggested_next_steps=ai_evaluation.suggested_next_steps
        )
        
        db.add(db_result)
        db_request.status = "completed"
        db.commit()
        db.refresh(db_result)
        db.refresh(db_request)
        
        return EligibilityCheckResponse(request=db_request, result=db_result)
        
    except Exception as e:
        logger.error(f"Failed to generate evaluation for request {db_request.id}: {str(e)}")
        db_request.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate AI evaluation. Please verify your credentials or try again."
        )

@router.get("/history", response_model=PaginatedHistoryResponse)
def get_eligibility_history(
    search: Optional[str] = Query(None, description="Search by name or email"),
    country: Optional[str] = Query(None, description="Filter by preferred country"),
    min_score: Optional[int] = Query(None, description="Filter by minimum eligibility score"),
    max_score: Optional[int] = Query(None, description="Filter by maximum eligibility score"),
    start_date: Optional[datetime] = Query(None, description="Filter from submission date"),
    end_date: Optional[datetime] = Query(None, description="Filter to submission date"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Records limit per page"),
    db: Session = Depends(get_db)
):
    """
    Get paginated logs of submissions with filters (Admin ready).
    """
    query = db.query(EligibilityRequest)

    # 1. Join with Results if filtering by score
    if min_score is not None or max_score is not None:
        query = query.join(EligibilityResult)
        if min_score is not None:
            query = query.filter(EligibilityResult.overall_score >= min_score)
        if max_score is not None:
            query = query.filter(EligibilityResult.overall_score <= max_score)

    # 2. Search filters
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                EligibilityRequest.full_name.ilike(search_filter),
                EligibilityRequest.email.ilike(search_filter)
            )
        )

    if country:
        query = query.filter(EligibilityRequest.preferred_country.ilike(country))

    if start_date:
        query = query.filter(EligibilityRequest.created_at >= start_date)
    if end_date:
        query = query.filter(EligibilityRequest.created_at <= end_date)

    # 3. Pagination computation
    total = query.count()
    pages = (total + limit - 1) // limit if total > 0 else 0
    offset = (page - 1) * limit
    
    requests = query.order_by(desc(EligibilityRequest.created_at)).offset(offset).limit(limit).all()

    return PaginatedHistoryResponse(
        total=total,
        page=page,
        limit=limit,
        pages=pages,
        requests=requests
    )

@router.get("/analytics")
def get_eligibility_analytics(db: Session = Depends(get_db)):
    """
    Fetches aggregate statistics on checker usage and funnel drop-offs.
    """
    return get_eligibility_analytics_report(db)

@router.get("/{request_id}", response_model=EligibilityCheckResponse)
def get_eligibility_by_id(request_id: str, db: Session = Depends(get_db)):
    """
    Fetches the eligibility request details and AI result evaluation by request ID.
    """
    db_request = db.query(EligibilityRequest).filter(EligibilityRequest.id == request_id).first()
    if not db_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment request ID not found."
        )
    return EligibilityCheckResponse(request=db_request, result=db_request.result)
