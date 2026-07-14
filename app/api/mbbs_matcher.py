import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Dict, Any

from ..database import get_db
from ..auth import get_current_user
from ..models import MBBSUniversity, UniversityMatch, DashboardActivity
from ..schemas import (
    MBBSProfileInput,
    MBBSMatchResponse
)
from ..services.match_service import evaluate_mbbs_abroad_matches_ai

logger = logging.getLogger(__name__)
router = APIRouter(tags=["mbbs_matcher"])


@router.post("/api/mbbs-matcher", response_model=MBBSMatchResponse)
def match_mbbs_universities(
    payload: MBBSProfileInput,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Submits MBBS student profile to OpenAI/fallback to generate matches.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    try:
        profile_dict = payload.model_dump()
        recs = evaluate_mbbs_abroad_matches_ai(db, profile_dict)
        
        # Log to Database (reusing UniversityMatch model since it stores JSON)
        db_match = UniversityMatch(
            user_id=user_id,
            profile_data={**profile_dict, "module": "mbbs_abroad"},
            recommendations=recs
        )
        db.add(db_match)
        
        activity = DashboardActivity(
            user_id=user_id,
            activity_type="MBBS Match",
            description=f"Generated {len(recs)} MBBS Abroad matches for NEET score {payload.neet_score}."
        )
        db.add(activity)
        db.commit()
        db.refresh(db_match)
        return db_match
    except Exception as e:
        logger.error(f"MBBS Abroad matching failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate MBBS Abroad matches."
        )


@router.get("/api/mbbs-matcher/history", response_model=List[MBBSMatchResponse])
def get_mbbs_matcher_history(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves previous MBBS matching results.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    
    # Query UniversityMatch entries that belong to this user and have 'mbbs_abroad' module flag
    matches = db.query(UniversityMatch).filter(
        UniversityMatch.user_id == user_id
    ).order_by(desc(UniversityMatch.created_at)).all()
    
    # Filter list in Python to keep those with module == 'mbbs_abroad' in profile_data
    filtered_matches = []
    for m in matches:
        if isinstance(m.profile_data, dict) and m.profile_data.get("module") == "mbbs_abroad":
            filtered_matches.append(m)
            
    return filtered_matches


@router.get("/api/mbbs-matcher/catalog", response_model=List[Dict[str, Any]])
def get_mbbs_universities_catalog(db: Session = Depends(get_db)):
    """
    Lists the seeded NMC-approved MBBS universities.
    """
    unis = db.query(MBBSUniversity).filter(MBBSUniversity.status == "Active").all()
    result = []
    for u in unis:
        result.append({
            "id": u.id,
            "name": u.name,
            "country": u.country,
            "nmc_approved": u.nmc_approved,
            "annual_fees": u.annual_fees,
            "hostel_fees": u.hostel_fees,
            "living_cost": u.living_cost,
            "duration": u.duration,
            "language": u.language,
            "eligibility": u.eligibility,
            "minimum_neet": u.minimum_neet,
            "recognition": u.recognition
        })
    return result
