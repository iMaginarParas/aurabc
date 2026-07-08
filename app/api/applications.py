import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional

from ..database import get_db
from ..auth import get_current_user
from ..models import (
    Application,
    ApplicationTask,
    ApplicationDocument,
    ApplicationNote,
    ApplicationTimeline,
    ApplicationCalendarItem,
    DashboardActivity
)
from ..schemas import (
    ApplicationResponse,
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationTaskResponse,
    TaskCreate,
    ApplicationDocumentResponse,
    DocumentCreate,
    ApplicationNoteResponse,
    NoteCreate,
    ApplicationCalendarResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["applications"])


def create_application(
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Creates a new university application pipeline record and sets up default task items.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    try:
        app_rec = Application(
            user_id=user_id,
            university=payload.university,
            country=payload.country,
            course=payload.course,
            degree=payload.degree,
            intake=payload.intake,
            tuition_fee=payload.tuition_fee,
            application_fee=payload.application_fee,
            deadline=payload.deadline,
            current_status=payload.current_status or "Interested",
            priority=payload.priority or "Medium",
            notes=payload.notes
        )
        db.add(app_rec)
        db.commit()
        db.refresh(app_rec)

        # 1. Create Default Document Slots
        docs = ["Passport", "Transcripts", "Resume", "SOP", "LOR", "Financial Documents"]
        for d in docs:
            db_doc = ApplicationDocument(
                application_id=app_rec.id,
                document_name=d,
                status="Pending"
            )
            db.add(db_doc)

        # 2. Create Default Tasks
        tasks = [
            {"title": "Generate SOP", "priority": "High"},
            {"title": "Upload Passport scan copy", "priority": "High"},
            {"title": "Verify IELTS language test scores", "priority": "Medium"}
        ]
        for t in tasks:
            db_task = ApplicationTask(
                application_id=app_rec.id,
                title=t["title"],
                status="pending",
                priority=t["priority"]
            )
            db.add(db_task)

        # 3. Create Timeline Logs
        db_time = ApplicationTimeline(
            application_id=app_rec.id,
            event_title="Application Created",
            event_description=f"Initiated application pipeline for {payload.degree} in {payload.course}."
        )
        db.add(db_time)

        # 4. Create Calendar Item
        if payload.deadline:
            db_cal = ApplicationCalendarItem(
                application_id=app_rec.id,
                event_title=f"{payload.university} Deadline",
                event_type="Deadline",
                event_date=payload.deadline
            )
            db.add(db_cal)

        # 4. Log to Dashboard activity tracker
        activity = DashboardActivity(
            user_id=user_id,
            activity_type="Application",
            description=f"Started tracking application for {payload.university}."
        )
        db.add(activity)

        db.commit()
        db.refresh(app_rec)
        return app_rec
    except Exception as e:
        logger.error(f"Failed to create application: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate application workspace."
        )


@router.get("/api/applications", response_model=List[ApplicationResponse])
def get_applications(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Lists all university applications tracked by the student.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    return db.query(Application).filter(
        Application.user_id == user_id
    ).order_by(desc(Application.updated_at)).all()


@router.get("/api/applications/{app_id}", response_model=ApplicationResponse)
def get_application_by_id(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves detailed logs for a single application.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    app_rec = db.query(Application).filter(
        Application.id == app_id,
        Application.user_id == user_id
    ).first()
    if not app_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application record not found or access denied."
        )
    return app_rec


@router.put("/api/applications/{app_id}", response_model=ApplicationResponse)
def update_application(
    app_id: str,
    payload: ApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Updates application properties (including drag pipeline status updates).
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    app_rec = db.query(Application).filter(
        Application.id == app_id,
        Application.user_id == user_id
    ).first()
    if not app_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application record not found or access denied."
        )

    # Track status change for timeline logging
    status_changed = False
    old_status = app_rec.current_status

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(app_rec, key, value)
        if key == "current_status" and value != old_status:
            status_changed = True

    if status_changed:
        # Add Timeline Log
        db_time = ApplicationTimeline(
            application_id=app_rec.id,
            event_title="Pipeline Moved",
            event_description=f"Status transitioned from '{old_status}' to '{app_rec.current_status}'."
        )
        db.add(db_time)

    db.commit()
    db.refresh(app_rec)
    return app_rec


@router.delete("/api/applications/{app_id}", status_code=status.HTTP_200_OK)
def delete_application(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Removes the application workspace from the database.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    app_rec = db.query(Application).filter(
        Application.id == app_id,
        Application.user_id == user_id
    ).first()
    if not app_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application record not found."
        )
    db.delete(app_rec)
    db.commit()
    return {"message": "Application removed successfully."}


@router.post("/api/application/tasks", response_model=ApplicationTaskResponse, status_code=status.HTTP_201_CREATED)
def create_application_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Adds a custom checklist task under an application.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    app_rec = db.query(Application).filter(
        Application.id == payload.application_id,
        Application.user_id == user_id
    ).first()
    if not app_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application reference not found or access denied."
        )

    db_task = ApplicationTask(
        application_id=payload.application_id,
        title=payload.title,
        status="pending",
        due_date=payload.due_date,
        priority=payload.priority or "Medium",
        notes=payload.notes
    )
    db.add(db_task)
    
    # Timeline check
    db_time = ApplicationTimeline(
        application_id=payload.application_id,
        event_title="Task Added",
        event_description=f"Logged new milestone: {payload.title}"
    )
    db.add(db_time)

    db.commit()
    db.refresh(db_task)
    return db_task


@router.put("/api/application/tasks/{task_id}/toggle", response_model=ApplicationTaskResponse)
def toggle_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Toggles a task between completed and pending.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    db_task = db.query(ApplicationTask).join(Application).filter(
        ApplicationTask.id == task_id,
        Application.user_id == user_id
    ).first()
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task record not found or access denied."
        )

    db_task.status = "completed" if db_task.status == "pending" else "pending"
    
    # Log timeline event
    db_time = ApplicationTimeline(
        application_id=db_task.application_id,
        event_title="Task Completed" if db_task.status == "completed" else "Task Re-opened",
        event_description=f"Task '{db_task.title}' was marked as {db_task.status}."
    )
    db.add(db_time)

    db.commit()
    db.refresh(db_task)
    return db_task


