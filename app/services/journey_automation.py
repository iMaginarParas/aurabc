import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..models import (
    StudentJourney,
    JourneyStage,
    JourneyTask,
    JourneyActivity,
    VisaTracker,
    CalendarEvent,
    StudentReminder,
    EligibilityRequest,
    Application,
    ApplicationDocument,
    ApplicationTask,
    ApplicationTimeline,
    ApplicationCalendarItem,
    DashboardActivity
)

logger = logging.getLogger(__name__)

STAGES_LIST = [
    "Eligibility",
    "Universities",
    "Scholarships",
    "SOP",
    "Applications",
    "Offer Letter",
    "Financial Preparation",
    "Visa Documents",
    "Visa Submission",
    "Biometrics",
    "Interview",
    "Visa Approved",
    "Accommodation",
    "Travel Preparation",
    "Completed"
]

DEFAULT_TASKS = {
    "Eligibility": [
        {"title": "Complete profile details (GPA, preferences)", "priority": "High", "is_premium": False},
        {"title": "Run eligibility check with Aura AI", "priority": "High", "is_premium": False}
    ],
    "Universities": [
        {"title": "Research suggested universities on dashboard", "priority": "High", "is_premium": False},
        {"title": "Shortlist at least 3 universities", "priority": "High", "is_premium": False}
    ],
    "Scholarships": [
        {"title": "Identify target scholarships matching your course", "priority": "Medium", "is_premium": False},
        {"title": "Prepare scholarship documents & deadlines", "priority": "Medium", "is_premium": False}
    ],
    "SOP": [
        {"title": "Generate initial SOP draft with Aura AI", "priority": "High", "is_premium": False},
        {"title": "Review and edit SOP content", "priority": "High", "is_premium": False}
    ],
    "Applications": [
        {"title": "Prepare transcripts and academic certificates", "priority": "High", "is_premium": False},
        {"title": "Submit application to shortlisted universities", "priority": "High", "is_premium": False}
    ],
    "Offer Letter": [
        {"title": "Track university application status", "priority": "High", "is_premium": False},
        {"title": "Accept offer and pay deposit fee", "priority": "High", "is_premium": False}
    ],
    "Financial Preparation": [
        {"title": "Prepare proof of tuition funds", "priority": "High", "is_premium": False},
        {"title": "Apply for education loan / confirm sponsors", "priority": "Medium", "is_premium": False}
    ],
    "Visa Documents": [
        {"title": "Upload passport scan for audit", "priority": "High", "is_premium": False},
        {"title": "Prepare financial documentation for visa", "priority": "High", "is_premium": False}
    ],
    "Visa Submission": [
        {"title": "Pay visa fee and submit form", "priority": "High", "is_premium": False}
    ],
    "Biometrics": [
        {"title": "Book biometrics appointment", "priority": "High", "is_premium": False},
        {"title": "Attend biometrics enrollment", "priority": "High", "is_premium": False}
    ],
    "Interview": [
        {"title": "Run visa interview prep with Aura AI", "priority": "High", "is_premium": True},
        {"title": "Attend embassy visa interview", "priority": "High", "is_premium": False}
    ],
    "Visa Approved": [
        {"title": "Upload scan of visa stamp/letter", "priority": "High", "is_premium": False}
    ],
    "Accommodation": [
        {"title": "Book student accommodation near campus", "priority": "Medium", "is_premium": False}
    ],
    "Travel Preparation": [
        {"title": "Book flight ticket", "priority": "Medium", "is_premium": False},
        {"title": "Upload travel insurance scan", "priority": "High", "is_premium": False}
    ],
    "Completed": [
        {"title": "Complete pre-departure orientation checklist", "priority": "Low", "is_premium": False}
    ]
}

