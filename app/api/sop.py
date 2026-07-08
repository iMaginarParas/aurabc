import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional

from ..database import get_db
from ..auth import get_current_user
from ..models import Service, Order, SOPDocument, SOPVersion, EligibilityRequest
from ..services.notifications.dispatcher import dispatch_whatsapp_event
from ..schemas import (
    SOPGenerateRequest,
    SOPDocumentSave,
    SOPRewriteRequest,
    SOPDocumentResponse,
    SOPVersionResponse
)
from ..services.sop_service import (
    generate_sop_draft,
    rewrite_sop_segment
)
from ..rate_limiter import rate_limit


logger = logging.getLogger(__name__)
router = APIRouter(tags=["sop"])

def verify_sop_purchase(db: Session, user_id: str):
    """
    Enforces access control. Verifies if there is a paid order for the 'ai-sop-generator' service for the specific user.
    Raises HTTP 402 if not paid.
    """
    logger.info(f"Verifying purchase authorization for AI SOP Generator for user {user_id}...")
    # Lookup paid orders for the AI SOP Generator
    paid_order = db.query(Order).join(Service).filter(
        Order.user_id == user_id,
        Order.payment_status == "paid",
        Service.slug == "ai-sop-generator"
    ).first()
    
    if not paid_order:
        logger.warning(f"No paid order found for user {user_id} for AI SOP Generator. Access denied.")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Access Locked: Please purchase the AI SOP Generator package to unlock this feature."
        )
    logger.info("Access authorized.")
    return True


@router.post("/api/sop/generate", response_model=SOPDocumentResponse, status_code=status.HTTP_201_CREATED)
def generate_sop(
    payload: SOPGenerateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    _rl: None = Depends(rate_limit(limit=5, window_seconds=60))
):
    """
    Validates purchase lock, generates Statement of Purpose, and creates database records.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    verify_sop_purchase(db, user_id)

    try:
        # Extract metadata
        target_country = payload.target_education.country
        target_university = payload.target_education.university
        target_course = payload.target_education.course
        title = f"SOP - {target_course} at {target_university}"

        logger.info(f"Generating initial SOP for: {title}")
        # Convert Pydantic payload to dictionary
        profile_dict = payload.dict()
        sop_html = generate_sop_draft(profile_dict)

        # 1. Create Document record
        db_doc = SOPDocument(
            user_id=user_id,
            title=title,
            target_country=target_country,
            target_university=target_university,
            target_course=target_course,
            content=sop_html,
            ai_model="gpt-4o-mini",
            version=1
        )
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)

        # 2. Save version history log
        db_version = SOPVersion(
            document_id=db_doc.id,
            version_number=1,
            content=sop_html,
            changes="Initial AI Draft Generation"
        )
        db.add(db_version)
        db.commit()
        db.refresh(db_doc)

        # Trigger Journey Automation
        try:
            from ..services.journey_automation import JourneyAutomationService
            JourneyAutomationService.on_sop_generated(
                db=db,
                user_id=user_id,
                doc_title=title
            )
        except Exception as journey_err:
            logger.error(f"Failed to trigger SOP generation automation: {str(journey_err)}")

        # Dispatch WhatsApp Notification
        try:
            profile = db.query(EligibilityRequest).filter(EligibilityRequest.email == current_user.get("email")).first()
            phone = profile.phone if profile else "+919891263337"
            dispatch_whatsapp_event(
                db=db,
                user_id=user_id,
                event_type="SOP_GENERATED",
                payload={"student_name": payload.personal_info.full_name},
                phone_number=phone
            )
        except Exception as dispatch_err:
            logger.error(f"Failed to auto-dispatch WhatsApp notification: {str(dispatch_err)}")

        return db_doc
    except Exception as e:
        logger.error(f"SOP generation API failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate SOP. Please retry."
        )


@router.post("/api/sop/regenerate/{document_id}", response_model=SOPDocumentResponse)
def regenerate_sop(
    document_id: str,
    payload: SOPGenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Completely regenerates the SOP, increments version number, and saves version history.
    """
    db_doc = db.query(SOPDocument).filter(SOPDocument.id == document_id).first()
    if not db_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SOP Document not found."
        )

    try:
        profile_dict = payload.dict()
        new_sop_html = generate_sop_draft(profile_dict)

        # Increment version
        new_version_num = db_doc.version + 1
        db_doc.version = new_version_num
        db_doc.content = new_sop_html
        
        # Save version history log
        db_version = SOPVersion(
            document_id=db_doc.id,
            version_number=new_version_num,
            content=new_sop_html,
            changes=f"Regenerated Draft (Version {new_version_num})"
        )
        
        db.add(db_version)
        db.commit()
        db.refresh(db_doc)
        return db_doc
    except Exception as e:
        logger.error(f"Regeneration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate draft."
        )


@router.post("/api/sop/rewrite/{document_id}")
def rewrite_sop(
    document_id: str,
    payload: SOPRewriteRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Performs section rewrite edits (grammar, vocabulary, professionalize, expand, etc.) and autosaves.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    db_doc = db.query(SOPDocument).filter(
        SOPDocument.id == document_id,
        SOPDocument.user_id == user_id
    ).first()
    if not db_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SOP Document not found."
        )

    try:
        updated_content = rewrite_sop_segment(
            content=payload.content,
            instruction=payload.instruction,
            selected_text=payload.selected_text
        )

        # Autosave the modification to the document content
        db_doc.content = updated_content
        db.commit()
        db.refresh(db_doc)

        return {"content": updated_content, "version": db_doc.version}
    except Exception as e:
        logger.error(f"Rewrite API failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Assistant editing failed. Please retry."
        )


@router.put("/api/sop/save/{document_id}", response_model=SOPDocumentResponse)
def save_sop(
    document_id: str,
    payload: SOPDocumentSave,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Manually or autosaves text modifications from the rich text editor dashboard.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    db_doc = db.query(SOPDocument).filter(
        SOPDocument.id == document_id,
        SOPDocument.user_id == user_id
    ).first()
    if not db_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SOP Document not found."
        )

    db_doc.title = payload.title
    db_doc.content = payload.content
    db.commit()
    db.refresh(db_doc)
    return db_doc


@router.get("/api/sop/history", response_model=List[SOPDocumentResponse])
def get_sop_history(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves all previously drafted SOP document cards.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    return db.query(SOPDocument).filter(SOPDocument.user_id == user_id).order_by(desc(SOPDocument.updated_at)).all()


@router.get("/api/sop/{document_id}", response_model=SOPDocumentResponse)
def get_sop_by_id(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves a specific SOP document and its full version history logs.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    db_doc = db.query(SOPDocument).filter(
        SOPDocument.id == document_id,
        SOPDocument.user_id == user_id
    ).first()
    if not db_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SOP Document not found."
        )
    return db_doc


@router.delete("/api/sop/{document_id}", status_code=status.HTTP_200_OK)
def delete_sop(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Deletes the document from log registers.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    db_doc = db.query(SOPDocument).filter(
        SOPDocument.id == document_id,
        SOPDocument.user_id == user_id
    ).first()
    if not db_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SOP Document not found."
        )
    db.delete(db_doc)
    db.commit()
    return {"message": "Document deleted successfully."}