@router.post("/api/application/documents", response_model=ApplicationDocumentResponse, status_code=status.HTTP_201_CREATED)
def update_application_document_status(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Creates or updates the upload verification status of a document checklist slot.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    
    app_rec = db.query(Application).filter(
        Application.id == payload.application_id,
        Application.user_id == user_id
    ).first()
    if not app_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application reference not found or access denied."
        )

    db_doc = db.query(ApplicationDocument).filter(
        ApplicationDocument.application_id == payload.application_id,
        ApplicationDocument.document_name == payload.document_name
    ).first()

    if not db_doc:
        db_doc = ApplicationDocument(
            application_id=payload.application_id,
            document_name=payload.document_name,
            status=payload.status or "Pending",
            file_path=payload.file_path
        )
        db.add(db_doc)
    else:
        db_doc.status = payload.status or "Pending"
        if payload.file_path:
            db_doc.file_path = payload.file_path

    # Log timeline event
    db_time = ApplicationTimeline(
        application_id=payload.application_id,
        event_title="Document Updated",
        event_description=f"Checklist status for '{payload.document_name}' set to {db_doc.status}."
    )
    db.add(db_time)

    db.commit()
    db.refresh(db_doc)
    return db_doc


@router.post("/api/application/notes", response_model=ApplicationNoteResponse, status_code=status.HTTP_201_CREATED)
def create_application_note(
    payload: NoteCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Appends a text note under an application profile.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    
    app_rec = db.query(Application).filter(
        Application.id == payload.application_id,
        Application.user_id == user_id
    ).first()
    if not app_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application reference not found or access denied."
        )

    db_note = ApplicationNote(
        application_id=payload.application_id,
        title=payload.title,
        content=payload.content
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note


@router.get("/api/application/calendar", response_model=List[ApplicationCalendarResponse])
def get_application_calendar_events(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Gathers all scheduled deadlines and reminders.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id = current_user.get("sub")
    return db.query(ApplicationCalendarItem).join(Application).filter(
        Application.user_id == user_id
    ).order_by(ApplicationCalendarItem.event_date).all()