class JourneyAutomationService:
    @staticmethod
    def initialize_journey(db: Session, user_id: str, email: str) -> StudentJourney:
        """
        Initializes a fresh student journey record with stages and default tasks in PostgreSQL database.
        """
        logger.info(f"Initializing student journey for user {user_id} ({email})")

        # Failsafe check
        existing = db.query(StudentJourney).filter(StudentJourney.user_id == user_id).first()
        if existing:
            return existing

        # Create journey
        journey = StudentJourney(
            user_id=user_id,
            current_stage="Eligibility",
            overall_progress=0.0,
            health_score=100,
            expected_completion_date=datetime.utcnow() + timedelta(days=365)
        )
        db.add(journey)
        db.commit()
        db.refresh(journey)

        # Create stages list
        for idx, stage_name in enumerate(STAGES_LIST):
            status = "In Progress" if stage_name == "Eligibility" else "Not Started"
            completion = 10.0 if stage_name == "Eligibility" else 0.0

            db_stage = JourneyStage(
                journey_id=journey.id,
                stage_name=stage_name,
                status=status,
                completion_percentage=completion
            )
            db.add(db_stage)

            # Insert default tasks for each stage
            tasks = DEFAULT_TASKS.get(stage_name, [])
            for t in tasks:
                db_task = JourneyTask(
                    journey_id=journey.id,
                    stage_name=stage_name,
                    title=t["title"],
                    priority=t["priority"],
                    is_premium=t["is_premium"],
                    due_date=(datetime.utcnow() + timedelta(days=30 * (idx + 1))).strftime("%Y-%m-%d"),
                    completed=False
                )
                db.add(db_task)

        # Initialize Visa Tracker
        visa = VisaTracker(
            journey_id=journey.id,
            visa_type="Student Visa",
            current_stage="Submitted",
            readiness_score=0,
            status="Pending"
        )
        db.add(visa)

        # Add initial activity log
        activity = JourneyActivity(
            journey_id=journey.id,
            activity_type="Journey Initialized",
            description="Welcome to Aura Routes! Your personalized Study Abroad Journey has been initialized."
        )
        db.add(activity)
        db.commit()
        db.refresh(journey)

        # Check if they have already completed eligibility checks and auto-advance
        profile = db.query(EligibilityRequest).filter(EligibilityRequest.email == email).first()
        if profile and profile.status == "completed":
            JourneyAutomationService.on_eligibility_completed(db, user_id)

        return journey

    @staticmethod
    def recalculate_overall_progress(db: Session, journey_id: str):
        """
        Updates the overall progress score based on the average completion percent of all 15 stages.
        """
        journey = db.query(StudentJourney).filter(StudentJourney.id == journey_id).first()
        if not journey:
            return

        stages = db.query(JourneyStage).filter(JourneyStage.journey_id == journey_id).all()
        if not stages:
            return

        # Calculate average of all stages
        total_percent = sum(s.completion_percentage for s in stages)
        journey.overall_progress = round(total_percent / len(STAGES_LIST), 1)

        # Dynamically evaluate health score based on overdue uncompleted tasks
        tasks = db.query(JourneyTask).filter(JourneyTask.journey_id == journey_id).all()
        overdue_tasks = 0
        current_date_str = datetime.utcnow().strftime("%Y-%m-%d")
        for t in tasks:
            if not t.completed and t.due_date and t.due_date < current_date_str:
                overdue_tasks += 1

        journey.health_score = max(50, 100 - (overdue_tasks * 5))
        db.commit()

    @staticmethod
    def on_eligibility_completed(db: Session, user_id: str):
        """
        Advanced auto-trigger: Updates Eligibility stage to 100% and advances to Universities discovery.
        """
        journey = db.query(StudentJourney).filter(StudentJourney.user_id == user_id).first()
        if not journey:
            return

        # Complete all Eligibility stage tasks
        elig_tasks = db.query(JourneyTask).filter(
            JourneyTask.journey_id == journey.id,
            JourneyTask.stage_name == "Eligibility"
        ).all()
        for t in elig_tasks:
            t.completed = True

        # Set Stage completion to 100%
        elig_stage = db.query(JourneyStage).filter(
            JourneyStage.journey_id == journey.id,
            JourneyStage.stage_name == "Eligibility"
        ).first()
        if elig_stage:
            elig_stage.status = "Completed"
            elig_stage.completion_percentage = 100.0

        # Advance next stage Universities to In Progress
        uni_stage = db.query(JourneyStage).filter(
            JourneyStage.journey_id == journey.id,
            JourneyStage.stage_name == "Universities"
        ).first()
        if uni_stage and uni_stage.status == "Not Started":
            uni_stage.status = "In Progress"
            uni_stage.completion_percentage = 20.0
            journey.current_stage = "Universities"

        # Log Activity
        activity = JourneyActivity(
            journey_id=journey.id,
            activity_type="Eligibility Completed",
            description="Aura AI eligibility profile assessment completed successfully. Starting University Discovery!"
        )
        db.add(activity)
        db.commit()

        # Recalculate
        JourneyAutomationService.recalculate_overall_progress(db, journey.id)

    @staticmethod
    def on_university_saved(db: Session, user_id: str, uni_name: str, country: str, course: str, tuition: str):
        """
        Advanced auto-trigger: When saved, creates a default pipeline application and schedules deadlines.
        """
        journey = db.query(StudentJourney).filter(StudentJourney.user_id == user_id).first()
        if not journey:
            return

        # 1. Update Stage Universities status to In Progress
        uni_stage = db.query(JourneyStage).filter(
            JourneyStage.journey_id == journey.id,
            JourneyStage.stage_name == "Universities"
        ).first()
        if uni_stage:
            uni_stage.status = "In Progress"
            uni_stage.completion_percentage = min(100.0, uni_stage.completion_percentage + 40.0)
            if uni_stage.completion_percentage >= 100.0:
                uni_stage.status = "Completed"
                # Unlock Scholarships
                schol_stage = db.query(JourneyStage).filter(
                    JourneyStage.journey_id == journey.id,
                    JourneyStage.stage_name == "Scholarships"
                ).first()
                if schol_stage and schol_stage.status == "Not Started":
                    schol_stage.status = "In Progress"
                    journey.current_stage = "Scholarships"

        # Mark "Shortlist at least 3 universities" task as completed if multiple saved
        uni_tasks = db.query(JourneyTask).filter(
            JourneyTask.journey_id == journey.id,
            JourneyTask.stage_name == "Universities"
        ).all()
        for t in uni_tasks:
            t.completed = True

        # 2. Automatically Create a Pipeline Application record
        # Avoid duplication
        dup = db.query(Application).filter(
            Application.user_id == user_id,
            Application.university == uni_name,
            Application.course == course
        ).first()
        if not dup:
            app_rec = Application(
                user_id=user_id,
                university=uni_name,
                country=country,
                course=course,
                degree="Masters",
                intake="Fall 2026",
                tuition_fee=tuition,
                current_status="Interested",
                priority="Medium",
                notes="Auto-created when university was favorited from Search Matcher."
            )
            db.add(app_rec)
            db.commit()
            db.refresh(app_rec)

            # Insert application sub-checklist items
            docs = ["Passport", "Transcripts", "Resume", "SOP", "LOR", "Financial Documents"]
            for d in docs:
                db_doc = ApplicationDocument(
                    application_id=app_rec.id,
                    document_name=d,
                    status="Pending"
                )
                db.add(db_doc)

            # Schedule application deadline in CalendarEvents
            dl_date = (datetime.utcnow() + timedelta(days=120)).strftime("%Y-%m-%d")
            db_cal = CalendarEvent(
                user_id=user_id,
                event_title=f"Application Deadline: {uni_name}",
                event_type="Application Deadline",
                event_date=dl_date,
                reference_id=app_rec.id
            )
            db.add(db_cal)

            # Create Timeline log
            db_time = ApplicationTimeline(
                application_id=app_rec.id,
                event_title="Application Synced",
                event_description=f"Journey engine initialized university workspace for {uni_name}."
            )
            db.add(db_time)

            # Create Student Reminder
            reminder = StudentReminder(
                user_id=user_id,
                title="University Shortlist Deadline",
                message=f"Application deadline for {uni_name} is scheduled on {dl_date}. Prepare document checks!",
                reminder_type="Deadline",
                trigger_date=(datetime.utcnow() + timedelta(days=90)).strftime("%Y-%m-%d")
            )
            db.add(reminder)

        # Log Activity
        activity = JourneyActivity(
            journey_id=journey.id,
            activity_type="University Saved",
            description=f"Saved university {uni_name} to shortlists. Application pipeline initialized."
        )
        db.add(activity)
        db.commit()

        # Recalculate
        JourneyAutomationService.recalculate_overall_progress(db, journey.id)

    @staticmethod
    def on_sop_generated(db: Session, user_id: str, doc_title: str):
        """
        Advanced auto-trigger: Automatically completes the SOP stage when Statement of Purpose is generated.
        """
        journey = db.query(StudentJourney).filter(StudentJourney.user_id == user_id).first()
        if not journey:
            return

        # Complete SOP stage tasks
        sop_tasks = db.query(JourneyTask).filter(
            JourneyTask.journey_id == journey.id,
            JourneyTask.stage_name == "SOP"
        ).all()
        for t in sop_tasks:
            t.completed = True

        # Complete SOP stage
        sop_stage = db.query(JourneyStage).filter(
            JourneyStage.journey_id == journey.id,
            JourneyStage.stage_name == "SOP"
        ).first()
        if sop_stage:
            sop_stage.status = "Completed"
            sop_stage.completion_percentage = 100.0

            # Advance next stage Applications
            app_stage = db.query(JourneyStage).filter(
                JourneyStage.journey_id == journey.id,
                JourneyStage.stage_name == "Applications"
            ).first()
            if app_stage and app_stage.status == "Not Started":
                app_stage.status = "In Progress"
                app_stage.completion_percentage = 10.0
                journey.current_stage = "Applications"

        # Log Activity
        activity = JourneyActivity(
            journey_id=journey.id,
            activity_type="SOP Completed",
            description=f"Aura AI auto-generated Statement of Purpose draft: {doc_title}."
        )
        db.add(activity)
        db.commit()

        # Recalculate
        JourneyAutomationService.recalculate_overall_progress(db, journey.id)

    @staticmethod
    def on_scholarship_saved(db: Session, user_id: str, schol_name: str):
        """
        Advanced auto-trigger: Completes Scholarship tasks and sets progress to In Progress / Completed.
        """
        journey = db.query(StudentJourney).filter(StudentJourney.user_id == user_id).first()
        if not journey:
            return

        # Complete Scholarship stage tasks
        schol_tasks = db.query(JourneyTask).filter(
            JourneyTask.journey_id == journey.id,
            JourneyTask.stage_name == "Scholarships"
        ).all()
        for t in schol_tasks:
            t.completed = True

        # Complete stage
        schol_stage = db.query(JourneyStage).filter(
            JourneyStage.journey_id == journey.id,
            JourneyStage.stage_name == "Scholarships"
        ).first()
        if schol_stage:
            schol_stage.status = "Completed"
            schol_stage.completion_percentage = 100.0

            # Advance to SOP
            sop_stage = db.query(JourneyStage).filter(
                JourneyStage.journey_id == journey.id,
                JourneyStage.stage_name == "SOP"
            ).first()
            if sop_stage and sop_stage.status == "Not Started":
                sop_stage.status = "In Progress"
                journey.current_stage = "SOP"

        # Log Activity
        activity = JourneyActivity(
            journey_id=journey.id,
            activity_type="Scholarship Saved",
            description=f"Saved scholarship plan matching eligibility: {schol_name}."
        )
        db.add(activity)
        db.commit()

        # Recalculate
        JourneyAutomationService.recalculate_overall_progress(db, journey.id)

    @staticmethod
    def on_payment_completed(db: Session, user_id: str, service_slug: str):
        """
        Advanced auto-trigger: Unlocks premium journey tasks when a paid invoice is detected.
        """
        journey = db.query(StudentJourney).filter(StudentJourney.user_id == user_id).first()
        if not journey:
            return

        # Unlock all premium tasks
        tasks = db.query(JourneyTask).filter(
            JourneyTask.journey_id == journey.id,
            JourneyTask.is_premium == True
        ).all()
        for t in tasks:
            t.is_premium = False  # Set to False so it appears as unlocked standard task

        # Add payment confirmation activity log
        activity = JourneyActivity(
            journey_id=journey.id,
            activity_type="Premium Unlocked",
            description=f"Transaction verified for package '{service_slug}'. Advanced AI Tasks unlocked."
        )
        db.add(activity)
        db.commit()

        # Recalculate
        JourneyAutomationService.recalculate_overall_progress(db, journey.id)

    @staticmethod
    def on_visa_report_ready(db: Session, user_id: str, readiness_score: int):
        """
        Advanced auto-trigger: Automatically populates visa timeline checkpoints and biometrics reminders.
        """
        journey = db.query(StudentJourney).filter(StudentJourney.user_id == user_id).first()
        if not journey:
            return

        # Update Visa stage tasks
        visa_tasks = db.query(JourneyTask).filter(
            JourneyTask.journey_id == journey.id,
            JourneyTask.stage_name == "Visa Documents"
        ).all()
        for t in visa_tasks:
            t.completed = True

        # Advance stage
        visa_stage = db.query(JourneyStage).filter(
            JourneyStage.journey_id == journey.id,
            JourneyStage.stage_name == "Visa Documents"
        ).first()
        if visa_stage:
            visa_stage.status = "Completed"
            visa_stage.completion_percentage = 100.0

            # Advance to submission
            sub_stage = db.query(JourneyStage).filter(
                JourneyStage.journey_id == journey.id,
                JourneyStage.stage_name == "Visa Submission"
            ).first()
            if sub_stage and sub_stage.status == "Not Started":
                sub_stage.status = "In Progress"
                journey.current_stage = "Visa Submission"

        # Update Visa Tracker readiness score
        tracker = db.query(VisaTracker).filter(VisaTracker.journey_id == journey.id).first()
        if tracker:
            tracker.readiness_score = readiness_score
            tracker.current_stage = "Biometrics"
            tracker.biometrics_date = (datetime.utcnow() + timedelta(days=15)).strftime("%Y-%m-%d")
            tracker.interview_date = (datetime.utcnow() + timedelta(days=25)).strftime("%Y-%m-%d")
            tracker.submission_date = datetime.utcnow().strftime("%Y-%m-%d")
            tracker.status = "Submitted"

            # Create biometrics calendar event
            cal = CalendarEvent(
                user_id=user_id,
                event_title="Visa Biometrics Enrolment Slot",
                event_type="Biometrics",
                event_date=tracker.biometrics_date,
                reference_id=tracker.id
            )
            db.add(cal)

            # Create interview calendar event
            cal_int = CalendarEvent(
                user_id=user_id,
                event_title="Embassy Visa Interview Schedule",
                event_type="Interview",
                event_date=tracker.interview_date,
                reference_id=tracker.id
            )
            db.add(cal_int)

        # Log Activity
        activity = JourneyActivity(
            journey_id=journey.id,
            activity_type="Visa Audit Ready",
            description=f"AI Visa readiness checker scan complete. Readiness Score: {readiness_score}%."
        )
        db.add(activity)
        db.commit()

        # Recalculate
        JourneyAutomationService.recalculate_overall_progress(db, journey.id)
