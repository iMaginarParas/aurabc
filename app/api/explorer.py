import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_, and_
from typing import List, Optional
from pydantic import BaseModel

from ..database import get_db
from ..auth import get_current_user
from ..models import (
    ExplorerUniversity,
    ExplorerCourse,
    ExplorerCountry,
    UniversityBookmark,
    CourseBookmark,
    CountryBookmark,
    ExplorerRecentSearch,
    UniversityReview,
    ExplorerComparison,
    Application,
    ApplicationDocument,
    ApplicationTimeline,
    CalendarEvent,
    StudentJourney,
)
from ..services.explorer_service import get_ai_university_summary

logger = logging.getLogger(__name__)
router = APIRouter(tags=["explorer"])


# ============================================================
# Pydantic Schemas
# ============================================================

class BookmarkInput(BaseModel):
    type: str  # university, course, country
    item_id: str  # university_id, course_id, or country_slug
    collection_name: Optional[str] = "My Shortlist"


class ReviewInput(BaseModel):
    university_id: str
    rating: int  # 1–5
    pros: Optional[List[str]] = []
    cons: Optional[List[str]] = []
    review_text: Optional[str] = None
    program_studied: Optional[str] = None
    graduation_year: Optional[int] = None


class CompareInput(BaseModel):
    university_slugs: List[str]
    name: Optional[str] = "My Comparison"


class AISummaryInput(BaseModel):
    university_name: str
    country: str
    course: str
    student_profile: Optional[dict] = {}


class ApplyInput(BaseModel):
    university_id: str
    course_id: Optional[str] = None
    intake: Optional[str] = "Fall 2026"


# ============================================================
# UNIVERSITIES ENDPOINTS
# ============================================================

