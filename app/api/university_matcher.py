import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List

from ..database import get_db
from ..auth import get_current_user
from ..models import University, UniversityMatch, SavedUniversity, UniversityComparison, DashboardActivity
from ..schemas import (
    UniversityResponse,
    UniversityProfileInput,
    UniversityMatchResponse,
    SaveUniversityRequest,
    SavedUniversityResponse,
    ComparisonRequest,
    ComparisonResponse
)
from ..services.match_service import evaluate_university_matches_ai

logger = logging.getLogger(__name__)
router = APIRouter(tags=["university_matcher"])


@router.post("/api/university-matcher", response_model=UniversityMatchResponse)
def match_universities(
    payload: UniversityProfileInput,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Submits student profiles to OpenAI to generate matched university recommendations.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    try:
        # Convert profile to standard dict for prompt parser
        profile_dict = payload.model_dump()
        
        # Evaluate recommendations
        recs = evaluate_university_matches_ai(db, profile_dict)
        
        # Log to Database
        db_match = UniversityMatch(
            user_id=user_id,
            profile_data=profile_dict,
            recommendations=recs
        )
        db.add(db_match)
        
        # Add to Dashboard activity log
        activity = DashboardActivity(
            user_id=user_id,
            activity_type="University Match",
            description=f"Generated {len(recs)} university matches for {payload.course}."
        )
        db.add(activity)
        
        db.commit()
        db.refresh(db_match)
        return db_match
    except Exception as e:
        logger.error(f"University matching failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate university matches."
        )


@router.get("/api/university-matcher/history", response_model=List[UniversityMatchResponse])
def get_matcher_history(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves previous matching results.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    return db.query(UniversityMatch).filter(
        UniversityMatch.user_id == user_id
    ).order_by(desc(UniversityMatch.created_at)).all()


@router.get("/api/university/{uni_id}", response_model=UniversityResponse)
def get_university_by_id(uni_id: str, db: Session = Depends(get_db)):
    """
    Retrieves specific university profile details from the catalog database.
    """
    uni = db.query(University).filter(University.id == uni_id).first()
    if not uni:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="University profile not found in catalog."
        )
    return uni


@router.get("/api/universities/catalog", response_model=List[UniversityResponse])
def get_universities_catalog(db: Session = Depends(get_db)):
    """
    Lists the seeded global universities.
    """
    return db.query(University).order_by(University.world_ranking).all()


@router.post("/api/university/save", response_model=SavedUniversityResponse, status_code=status.HTTP_201_CREATED)
def save_university_to_favorites(
    payload: SaveUniversityRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Saves a matched course recommendation to the student's favorites list.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    # Check if already saved
    existing = db.query(SavedUniversity).filter(
        SavedUniversity.user_id == user_id,
        SavedUniversity.name == payload.name,
        SavedUniversity.course == payload.course
    ).first()
    
    if existing:
        return existing
        
    db_fav = SavedUniversity(
        user_id=user_id,
        name=payload.name,
        country=payload.country,
        course=payload.course,
        tuition_fee=payload.tuition_fee,
        match_percentage=payload.match_percentage
    )
    db.add(db_fav)
    db.commit()
    db.refresh(db_fav)
    return db_fav


@router.get("/api/university/saved", response_model=List[SavedUniversityResponse])
def get_saved_universities(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Lists all saved universities.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    return db.query(SavedUniversity).filter(
        SavedUniversity.user_id == user_id
    ).order_by(desc(SavedUniversity.created_at)).all()


@router.delete("/api/university/saved/{fav_id}", status_code=status.HTTP_200_OK)
def remove_saved_university(
    fav_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Removes a university from the saved list.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    fav = db.query(SavedUniversity).filter(
        SavedUniversity.id == fav_id,
        SavedUniversity.user_id == user_id
    ).first()
    if not fav:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved university not found."
        )
    db.delete(fav)
    db.commit()
    return {"message": "Removed from saved favorites list."}


@router.post("/api/university/compare", response_model=ComparisonResponse, status_code=status.HTTP_201_CREATED)
def save_comparison_matrix(
    payload: ComparisonRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Saves a side-by-side compared matrices configuration.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    db_comp = UniversityComparison(
        user_id=user_id,
        name=payload.name,
        data=payload.data
    )
    db.add(db_comp)
    db.commit()
    db.refresh(db_comp)
    return db_comp
