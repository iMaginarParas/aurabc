import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ..database import get_db
from ..auth import get_current_user
from ..models import (
    StudentJourney,
    JourneyStage,
    JourneyTask,
    JourneyActivity,
    VisaTracker,
    CalendarEvent,
    StudentReminder,
    Application,
    ApplicationDocument,
    ApplicationTimeline,
    Appointment,
    EligibilityRequest
)
from ..services.journey_automation import JourneyAutomationService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["journey"])

# Pydantic Input Schemas
class JourneyUpdateInput(BaseModel):
    current_stage: str
    health_score: Optional[int] = None

class TaskUpdateInput(BaseModel):
    completed: bool
    notes: Optional[str] = None

class ApplicationInput(BaseModel):
    university: str
    country: str
    course: str
    degree: str
    intake: str = "Fall 2026"
    tuition_fee: Optional[str] = None
    application_fee: Optional[str] = None
    deadline: Optional[str] = None
    current_status: str = "Interested"
    priority: str = "Medium"
    notes: Optional[str] = None

class ApplicationUpdateInput(BaseModel):
    current_status: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = None
    tuition_fee: Optional[str] = None
    application_fee: Optional[str] = None
    deadline: Optional[str] = None

class VisaUpdateInput(BaseModel):
    visa_type: Optional[str] = None
    country: Optional[str] = None
    current_stage: Optional[str] = None
    biometrics_date: Optional[str] = None
    interview_date: Optional[str] = None
    submission_date: Optional[str] = None
    expected_approval_date: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