@router.get("/api/explorer/universities")
def list_universities(
    search: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    university_type: Optional[str] = Query(None),
    ielts_max: Optional[float] = Query(None),
    tuition_max: Optional[float] = Query(None),
    scholarship_only: Optional[bool] = Query(False),
    visa_difficulty: Optional[str] = Query(None),
    ranking_max: Optional[int] = Query(None),
    acceptance_max: Optional[float] = Query(None),
    sort_by: Optional[str] = Query("qs_ranking"),  # qs_ranking, tuition_min, acceptance_rate, name
    sort_dir: Optional[str] = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    featured_only: Optional[bool] = Query(False),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Returns paginated, filtered university catalog."""
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    q = db.query(ExplorerUniversity).filter(ExplorerUniversity.is_active == True)

    if search:
        q = q.filter(or_(
            ExplorerUniversity.name.ilike(f"%{search}%"),
            ExplorerUniversity.city.ilike(f"%{search}%"),
            ExplorerUniversity.country.ilike(f"%{search}%"),
        ))
    if country:
        q = q.filter(ExplorerUniversity.country.ilike(f"%{country}%"))
    if city:
        q = q.filter(ExplorerUniversity.city.ilike(f"%{city}%"))
    if university_type:
        q = q.filter(ExplorerUniversity.university_type == university_type)
    if ielts_max is not None:
        q = q.filter(or_(ExplorerUniversity.ielts_requirement == None, ExplorerUniversity.ielts_requirement <= ielts_max))
    if tuition_max is not None:
        q = q.filter(or_(ExplorerUniversity.tuition_min == None, ExplorerUniversity.tuition_min <= tuition_max))
    if scholarship_only:
        q = q.filter(ExplorerUniversity.scholarship_available == True)
    if visa_difficulty:
        q = q.filter(ExplorerUniversity.visa_difficulty == visa_difficulty)
    if ranking_max is not None:
        q = q.filter(or_(ExplorerUniversity.qs_ranking == None, ExplorerUniversity.qs_ranking <= ranking_max))
    if acceptance_max is not None:
        q = q.filter(or_(ExplorerUniversity.acceptance_rate == None, ExplorerUniversity.acceptance_rate <= acceptance_max))
    if featured_only:
        q = q.filter(ExplorerUniversity.is_featured == True)

    # Sorting
    sort_col = getattr(ExplorerUniversity, sort_by, ExplorerUniversity.qs_ranking)
    if sort_dir == "desc":
        q = q.order_by(desc(sort_col).nulls_last())
    else:
        q = q.order_by(asc(sort_col).nulls_last())

    total = q.count()
    unis = q.offset((page - 1) * page_size).limit(page_size).all()

    # Get user's bookmarks for badge display
    user_id = current_user.get("sub")
    bookmarked_ids = {b.university_id for b in db.query(UniversityBookmark).filter(
        UniversityBookmark.user_id == user_id
    ).all()}

    result = []
    for u in unis:
        result.append({
            "id": u.id,
            "slug": u.slug,
            "name": u.name,
            "short_name": u.short_name,
            "country": u.country,
            "city": u.city,
            "university_type": u.university_type,
            "logo_url": u.logo_url,
            "hero_image_url": u.hero_image_url,
            "qs_ranking": u.qs_ranking,
            "the_ranking": u.the_ranking,
            "acceptance_rate": u.acceptance_rate,
            "ielts_requirement": u.ielts_requirement,
            "tuition_display": u.tuition_display,
            "tuition_min": u.tuition_min,
            "living_cost_display": u.living_cost_display,
            "scholarship_available": u.scholarship_available,
            "visa_difficulty": u.visa_difficulty,
            "employment_rate": u.employment_rate,
            "intake_months": u.intake_months,
            "popular_courses": u.popular_courses,
            "total_programs": u.total_programs,
            "is_featured": u.is_featured,
            "is_bookmarked": u.id in bookmarked_ids,
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "data": result
    }


@router.get("/api/explorer/university/{slug}")
def get_university_detail(
    slug: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Returns full university detail including courses, reviews, and scholarship info."""
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    uni = db.query(ExplorerUniversity).filter(ExplorerUniversity.slug == slug, ExplorerUniversity.is_active == True).first()
    if not uni:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="University not found")

    user_id = current_user.get("sub")
    is_bookmarked = db.query(UniversityBookmark).filter(
        UniversityBookmark.user_id == user_id,
        UniversityBookmark.university_id == uni.id
    ).first() is not None

    # Get courses
    courses = db.query(ExplorerCourse).filter(ExplorerCourse.university_id == uni.id, ExplorerCourse.is_active == True).all()

    # Get reviews with average rating
    reviews = db.query(UniversityReview).filter(UniversityReview.university_id == uni.id).order_by(desc(UniversityReview.created_at)).limit(10).all()
    avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else 0

    return {
        "id": uni.id,
        "slug": uni.slug,
        "name": uni.name,
        "short_name": uni.short_name,
        "country": uni.country,
        "city": uni.city,
        "university_type": uni.university_type,
        "founded_year": uni.founded_year,
        "student_population": uni.student_population,
        "website": uni.website,
        "description": uni.description,
        "highlights": uni.highlights,
        "ai_summary": uni.ai_summary,
        "logo_url": uni.logo_url,
        "hero_image_url": uni.hero_image_url,
        "gallery_images": uni.gallery_images or [],
        "qs_ranking": uni.qs_ranking,
        "the_ranking": uni.the_ranking,
        "us_news_ranking": uni.us_news_ranking,
        "national_ranking": uni.national_ranking,
        "acceptance_rate": uni.acceptance_rate,
        "ielts_requirement": uni.ielts_requirement,
        "toefl_requirement": uni.toefl_requirement,
        "pte_requirement": uni.pte_requirement,
        "gre_requirement": uni.gre_requirement,
        "gmat_requirement": uni.gmat_requirement,
        "min_gpa": uni.min_gpa,
        "tuition_display": uni.tuition_display,
        "tuition_min": uni.tuition_min,
        "tuition_max": uni.tuition_max,
        "tuition_currency": uni.tuition_currency,
        "living_cost_display": uni.living_cost_display,
        "application_fee": uni.application_fee,
        "scholarship_available": uni.scholarship_available,
        "scholarship_details": uni.scholarship_details or [],
        "employment_rate": uni.employment_rate,
        "average_salary_post_study": uni.average_salary_post_study,
        "top_employers": uni.top_employers or [],
        "visa_difficulty": uni.visa_difficulty,
        "campus_type": uni.campus_type,
        "accommodation_available": uni.accommodation_available,
        "accommodation_cost_display": uni.accommodation_cost_display,
        "popular_courses": uni.popular_courses or [],
        "intake_months": uni.intake_months or [],
        "total_programs": uni.total_programs,
        "latitude": uni.latitude,
        "longitude": uni.longitude,
        "address": uni.address,
        "is_featured": uni.is_featured,
        "is_bookmarked": is_bookmarked,
        "courses": [
            {
                "id": c.id,
                "slug": c.slug,
                "name": c.name,
                "degree": c.degree,
                "field": c.field,
                "duration_display": c.duration_display,
                "tuition_display": c.tuition_display,
                "ielts_requirement": c.ielts_requirement,
                "scholarship_available": c.scholarship_available,
                "intake_months": c.intake_months or [],
                "career_outcomes": c.career_outcomes or [],
                "salary_estimate_display": c.salary_estimate_display,
                "is_featured": c.is_featured,
            } for c in courses
        ],
        "reviews": [
            {
                "id": r.id,
                "rating": r.rating,
                "pros": r.pros or [],
                "cons": r.cons or [],
                "review_text": r.review_text,
                "program_studied": r.program_studied,
                "graduation_year": r.graduation_year,
                "created_at": r.created_at.isoformat()
            } for r in reviews
        ],
        "average_rating": avg_rating,
        "total_reviews": len(reviews)
    }


