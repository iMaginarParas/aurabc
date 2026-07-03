import os
import shutil
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional

from ..database import get_db
from ..auth import get_current_user
from ..models import Service, Order, VisaDocumentCheck, UploadedDocument, DocumentAnalysis
from ..schemas import (
    VisaCheckResponse,
    UploadedDocumentResponse,
    VisaCheckStart
)
from ..services.visa_service import (
    evaluate_visa_documents_ai
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["visa_checker"])

UPLOAD_DIR = os.path.join("backend", "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def verify_visa_checker_purchase(db: Session):
    """
    Enforces purchase locks. Verifies if there is a paid order for the 'ai-visa-doc-checker' service.
    """
    logger.info("Verifying purchase authorization for AI Visa Document Checker...")
    paid_order = db.query(Order).join(Service).filter(
        Order.payment_status == "paid",
        Service.slug == "ai-visa-doc-checker"
    ).first()
    
    if not paid_order:
        logger.warning("No paid order found for AI Visa Document Checker. Access denied.")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Access Locked: Please purchase the AI Visa Document Checker package to unlock this feature."
        )
    logger.info("Access authorized.")
    return True


@router.post("/api/visa-check/upload", response_model=UploadedDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_visa_document(
    check_id: str = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Saves an uploaded document file inside a local directory and logs file metadata.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    # Verify that the VisaCheck reference exists and belongs to the user
    check = db.query(VisaDocumentCheck).filter(
        VisaDocumentCheck.id == check_id,
        VisaDocumentCheck.user_id == user_id
    ).first()
    if not check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parent Visa Document Check reference not found."
        )

    # Validate file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".jpg", ".jpeg", ".png"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Only PDF, JPG, JPEG, and PNG are allowed."
        )

    try:
        # Generate unique file path
        unique_name = f"{uuid.uuid4().hex}{ext}"
        content = await file.read()
        file_size = len(content)

        # Upload to Supabase Storage
        from ..services.storage_service import upload_file_to_supabase
        storage_url = upload_file_to_supabase("documents", unique_name, content, file.content_type or "application/octet-stream")
        
        # Log to Database
        db_doc = UploadedDocument(
            check_id=check_id,
            document_type=document_type,
            filename=file.filename,
            content_type=file.content_type,
            file_size=file_size,
            file_path=storage_url
        )
        
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)
        return db_doc
    except Exception as e:
        logger.error(f"File upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded document to storage: {str(e)}"
        )


@router.post("/api/visa-check/analyze/{check_id}", response_model=VisaCheckResponse)
def analyze_visa_documents(
    check_id: str,
    bypass_check: bool = Query(False),  # Developer bypass check helper
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Performs AI visa validation checks across all uploaded documents under the check ID.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    if not bypass_check:
        verify_visa_checker_purchase(db)

    check = db.query(VisaDocumentCheck).filter(
        VisaDocumentCheck.id == check_id,
        VisaDocumentCheck.user_id == user_id
    ).first()
    if not check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visa Document Check record not found."
        )

    uploaded_files = check.uploaded_documents
    if not uploaded_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No documents have been uploaded for validation yet."
        )

    try:
        # 1. Map files to lists for service utility
        files_payload = []
        for doc in uploaded_files:
            files_payload.append({
                "id": doc.id,
                "filename": doc.filename,
                "document_type": doc.document_type
            })

        # 2. Query Rules Engine & AI service
        report = evaluate_visa_documents_ai(
            country=check.country,
            visa_type=check.visa_type,
            uploaded_files=files_payload
        )

        # 3. Save overall metrics to check ID
        check.readiness_score = report.get("readiness_score", 0)
        check.status = report.get("status", "Needs Improvement")
        check.ai_response = report
        
        # 4. Clear any old analyses before logging new ones to support re-runs
        db.query(DocumentAnalysis).filter(DocumentAnalysis.check_id == check_id).delete()
        
        # 5. Insert individual document reports
        doc_analyses = report.get("document_analyses", [])
        for doc_rep in doc_analyses:
            # Match the document by name to link to uploaded file ID
            doc_file = next((f for f in uploaded_files if f.filename == doc_rep["document_name"]), None)
            doc_file_id = doc_file.id if doc_file else None

            db_analysis = DocumentAnalysis(
                check_id=check_id,
                uploaded_document_id=doc_file_id,
                document_name=doc_rep["document_name"],
                status=doc_rep["status"],
                issues=doc_rep.get("issues", []),
                suggestions=doc_rep.get("suggestions", []),
                confidence_score=doc_rep.get("confidence_score", 1.0),
                critical=doc_rep.get("critical", False)
            )
            db.add(db_analysis)

        db.commit()
        db.refresh(check)
        return check
    except Exception as e:
        logger.error(f"Visa check analysis failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run document check analysis."
        )


@router.post("/api/visa-check/start", response_model=VisaCheckResponse, status_code=status.HTTP_201_CREATED)
def start_visa_check(
    payload: VisaCheckStart,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Initiates a new visa checklist record in the database.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")

    db_check = VisaDocumentCheck(
        user_id=user_id,
        country=payload.country,
        visa_type=payload.visa_type,
        readiness_score=0,
        status="Needs Improvement"
    )
    db.add(db_check)
    db.commit()
    db.refresh(db_check)
    return db_check


@router.get("/api/visa-check/history", response_model=List[VisaCheckResponse])
def get_visa_check_history(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves all previously recorded visa document checks.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    return db.query(VisaDocumentCheck).filter(VisaDocumentCheck.user_id == user_id).order_by(desc(VisaDocumentCheck.updated_at)).all()


@router.get("/api/visa-check/{check_id}", response_model=VisaCheckResponse)
def get_visa_check_by_id(
    check_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves a specific visa document check report and file list logs.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    check = db.query(VisaDocumentCheck).filter(
        VisaDocumentCheck.id == check_id,
        VisaDocumentCheck.user_id == user_id
    ).first()
    if not check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visa check record not found."
        )
    return check


@router.delete("/api/visa-check/{check_id}", status_code=status.HTTP_200_OK)
def delete_visa_check(
    check_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Deletes the document checking record and files.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    check = db.query(VisaDocumentCheck).filter(
        VisaDocumentCheck.id == check_id,
        VisaDocumentCheck.user_id == user_id
    ).first()
    if not check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visa check record not found."
        )
    
    # Optional: Delete actual files from disk
    for doc in check.uploaded_documents:
        full_path = os.path.join("backend", doc.file_path.lstrip("/"))
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
            except Exception:
                pass

    db.delete(check)
    db.commit()
    return {"message": "Visa check record deleted successfully."}
