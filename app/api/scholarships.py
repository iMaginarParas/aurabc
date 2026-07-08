import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional, Dict, Any

from ..database import get_db
from ..auth import get_current_user
from ..models import (
    Scholarship,
    ScholarshipMatch,
    SavedScholarship,
    FundingPlan,
    ScholarshipDeadline,
    ScholarshipReport,
    DashboardActivity
)
from ..schemas import (
    ScholarshipResponse,
    ScholarshipProfileInput,
    ScholarshipMatchResponse,
    SaveUniversityRequest, # We can reuse SaveUniversityRequest structures or define SaveScholarshipRequest
    SavedScholarshipResponse,
    FundingPlannerRequest,
    FundingPlannerResponse
)
from ..services.scholarship_service import evaluate_scholarship_matches_ai, evaluate_funding_planner_ai

logger = logging.getLogger(__name__)
router = APIRouter(tags=["scholarships"])


@router.post("/api/scholarships/match", response_model=List[Dict] if not None else Any)
def match_scholarships(
    payload: ScholarshipProfileInput,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Evaluates student credentials and preferred countries against catalog to return recommended opportunities.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    try:
        profile_dict = payload.model_dump()
        recs = evaluate_scholarship_matches_ai(db, profile_dict)

        # Log match session
        db_match = ScholarshipMatch(
            user_id=user_id,
            profile_data=profile_dict,
            recommendations=recs
        )
        db.add(db_match)

        # Log Dashboard Activity
        db.add(DashboardActivity(
            user_id=user_id,
            activity_type="Scholarships Match",
            description=f"Generated {len(recs)} matched scholarships recommendations."
        ))

        db.commit()
        return recs
    except Exception as e:
        logger.error(f"Scholarship matching failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to discover scholarship matches."
        )


        insurance = payload.get("insurance", 0.0)
        misc = payload.get("misc_expenses", 0.0)

        scholarship_amt = payload.get("scholarship_amount", 0.0)
        loan = payload.get("loan_amount", 0.0)
        savings = payload.get("savings", 0.0)

        total_cost = tuition + living + travel + visa + insurance + misc
        total_available = scholarship_amt + loan + savings
        gap = max(0.0, total_cost - total_available)

        # Prepare planner data for AI advisor
        planner_data = {
            "total_cost": total_cost,
            "total_available": total_available,
            "funding_gap": gap,
            "tuition_fee": tuition,
            "living_cost": living,
            "scholarship_amount": scholarship_amt,
            "loan_amount": loan,
            "savings": savings
        }

        ai_res = evaluate_funding_planner_ai({}, planner_data)

        db_plan = FundingPlan(
            user_id=user_id,
            tuition_fee=tuition,
            living_cost=living,
            travel_cost=travel,
            visa_cost=visa,
            insurance=insurance,
            misc_expenses=misc,
            scholarship_amount=scholarship_amt,
            loan_amount=loan,
            savings=savings,
            funding_gap=gap,
            total_cost=total_cost,
            total_available=total_available,
            readiness_score=ai_res.get("financial_readiness_score", 50),
            suggested_plan=ai_res.get("suggested_plan")
        )
        db.add(db_plan)

        # Create scholarship reports entry
        db_report = ScholarshipReport(
            user_id=user_id,
            report_data={
                "funding_summary": planner_data,
                "ai_advices": ai_res
            }
        )
        db.add(db_report)

        db.commit()
        db.refresh(db_plan)
        return {
            "plan": db_plan,
            "recommendations": ai_res.get("recommendations", [])
        }
    except Exception as e:
        logger.error(f"Funding planning failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate financial planner report."
        )


@router.get("/api/scholarships/history")
def get_matching_history(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Gathers previous matching sessions logs.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    return db.query(ScholarshipMatch).filter(
        ScholarshipMatch.user_id == user_id
    ).order_by(desc(ScholarshipMatch.created_at)).all()


@router.post("/api/scholarships/save")
def save_scholarship_bookmark(
    payload: Dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Saves/Bookmarks a recommended scholarship.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    # Check duplicate
    existing = db.query(SavedScholarship).filter(
        SavedScholarship.user_id == user_id,
        SavedScholarship.name == payload.get("name")
    ).first()

    if existing:
        return existing

    db_fav = SavedScholarship(
        user_id=user_id,
        name=payload.get("name"),
        provider=payload.get("provider", "Global"),
        country=payload.get("country", "Global"),
        funding_amount=payload.get("funding_amount", "Varies"),
        match_percentage=payload.get("match_percentage", 80),
        deadline=payload.get("deadline")
    )
    db.add(db_fav)
    
    # Generate calendar deadline alert
    if payload.get("deadline"):
        db.add(ScholarshipDeadline(
            user_id=user_id,
            event_title=f"Apply for {payload.get('name')}",
            event_type="Deadline",
            event_date=payload.get("deadline")
        ))

    db.commit()
    db.refresh(db_fav)
    return db_fav


@router.get("/api/scholarships/saved")
def get_saved_scholarships(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Gathers all bookmarked scholarships.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    return db.query(SavedScholarship).filter(
        SavedScholarship.user_id == user_id
    ).order_by(desc(SavedScholarship.created_at)).all()


@router.delete("/api/scholarships/saved/{fav_id}")
def remove_saved_scholarship(
    fav_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Removes a scholarship from saved checklist.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    fav = db.query(SavedScholarship).filter(
        SavedScholarship.id == fav_id,
        SavedScholarship.user_id == user_id
    ).first()
    if not fav:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved scholarship not found."
        )
    db.delete(fav)
    db.commit()
    return {"message": "Bookmark removed."}


@router.get("/api/scholarships/deadlines")
def get_scholarships_deadlines_calendar(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns dates for saved scholarship applications.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    return db.query(ScholarshipDeadline).filter(
        ScholarshipDeadline.user_id == user_id
    ).order_by(ScholarshipDeadline.event_date).all()