# ============================================================
# COURSES ENDPOINTS
# ============================================================

@router.get("/api/explorer/courses")
def list_courses(
    search: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    degree: Optional[str] = Query(None),
    field: Optional[str] = Query(None),
    ielts_max: Optional[float] = Query(None),
    tuition_max: Optional[float] = Query(None),
    scholarship_only: Optional[bool] = Query(False),
    sort_by: Optional[str] = Query("name"),
    sort_dir: Optional[str] = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Returns paginated, filtered course catalog."""
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    q = db.query(ExplorerCourse).filter(ExplorerCourse.is_active == True)

    if search:
        q = q.filter(or_(
            ExplorerCourse.name.ilike(f"%{search}%"),
            ExplorerCourse.field.ilike(f"%{search}%"),
            ExplorerCourse.university_name.ilike(f"%{search}%"),
        ))
    if country:
        q = q.filter(ExplorerCourse.country.ilike(f"%{country}%"))
    if degree:
        q = q.filter(ExplorerCourse.degree.ilike(f"%{degree}%"))
    if field:
        q = q.filter(ExplorerCourse.field.ilike(f"%{field}%"))
    if ielts_max is not None:
        q = q.filter(or_(ExplorerCourse.ielts_requirement == None, ExplorerCourse.ielts_requirement <= ielts_max))
    if tuition_max is not None:
        q = q.filter(or_(ExplorerCourse.tuition_annual == None, ExplorerCourse.tuition_annual <= tuition_max))
    if scholarship_only:
        q = q.filter(ExplorerCourse.scholarship_available == True)

    sort_col = getattr(ExplorerCourse, sort_by if hasattr(ExplorerCourse, sort_by) else "name", ExplorerCourse.name)
    q = q.order_by(desc(sort_col).nulls_last() if sort_dir == "desc" else asc(sort_col).nulls_last())

    total = q.count()
    courses = q.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "data": [
            {
                "id": c.id,
                "slug": c.slug,
                "name": c.name,
                "university_name": c.university_name,
                "country": c.country,
                "degree": c.degree,
                "field": c.field,
                "duration_display": c.duration_display,
                "mode": c.mode,
                "tuition_display": c.tuition_display,
                "ielts_requirement": c.ielts_requirement,
                "scholarship_available": c.scholarship_available,
                "scholarship_amount": c.scholarship_amount,
                "career_outcomes": c.career_outcomes or [],
                "salary_estimate_display": c.salary_estimate_display,
                "employment_rate": c.employment_rate,
                "intake_months": c.intake_months or [],
                "application_deadline": c.application_deadline,
                "is_featured": c.is_featured,
            } for c in courses
        ]
    }


@router.get("/api/explorer/course/{slug}")
def get_course_detail(
    slug: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Returns full course detail."""
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    course = db.query(ExplorerCourse).filter(ExplorerCourse.slug == slug, ExplorerCourse.is_active == True).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    university = db.query(ExplorerUniversity).filter(ExplorerUniversity.id == course.university_id).first()

    return {
        "id": course.id,
        "slug": course.slug,
        "university_id": course.university_id,
        "university_name": course.university_name,
        "university_slug": university.slug if university else None,
        "university_logo": university.logo_url if university else None,
        "country": course.country,
        "name": course.name,
        "degree": course.degree,
        "field": course.field,
        "duration_years": course.duration_years,
        "duration_display": course.duration_display,
        "credits": course.credits,
        "mode": course.mode,
        "tuition_display": course.tuition_display,
        "tuition_annual": course.tuition_annual,
        "tuition_currency": course.tuition_currency,
        "ielts_requirement": course.ielts_requirement,
        "toefl_requirement": course.toefl_requirement,
        "pte_requirement": course.pte_requirement,
        "gre_requirement": course.gre_requirement,
        "gmat_requirement": course.gmat_requirement,
        "min_gpa": course.min_gpa,
        "work_experience_years": course.work_experience_years,
        "other_requirements": course.other_requirements or [],
        "scholarship_available": course.scholarship_available,
        "scholarship_amount": course.scholarship_amount,
        "career_outcomes": course.career_outcomes or [],
        "salary_estimate_display": course.salary_estimate_display,
        "employment_rate": course.employment_rate,
        "intake_months": course.intake_months or [],
        "application_deadline": course.application_deadline,
        "description": course.description,
        "curriculum_highlights": course.curriculum_highlights or [],
    }


# ============================================================
# COUNTRIES ENDPOINTS
# ============================================================

@router.get("/api/explorer/countries")
def list_countries(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Returns all active country records."""
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    countries = db.query(ExplorerCountry).filter(ExplorerCountry.is_active == True).order_by(
        desc(ExplorerCountry.is_featured), ExplorerCountry.name
    ).all()

    return [
        {
            "id": c.id,
            "slug": c.slug,
            "name": c.name,
            "flag_emoji": c.flag_emoji,
            "hero_image_url": c.hero_image_url,
            "living_cost_monthly_display": c.living_cost_monthly_display,
            "student_visa_name": c.student_visa_name,
            "post_study_work_duration": c.post_study_work_duration,
            "average_salary_display": c.average_salary_display,
            "visa_difficulty": c.visa_difficulty,
            "total_universities": c.total_universities,
            "popular_courses": c.popular_courses or [],
            "is_featured": c.is_featured
        } for c in countries
    ]


@router.get("/api/explorer/country/{slug}")
def get_country_detail(
    slug: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Returns full country overview page data."""
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    country = db.query(ExplorerCountry).filter(ExplorerCountry.slug == slug).first()
    if not country:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Country not found")

    # Get universities in this country (up to 6 featured)
    unis = db.query(ExplorerUniversity).filter(
        ExplorerUniversity.country == country.name,
        ExplorerUniversity.is_active == True
    ).order_by(asc(ExplorerUniversity.qs_ranking).nulls_last()).limit(6).all()

    uni_data = [
        {
            "id": u.id, "slug": u.slug, "name": u.name,
            "qs_ranking": u.qs_ranking, "city": u.city,
            "tuition_display": u.tuition_display,
            "logo_url": u.logo_url, "hero_image_url": u.hero_image_url
        } for u in unis
    ]

    return {
        "id": country.id,
        "slug": country.slug,
        "name": country.name,
        "flag_emoji": country.flag_emoji,
        "hero_image_url": country.hero_image_url,
        "description": country.description,
        "living_cost_monthly_display": country.living_cost_monthly_display,
        "avg_rent_display": country.avg_rent_display,
        "avg_food_display": country.avg_food_display,
        "avg_transport_display": country.avg_transport_display,
        "student_visa_name": country.student_visa_name,
        "visa_processing_time": country.visa_processing_time,
        "visa_fee_display": country.visa_fee_display,
        "visa_requirements_summary": country.visa_requirements_summary or [],
        "visa_difficulty": country.visa_difficulty,
        "work_rights_during_study": country.work_rights_during_study,
        "work_hours_per_week": country.work_hours_per_week,
        "post_study_work_visa": country.post_study_work_visa,
        "post_study_work_duration": country.post_study_work_duration,
        "average_salary_display": country.average_salary_display,
        "top_industries": country.top_industries or [],
        "popular_courses": country.popular_courses or [],
        "climate": country.climate,
        "official_language": country.official_language,
        "currency": country.currency,
        "government_scholarships": country.government_scholarships or [],
        "ai_summary": country.ai_summary,
        "total_universities": country.total_universities,
        "top_universities": uni_data
    }


# ============================================================
# SEARCH ENDPOINT
# ============================================================

@router.get("/api/explorer/search")
def global_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(8),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Global autocomplete search across universities, courses, and countries."""
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    user_id = current_user.get("sub")

    unis = db.query(ExplorerUniversity).filter(
        ExplorerUniversity.is_active == True,
        or_(
            ExplorerUniversity.name.ilike(f"%{q}%"),
            ExplorerUniversity.city.ilike(f"%{q}%"),
            ExplorerUniversity.country.ilike(f"%{q}%")
        )
    ).limit(limit // 2).all()

    courses = db.query(ExplorerCourse).filter(
        ExplorerCourse.is_active == True,
        or_(
            ExplorerCourse.name.ilike(f"%{q}%"),
            ExplorerCourse.field.ilike(f"%{q}%")
        )
    ).limit(limit // 2).all()

    countries = db.query(ExplorerCountry).filter(
        ExplorerCountry.is_active == True,
        ExplorerCountry.name.ilike(f"%{q}%")
    ).limit(4).all()

    # Log recent search
    try:
        db.add(ExplorerRecentSearch(user_id=user_id, query=q, search_type="global"))
        db.commit()
    except Exception:
        pass

    return {
        "universities": [{"id": u.id, "slug": u.slug, "name": u.name, "country": u.country, "qs_ranking": u.qs_ranking, "type": "university"} for u in unis],
        "courses": [{"id": c.id, "slug": c.slug, "name": c.name, "university_name": c.university_name, "degree": c.degree, "type": "course"} for c in courses],
        "countries": [{"slug": c.slug, "name": c.name, "flag_emoji": c.flag_emoji, "type": "country"} for c in countries]
    }


@router.get("/api/explorer/recent-searches")
def get_recent_searches(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    user_id = current_user.get("sub")
    searches = db.query(ExplorerRecentSearch).filter(
        ExplorerRecentSearch.user_id == user_id
    ).order_by(desc(ExplorerRecentSearch.created_at)).limit(8).all()

    seen = set()
    unique = []
    for s in searches:
        if s.query not in seen:
            seen.add(s.query)
            unique.append({"id": s.id, "query": s.query, "search_type": s.search_type})
    return unique


# ============================================================
# BOOKMARK ENDPOINTS
# ============================================================

@router.post("/api/explorer/bookmark", status_code=status.HTTP_201_CREATED)
def create_bookmark(
    payload: BookmarkInput,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Save a university, course, or country to bookmarks."""
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    user_id = current_user.get("sub")

    if payload.type == "university":
        existing = db.query(UniversityBookmark).filter(
            UniversityBookmark.user_id == user_id,
            UniversityBookmark.university_id == payload.item_id
        ).first()
        if existing:
            return {"message": "Already bookmarked", "id": existing.id}
        bm = UniversityBookmark(user_id=user_id, university_id=payload.item_id, collection_name=payload.collection_name or "My Shortlist")
        db.add(bm)

    elif payload.type == "course":
        existing = db.query(CourseBookmark).filter(
            CourseBookmark.user_id == user_id,
            CourseBookmark.course_id == payload.item_id
        ).first()
        if existing:
            return {"message": "Already bookmarked", "id": existing.id}
        bm = CourseBookmark(user_id=user_id, course_id=payload.item_id, collection_name=payload.collection_name or "My Courses")
        db.add(bm)

    elif payload.type == "country":
        existing = db.query(CountryBookmark).filter(
            CountryBookmark.user_id == user_id,
            CountryBookmark.country_slug == payload.item_id
        ).first()
        if existing:
            return {"message": "Already bookmarked", "id": existing.id}
        bm = CountryBookmark(user_id=user_id, country_slug=payload.item_id)
        db.add(bm)
    else:
        raise HTTPException(status_code=400, detail="Invalid bookmark type")

    db.commit()
    return {"message": "Bookmarked successfully"}


@router.get("/api/explorer/bookmarks")
def get_bookmarks(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Returns all user bookmarks grouped by type."""
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    user_id = current_user.get("sub")

    uni_bms = db.query(UniversityBookmark).filter(UniversityBookmark.user_id == user_id).all()
    course_bms = db.query(CourseBookmark).filter(CourseBookmark.user_id == user_id).all()
    country_bms = db.query(CountryBookmark).filter(CountryBookmark.user_id == user_id).all()

    universities = []
    for bm in uni_bms:
        uni = db.query(ExplorerUniversity).filter(ExplorerUniversity.id == bm.university_id).first()
        if uni:
            universities.append({
                "bookmark_id": bm.id, "collection_name": bm.collection_name,
                "id": uni.id, "slug": uni.slug, "name": uni.name,
                "country": uni.country, "city": uni.city,
                "qs_ranking": uni.qs_ranking, "tuition_display": uni.tuition_display,
                "logo_url": uni.logo_url, "hero_image_url": uni.hero_image_url,
                "scholarship_available": uni.scholarship_available,
                "visa_difficulty": uni.visa_difficulty
            })

    courses = []
    for bm in course_bms:
        course = db.query(ExplorerCourse).filter(ExplorerCourse.id == bm.course_id).first()
        if course:
            courses.append({
                "bookmark_id": bm.id, "collection_name": bm.collection_name,
                "id": course.id, "slug": course.slug, "name": course.name,
                "university_name": course.university_name, "country": course.country,
                "degree": course.degree, "tuition_display": course.tuition_display,
                "duration_display": course.duration_display,
                "salary_estimate_display": course.salary_estimate_display
            })

    countries = []
    for bm in country_bms:
        c = db.query(ExplorerCountry).filter(ExplorerCountry.slug == bm.country_slug).first()
        if c:
            countries.append({
                "bookmark_id": bm.id,
                "slug": c.slug, "name": c.name, "flag_emoji": c.flag_emoji,
                "living_cost_monthly_display": c.living_cost_monthly_display,
                "post_study_work_duration": c.post_study_work_duration,
                "visa_difficulty": c.visa_difficulty, "total_universities": c.total_universities
            })

    return {"universities": universities, "courses": courses, "countries": countries}


@router.delete("/api/explorer/bookmark/{bookmark_id}")
def delete_bookmark(
    bookmark_id: str,
    bookmark_type: str = Query(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Remove a bookmark."""
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    user_id = current_user.get("sub")

    if bookmark_type == "university":
        bm = db.query(UniversityBookmark).filter(UniversityBookmark.id == bookmark_id, UniversityBookmark.user_id == user_id).first()
    elif bookmark_type == "course":
        bm = db.query(CourseBookmark).filter(CourseBookmark.id == bookmark_id, CourseBookmark.user_id == user_id).first()
    elif bookmark_type == "country":
        bm = db.query(CountryBookmark).filter(CountryBookmark.id == bookmark_id, CountryBookmark.user_id == user_id).first()
    else:
        raise HTTPException(status_code=400, detail="Invalid type")

    if not bm:
        raise HTTPException(status_code=404, detail="Bookmark not found")

    db.delete(bm)
    db.commit()
    return {"message": "Bookmark removed"}


# ============================================================
# COMPARISON ENDPOINTS
# ============================================================

@router.post("/api/explorer/compare")
def save_comparison(
    payload: CompareInput,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    user_id = current_user.get("sub")
    comparison = ExplorerComparison(user_id=user_id, name=payload.name, university_slugs=payload.university_slugs)
    db.add(comparison)
    db.commit()
    db.refresh(comparison)
    return {"id": comparison.id, "message": "Comparison saved"}


@router.get("/api/explorer/compare")
def get_comparisons(
    slugs: str = Query(..., description="Comma-separated university slugs"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Returns full university data for comparison view."""
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    slug_list = [s.strip() for s in slugs.split(",") if s.strip()][:5]
    unis = db.query(ExplorerUniversity).filter(ExplorerUniversity.slug.in_(slug_list)).all()

    return [
        {
            "id": u.id, "slug": u.slug, "name": u.name, "country": u.country,
            "city": u.city, "qs_ranking": u.qs_ranking, "the_ranking": u.the_ranking,
            "acceptance_rate": u.acceptance_rate,
            "ielts_requirement": u.ielts_requirement,
            "tuition_display": u.tuition_display, "tuition_min": u.tuition_min,
            "living_cost_display": u.living_cost_display,
            "scholarship_available": u.scholarship_available,
            "scholarship_details": u.scholarship_details or [],
            "employment_rate": u.employment_rate,
            "average_salary_post_study": u.average_salary_post_study,
            "visa_difficulty": u.visa_difficulty,
            "highlights": u.highlights or [],
            "intake_months": u.intake_months or [],
            "total_programs": u.total_programs,
            "logo_url": u.logo_url,
            "hero_image_url": u.hero_image_url,
            "website": u.website,
        } for u in unis
    ]


# ============================================================
# REVIEWS ENDPOINTS
# ============================================================

@router.post("/api/explorer/review", status_code=status.HTTP_201_CREATED)
def submit_review(
    payload: ReviewInput,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    user_id = current_user.get("sub")
    review = UniversityReview(
        university_id=payload.university_id,
        user_id=user_id,
        rating=payload.rating,
        pros=payload.pros,
        cons=payload.cons,
        review_text=payload.review_text,
        program_studied=payload.program_studied,
        graduation_year=payload.graduation_year
    )
    db.add(review)
    db.commit()
    return {"message": "Review submitted successfully"}


# ============================================================
# AI SUMMARY ENDPOINT
# ============================================================

@router.post("/api/explorer/ai-summary")
def generate_ai_summary(
    payload: AISummaryInput,
    current_user: dict = Depends(get_current_user)
):
    """Returns an AI-powered personalized university analysis for the student."""
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    summary = get_ai_university_summary(
        university_name=payload.university_name,
        country=payload.country,
        course=payload.course,
        student_profile=payload.student_profile
    )
    return {"summary": summary}


# ============================================================
# APPLY NOW ENDPOINT — creates Application + Journey integration
# ============================================================

@router.post("/api/explorer/apply", status_code=status.HTTP_201_CREATED)
def apply_to_university(
    payload: ApplyInput,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Creates a new Application pipeline entry and integrates with Journey Engine.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    user_id = current_user.get("sub")

    uni = db.query(ExplorerUniversity).filter(ExplorerUniversity.id == payload.university_id).first()
    if not uni:
        raise HTTPException(status_code=404, detail="University not found")

    course_name = "General Program"
    if payload.course_id:
        course = db.query(ExplorerCourse).filter(ExplorerCourse.id == payload.course_id).first()
        if course:
            course_name = f"{course.name} ({course.degree})"

    # Check duplicate
    dup = db.query(Application).filter(
        Application.user_id == user_id,
        Application.university == uni.name
    ).first()
    if dup:
        return {"message": "Application already exists", "application_id": dup.id}

    # Create Application record
    app = Application(
        user_id=user_id,
        university=uni.name,
        country=uni.country,
        course=course_name,
        degree="Master's",
        intake=payload.intake or "Fall 2026",
        tuition_fee=uni.tuition_display,
        current_status="Interested",
        priority="High",
        notes=f"Applied via Explorer. Campus: {uni.city}, {uni.country}."
    )
    db.add(app)
    db.commit()
    db.refresh(app)

    # Insert default document checklist
    for doc_name in ["Passport", "Transcripts", "Resume/CV", "Statement of Purpose (SOP)", "Letters of Recommendation", "Financial Documents", "English Test Scores"]:
        db.add(ApplicationDocument(application_id=app.id, document_name=doc_name, status="Pending"))

    # Timeline entry
    db.add(ApplicationTimeline(
        application_id=app.id,
        event_title="Application Created via Explorer",
        event_description=f"Student expressed interest in {uni.name} through the University Explorer."
    ))

    # Calendar event for deadline
    if uni.intake_months:
        db.add(CalendarEvent(
            user_id=user_id,
            event_title=f"Application Deadline: {uni.name}",
            event_type="Application Deadline",
            event_date=f"2026-12-01",
            reference_id=app.id
        ))

    db.commit()

    # Trigger Journey Automation
    try:
        from ..services.journey_automation import JourneyAutomationService
        JourneyAutomationService.on_university_saved(
            db=db,
            user_id=user_id,
            uni_name=uni.name,
            country=uni.country,
            course=course_name,
            tuition=uni.tuition_display
        )
    except Exception as e:
        logger.error(f"Journey automation failed on Explorer apply: {str(e)}")

    return {
        "message": "Application created successfully",
        "application_id": app.id,
        "university": uni.name,
        "redirect": "/dashboard?tab=journey"
    }


# ============================================================
# FEATURED / HOMEPAGE ENDPOINT
# ============================================================

@router.get("/api/explorer/featured")
def get_featured(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Returns featured universities, countries, and courses for the Explorer homepage."""
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    unis = db.query(ExplorerUniversity).filter(
        ExplorerUniversity.is_featured == True, ExplorerUniversity.is_active == True
    ).order_by(asc(ExplorerUniversity.qs_ranking).nulls_last()).limit(8).all()

    countries = db.query(ExplorerCountry).filter(
        ExplorerCountry.is_featured == True, ExplorerCountry.is_active == True
    ).order_by(ExplorerCountry.name).all()

    courses = db.query(ExplorerCourse).filter(
        ExplorerCourse.is_featured == True, ExplorerCourse.is_active == True
    ).limit(6).all()

    return {
        "featured_universities": [
            {
                "id": u.id, "slug": u.slug, "name": u.name,
                "country": u.country, "city": u.city,
                "qs_ranking": u.qs_ranking, "hero_image_url": u.hero_image_url,
                "logo_url": u.logo_url, "tuition_display": u.tuition_display,
                "scholarship_available": u.scholarship_available,
                "acceptance_rate": u.acceptance_rate,
                "employment_rate": u.employment_rate
            } for u in unis
        ],
        "featured_countries": [
            {
                "slug": c.slug, "name": c.name, "flag_emoji": c.flag_emoji,
                "hero_image_url": c.hero_image_url,
                "living_cost_monthly_display": c.living_cost_monthly_display,
                "post_study_work_duration": c.post_study_work_duration,
                "visa_difficulty": c.visa_difficulty,
                "total_universities": c.total_universities
            } for c in countries
        ],
        "trending_courses": [
            {
                "id": c.id, "slug": c.slug, "name": c.name,
                "university_name": c.university_name, "degree": c.degree,
                "field": c.field, "tuition_display": c.tuition_display,
                "salary_estimate_display": c.salary_estimate_display
            } for c in courses
        ]
    }
