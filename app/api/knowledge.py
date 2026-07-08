from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from typing import List, Optional, Dict, Any
from ..database import SessionLocal
from ..auth import get_current_user
from ..models import KCCategory, KCArticle, KCBookmark, KCReadingHistory, KCArticleLike, KCAIGeneratedDraft
from ..services.knowledge_service import generate_article_with_ai, ask_ai_about_article, get_personalized_articles

router = APIRouter(prefix="/api", tags=["Knowledge Center"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/articles")
def get_articles(
    category: Optional[str] = None,
    country: Optional[str] = None,
    tag: Optional[str] = None,
    difficulty: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get paginated, filterable articles."""
    query = db.query(KCArticle).filter(KCArticle.is_published == True, KCArticle.is_active == True)
    
    if category:
        # Resolve category by slug or name
        cat = db.query(KCCategory).filter(or_(KCCategory.slug == category, KCCategory.name.ilike(category))).first()
        if cat:
            query = query.filter(KCArticle.category_id == cat.id)
            
    if country:
        query = query.filter(KCArticle.country.ilike(country))
        
    if difficulty:
        query = query.filter(KCArticle.difficulty.ilike(difficulty))
        
    if tag:
        # tag filtering (tags is JSON array)
        query = query.filter(KCArticle.tags.contains([tag]))
        
    if q:
        query = query.filter(
            or_(
                KCArticle.title.ilike(f"%{q}%"),
                KCArticle.subtitle.ilike(f"%{q}%"),
                KCArticle.excerpt.ilike(f"%{q}%")
            )
        )
        
    total = query.count()
    offset = (page - 1) * limit
    articles = query.order_by(desc(KCArticle.published_at)).offset(offset).limit(limit).all()
    
    return {
        "data": articles,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit if total > 0 else 1
    }

@router.get("/article/{slug}")
def get_article_detail(slug: str, user: Optional[dict] = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get single article by slug. Increments view count."""
    article = db.query(KCArticle).filter(KCArticle.slug == slug, KCArticle.is_published == True, KCArticle.is_active == True).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
        
    # Increment view count
    article.view_count = (article.view_count or 0) + 1
    db.commit()
    db.refresh(article)
    
    # Check if liked and bookmarked if user is authenticated
    is_bookmarked = False
    is_liked = False
    
    if user and user.get("sub") != "guest_user":
        user_id = user["sub"]
        bk = db.query(KCBookmark).filter(KCBookmark.user_id == user_id, KCBookmark.article_id == article.id).first()
        is_bookmarked = bk is not None
        
        lk = db.query(KCArticleLike).filter(KCArticleLike.user_id == user_id, KCArticleLike.article_id == article.id).first()
        is_liked = lk is not None
        
    return {
        "article": article,
        "is_bookmarked": is_bookmarked,
        "is_liked": is_liked
    }

@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    """Get all categories with active article counts."""
    categories = db.query(KCCategory).filter(KCCategory.is_active == True).order_by(KCCategory.display_order).all()
    # Recalculate article counts dynamically
    for cat in categories:
        count = db.query(KCArticle).filter(KCArticle.category_id == cat.id, KCArticle.is_published == True).count()
        cat.article_count = count
    db.commit()
    return categories

@router.post("/bookmark")
def toggle_bookmark(payload: Dict[str, Any], user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Bookmark or unbookmark an article."""
    if not user or user.get("sub") == "guest_user":
        raise HTTPException(status_code=401, detail="Authentication required for bookmarking")
        
    user_id = user["sub"]
    article_id = payload.get("article_id")
    collection_name = payload.get("collection_name", "My Saves")
    
    if not article_id:
        raise HTTPException(status_code=400, detail="Missing article_id")
        
    article = db.query(KCArticle).filter(KCArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
        
    bookmark = db.query(KCBookmark).filter(KCBookmark.user_id == user_id, KCBookmark.article_id == article_id).first()
    
    if bookmark:
        db.delete(bookmark)
        article.bookmark_count = max(0, (article.bookmark_count or 1) - 1)
        db.commit()
        return {"status": "removed", "bookmarked": False}
    else:
        new_bookmark = KCBookmark(user_id=user_id, article_id=article_id, collection_name=collection_name)
        db.add(new_bookmark)
        article.bookmark_count = (article.bookmark_count or 0) + 1
        db.commit()
        return {"status": "added", "bookmarked": True}

@router.get("/bookmarks")
def get_bookmarks(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get all articles bookmarked by the user."""
    if not user or user.get("sub") == "guest_user":
        raise HTTPException(status_code=401, detail="Authentication required")
        
    user_id = user["sub"]
    bookmarks = db.query(KCBookmark).filter(KCBookmark.user_id == user_id).all()
    
    data = []
    for bk in bookmarks:
        art = db.query(KCArticle).filter(KCArticle.id == bk.article_id).first()
        if art:
            data.append({
                "bookmark_id": bk.id,
                "collection_name": bk.collection_name,
                "created_at": bk.created_at,
                "article": art
            })
            
    return data

@router.post("/like")
def toggle_like(payload: Dict[str, Any], user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Like or unlike an article."""
    if not user or user.get("sub") == "guest_user":
        raise HTTPException(status_code=401, detail="Authentication required")
        
    user_id = user["sub"]
    article_id = payload.get("article_id")
    
    if not article_id:
        raise HTTPException(status_code=400, detail="Missing article_id")
        
    article = db.query(KCArticle).filter(KCArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
        
    like = db.query(KCArticleLike).filter(KCArticleLike.user_id == user_id, KCArticleLike.article_id == article_id).first()
    
    if like:
        db.delete(like)
        article.like_count = max(0, (article.like_count or 1) - 1)
        db.commit()
        return {"status": "unliked", "liked": False}
    else:
        new_like = KCArticleLike(user_id=user_id, article_id=article_id)
        db.add(new_like)
        article.like_count = (article.like_count or 0) + 1
        db.commit()
        return {"status": "liked", "liked": True}

@router.post("/history")
def update_reading_history(payload: Dict[str, Any], user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Save progress for currently reading article."""
    if not user or user.get("sub") == "guest_user":
        return {"status": "ignored", "detail": "guest_user"}
        
    user_id = user["sub"]
    article_id = payload.get("article_id")
    progress = payload.get("progress_percent", 0)
    
    if not article_id:
        raise HTTPException(status_code=400, detail="Missing article_id")
        
    history = db.query(KCReadingHistory).filter(KCReadingHistory.user_id == user_id, KCReadingHistory.article_id == article_id).first()
    
    if history:
        history.progress_percent = max(history.progress_percent, progress)
        history.last_read_at = datetime.utcnow()
        if progress >= 90:
            history.completed = True
        db.commit()
    else:
        new_hist = KCReadingHistory(
            user_id=user_id,
            article_id=article_id,
            progress_percent=progress,
            completed=progress >= 90
        )
        db.add(new_hist)
        db.commit()
        
    return {"status": "success"}

@router.get("/history")
def get_reading_history(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get the user's reading history."""
    if not user or user.get("sub") == "guest_user":
        raise HTTPException(status_code=401, detail="Authentication required")
        
    user_id = user["sub"]
    history = db.query(KCReadingHistory).filter(KCReadingHistory.user_id == user_id).order_by(desc(KCReadingHistory.last_read_at)).limit(20).all()
    
    data = []
    for hist in history:
        art = db.query(KCArticle).filter(KCArticle.id == hist.article_id).first()
        if art:
            data.append({
                "history_id": hist.id,
                "progress_percent": hist.progress_percent,
                "last_read_at": hist.last_read_at,
                "completed": hist.completed,
                "article": art
            })
            
    return data

@router.post("/ask-ai")
def ask_ai_article(payload: Dict[str, Any], user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ask Aura AI about a specific article."""
    if not user or user.get("sub") == "guest_user":
        raise HTTPException(status_code=401, detail="Authentication required to query Aura AI")
        
    article_id = payload.get("article_id")
    question = payload.get("question", "")
    mode = payload.get("mode", "custom")
    
    if not article_id:
        raise HTTPException(status_code=400, detail="Missing article_id")
        
    article = db.query(KCArticle).filter(KCArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
        
    answer = ask_ai_about_article(
        article_title=article.title,
        article_excerpt=article.excerpt or "",
        article_content=article.content_blocks or [],
        question=question,
        mode=mode
    )
    return {"answer": answer}

@router.post("/article/generate")
def generate_article(payload: Dict[str, Any], user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Admin-only: Generate country/visa/scholarship guide with AI and store as draft."""
    # Since there is no formal admin flag in base auth setup, we check if the user is authenticated (not guest).
    if not user or user.get("sub") == "guest_user":
        raise HTTPException(status_code=401, detail="Admin permissions required")
        
    topic = payload.get("topic")
    category_slug = payload.get("category_slug")
    country = payload.get("country")
    
    if not topic or not category_slug:
        raise HTTPException(status_code=400, detail="topic and category_slug are required")
        
    result = generate_article_with_ai(topic=topic, category_slug=category_slug, country=country, db=db)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
        
    return result

@router.get("/learn/featured")
def get_featured_articles(db: Session = Depends(get_db)):
    """Get featured, popular, and trending articles for homepage."""
    featured = db.query(KCArticle).filter(KCArticle.is_published == True, KCArticle.is_featured == True).order_by(desc(KCArticle.published_at)).limit(3).all()
    trending = db.query(KCArticle).filter(KCArticle.is_published == True).order_by(desc(KCArticle.view_count)).limit(6).all()
    latest = db.query(KCArticle).filter(KCArticle.is_published == True).order_by(desc(KCArticle.published_at)).limit(6).all()
    
    return {
        "featured": featured,
        "trending": trending,
        "latest": latest
    }

@router.get("/learn/personalized")
def get_personalized(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get personalized article recommendations."""
    # Default tags/preferences or fallback to user settings
    preferred_country = None
    preferred_course = None
    
    # We can attempt to pull from UserSetting or EligibilityRequest if available
    user_id = user.get("sub") if user else "guest_user"
    
    # Let's import inside to avoid circular reference or issues if not present
    from ..models import UserSetting, EligibilityRequest
    
    if user_id != "guest_user":
        settings_rec = db.query(UserSetting).filter(UserSetting.user_id == user_id).first()
        if settings_rec:
            # Check what properties exist on UserSetting. We can try to safe check.
            preferred_country = getattr(settings_rec, "preferred_country", None)
            preferred_course = getattr(settings_rec, "preferred_course", None)
            
        if not preferred_country:
            elig = db.query(EligibilityRequest).filter(EligibilityRequest.email == user.get("email")).order_by(desc(EligibilityRequest.created_at)).first()
            if elig:
                preferred_country = elig.preferred_country
                preferred_course = elig.preferred_course
                
    recs = get_personalized_articles(user_id=user_id, preferred_country=preferred_country, preferred_course=preferred_course, db=db)
    return recs