@router.post("/api/journey/create", status_code=status.HTTP_201_CREATED)
def create_student_journey(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Explicitly triggers initialization of the student journey framework.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    email = current_user.get("email") or "student@auraroutes.com"

    journey = JourneyAutomationService.initialize_journey(db, user_id, email)
    return {"message": "Journey initialized successfully.", "journey_id": journey.id}


@router.get("/api/journey")
def get_student_journey(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Fetches the detailed student journey tracker: stage pipelines, tasks, activity logs,
    and visual progress indicators. Auto-creates journey if none exists.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    email = current_user.get("email") or "student@auraroutes.com"

    # Failsafe: Initialize journey if not existing
    journey = db.query(StudentJourney).filter(StudentJourney.user_id == user_id).first()
    if not journey:
        journey = JourneyAutomationService.initialize_journey(db, user_id, email)

    stages = db.query(JourneyStage).filter(JourneyStage.journey_id == journey.id).all()
    tasks = db.query(JourneyTask).filter(JourneyTask.journey_id == journey.id).all()
    activities = db.query(JourneyActivity).filter(JourneyActivity.journey_id == journey.id).order_by(desc(JourneyActivity.created_at)).all()
    visa = db.query(VisaTracker).filter(VisaTracker.journey_id == journey.id).first()

    # Format stages objects
    stage_data = []
    for s in stages:
        stage_tasks = [t for t in tasks if t.stage_name == s.stage_name]
        stage_data.append({
            "id": s.id,
            "stage_name": s.stage_name,
            "status": s.status,
            "completion_percentage": s.completion_percentage,
            "notes": s.notes,
            "tasks_count": len(stage_tasks),
            "completed_tasks_count": len([t for t in stage_tasks if t.completed])
        })

    return {
        "journey": {
            "id": journey.id,
            "user_id": journey.user_id,
            "overall_progress": journey.overall_progress,
            "current_stage": journey.current_stage,
            "health_score": journey.health_score,
            "start_date": journey.start_date.isoformat(),
            "expected_completion_date": journey.expected_completion_date.isoformat() if journey.expected_completion_date else None
        },
        "stages": stage_data,
        "recent_activities": [
            {
                "id": a.id,
                "activity_type": a.activity_type,
                "description": a.description,
                "created_at": a.created_at.isoformat()
            } for a in activities[:8]
        ],
        "visa_tracker": {
            "id": visa.id,
            "visa_type": visa.visa_type,
            "country": visa.country,
            "current_stage": visa.current_stage,
            "biometrics_date": visa.biometrics_date,
            "interview_date": visa.interview_date,
            "submission_date": visa.submission_date,
            "readiness_score": visa.readiness_score,
            "expected_approval_date": visa.expected_approval_date,
            "status": visa.status,
            "notes": visa.notes
        } if visa else None
    }


@router.put("/api/journey")
def update_student_journey(
    payload: JourneyUpdateInput,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Shifts active timeline stage for the user.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    journey = db.query(StudentJourney).filter(StudentJourney.user_id == user_id).first()
    if not journey:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student journey workspace not found.")

    journey.current_stage = payload.current_stage
    if payload.health_score is not None:
        journey.health_score = payload.health_score
    
    # Save Activity
    act = JourneyActivity(
        journey_id=journey.id,
        activity_type="Stage Shifted",
        description=f"Active milestone advanced to '{payload.current_stage}'."
    )
    db.add(act)
    db.commit()

    return {"message": "Journey updated successfully.", "current_stage": journey.current_stage}


@router.get("/api/tasks")
def get_journey_tasks(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns lists of all current checklist items mapped by milestones.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    journey = db.query(StudentJourney).filter(StudentJourney.user_id == user_id).first()
    if not journey:
        return []

    tasks = db.query(JourneyTask).filter(JourneyTask.journey_id == journey.id).order_by(desc(JourneyTask.created_at)).all()
    return [
        {
            "id": t.id,
            "stage_name": t.stage_name,
            "title": t.title,
            "priority": t.priority,
            "due_date": t.due_date,
            "completed": t.completed,
            "reminder": t.reminder,
            "notes": t.notes,
            "is_premium": t.is_premium
        } for t in tasks
    ]


@router.put("/api/tasks/{id}")
def update_journey_task(
    id: str,
    payload: TaskUpdateInput,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Toggles completion status or updates notes on a specific task.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    task = db.query(JourneyTask).join(StudentJourney).filter(
        JourneyTask.id == id,
        StudentJourney.user_id == user_id
    ).first()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found or access denied.")

    task.completed = payload.completed
    if payload.notes is not None:
        task.notes = payload.notes

    # Update completion percentage on the parent stage
    stage = db.query(JourneyStage).filter(
        JourneyStage.journey_id == task.journey_id,
        JourneyStage.stage_name == task.stage_name
    ).first()
    if stage:
        all_stage_tasks = db.query(JourneyTask).filter(
            JourneyTask.journey_id == task.journey_id,
            JourneyTask.stage_name == task.stage_name
        ).all()
        comp_count = sum(1 for t in all_stage_tasks if t.completed)
        stage.completion_percentage = round((comp_count / len(all_stage_tasks)) * 100.0, 1) if all_stage_tasks else 0.0
        if stage.completion_percentage >= 100.0:
            stage.status = "Completed"
        elif stage.completion_percentage > 0.0:
            stage.status = "In Progress"
        else:
            stage.status = "Not Started"

    db.commit()

    # Recalculate journey-level completion percent
    JourneyAutomationService.recalculate_overall_progress(db, task.journey_id)

    return {"message": "Task updated successfully.", "completed": task.completed}


@router.post("/api/application", status_code=status.HTTP_201_CREATED)
def create_university_application_alias(
    payload: ApplicationInput,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Creates a new university application pipeline record under the student profile.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")

    # Double check if application already matches
    dup = db.query(Application).filter(
        Application.user_id == user_id,
        Application.university == payload.university,
        Application.course == payload.course
    ).first()
    if dup:
        return dup

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
        current_status=payload.current_status,
        priority=payload.priority,
        notes=payload.notes
    )
    db.add(app_rec)
    db.commit()
    db.refresh(app_rec)

    # Insert default checklist documents
    docs = ["Passport", "Transcripts", "Resume", "SOP", "LOR", "Financial Documents"]
    for d in docs:
        db_doc = ApplicationDocument(
            application_id=app_rec.id,
            document_name=d,
            status="Pending"
        )
        db.add(db_doc)

    # Add Timeline log
    db_time = ApplicationTimeline(
        application_id=app_rec.id,
        event_title="Application Synced",
        event_description="Workspace initialized under journey dashboard."
    )
    db.add(db_time)

    # Add Calendar event
    if payload.deadline:
        cal = CalendarEvent(
            user_id=user_id,
            event_title=f"Application Deadline: {payload.university}",
            event_type="Application Deadline",
            event_date=payload.deadline,
            reference_id=app_rec.id
        )
        db.add(cal)

    db.commit()
    db.refresh(app_rec)
    return app_rec


@router.get("/api/application")
def get_applications_alias(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Gathers list of all universities in active tracking pipeline.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    apps = db.query(Application).filter(Application.user_id == user_id).order_by(desc(Application.updated_at)).all()
    
    result = []
    for a in apps:
        docs = db.query(ApplicationDocument).filter(ApplicationDocument.application_id == a.id).all()
        result.append({
            "id": a.id,
            "university": a.university,
            "country": a.country,
            "course": a.course,
            "degree": a.degree,
            "intake": a.intake,
            "tuition_fee": a.tuition_fee,
            "application_fee": a.application_fee,
            "deadline": a.deadline,
            "current_status": a.current_status,
            "priority": a.priority,
            "notes": a.notes,
            "documents": [
                {
                    "id": d.id,
                    "document_name": d.document_name,
                    "status": d.status,
                    "file_path": d.file_path
                } for d in docs
            ]
        })
    return result


@router.put("/api/application/{id}")
def update_application_alias(
    id: str,
    payload: ApplicationUpdateInput,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Updates status transition (Kanban drags) or metadata properties.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    app_rec = db.query(Application).filter(Application.id == id, Application.user_id == user_id).first()
    if not app_rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application workspace not found.")

    if payload.current_status is not None:
        app_rec.current_status = payload.current_status
    if payload.priority is not None:
        app_rec.priority = payload.priority
    if payload.notes is not None:
        app_rec.notes = payload.notes
    if payload.tuition_fee is not None:
        app_rec.tuition_fee = payload.tuition_fee
    if payload.application_fee is not None:
        app_rec.application_fee = payload.application_fee
    if payload.deadline is not None:
        app_rec.deadline = payload.deadline

    db.commit()
    db.refresh(app_rec)
    return app_rec


@router.delete("/api/application/{id}")
def delete_application_alias(
    id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Removes application record.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    app_rec = db.query(Application).filter(Application.id == id, Application.user_id == user_id).first()
    if not app_rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application record not found.")

    db.delete(app_rec)
    db.commit()
    return {"message": "Application deleted successfully."}


@router.get("/api/visa")
def get_visa_tracker(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieves student visa application checklist status and schedule details.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    journey = db.query(StudentJourney).filter(StudentJourney.user_id == user_id).first()
    if not journey:
        return None

    visa = db.query(VisaTracker).filter(VisaTracker.journey_id == journey.id).first()
    return visa


@router.put("/api/visa")
def update_visa_tracker_info(
    payload: VisaUpdateInput,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Configures visa biometrics enrollment slots, audit scores, and expected timelines.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")
    journey = db.query(StudentJourney).filter(StudentJourney.user_id == user_id).first()
    if not journey:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active student journey not found.")

    visa = db.query(VisaTracker).filter(VisaTracker.journey_id == journey.id).first()
    if not visa:
        visa = VisaTracker(journey_id=journey.id)
        db.add(visa)

    if payload.visa_type is not None:
        visa.visa_type = payload.visa_type
    if payload.country is not None:
        visa.country = payload.country
    if payload.current_stage is not None:
        visa.current_stage = payload.current_stage
    if payload.biometrics_date is not None:
        visa.biometrics_date = payload.biometrics_date
        # Sync calendar
        cal_check = db.query(CalendarEvent).filter(CalendarEvent.user_id == user_id, CalendarEvent.event_type == "Biometrics").first()
        if cal_check:
            cal_check.event_date = payload.biometrics_date
        else:
            db.add(CalendarEvent(user_id=user_id, event_title="Biometrics slot slot", event_type="Biometrics", event_date=payload.biometrics_date))
    if payload.interview_date is not None:
        visa.interview_date = payload.interview_date
        cal_int = db.query(CalendarEvent).filter(CalendarEvent.user_id == user_id, CalendarEvent.event_type == "Interview").first()
        if cal_int:
            cal_int.event_date = payload.interview_date
        else:
            db.add(CalendarEvent(user_id=user_id, event_title="Embassy Visa Interview", event_type="Interview", event_date=payload.interview_date))
    if payload.submission_date is not None:
        visa.submission_date = payload.submission_date
    if payload.expected_approval_date is not None:
        visa.expected_approval_date = payload.expected_approval_date
    if payload.status is not None:
        visa.status = payload.status
    if payload.notes is not None:
        visa.notes = payload.notes

    db.commit()
    db.refresh(visa)
    return visa


@router.get("/api/calendar")
def get_calendar_agenda(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Compiles all deadlines, consultation bookings, travel timelines, and test dates.
    """
    if current_user.get("sub") == "guest_user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    
    user_id = current_user.get("sub")

    # Get custom calendar events
    events = db.query(CalendarEvent).filter(CalendarEvent.user_id == user_id).all()
    
    # Get consultant appointments
    appts = db.query(Appointment).filter(Appointment.user_id == user_id, Appointment.status == "upcoming").all()

    # Get applications deadlines
    apps = db.query(Application).filter(Application.user_id == user_id).all()

    agenda = []
    
    # Format events
    for e in events:
        agenda.append({
            "id": e.id,
            "title": e.event_title,
            "type": e.event_type,
            "date": e.event_date
        })

    # Format appts
    for a in appts:
        agenda.append({
            "id": a.id,
            "title": f"Advisor Call: {a.consultant_name}",
            "type": "Consultation",
            "date": a.date_time.strftime("%Y-%m-%d")
        })

    # Format applications deadlines
    for ap in apps:
        if ap.deadline:
            agenda.append({
                "id": ap.id,
                "title": f"Deadline: {ap.university}",
                "type": "Application Deadline",
                "date": ap.deadline
            })

    return agenda
