import uuid
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

def generate_uuid():
    return str(uuid.uuid4())

class EligibilityRequest(Base):
    __tablename__ = "eligibility_requests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False, index=True)
    phone = Column(String(20), nullable=False)
    country_residence = Column(String(100), nullable=False)
    nationality = Column(String(100), nullable=False)
    
    qualification = Column(String(100), nullable=False)
    gpa_10th = Column(Float, nullable=False)
    gpa_12th = Column(Float, nullable=False)
    cgpa_bachelors = Column(Float, nullable=True)
    cgpa_masters = Column(Float, nullable=True)
    grad_year = Column(Integer, nullable=False)
    
    english_exam = Column(String(50), nullable=False)
    english_score = Column(Float, nullable=True)
    
    preferred_country = Column(String(100), nullable=False)
    preferred_course = Column(String(100), nullable=False)
    preferred_intake = Column(String(50), nullable=False)
    budget_range = Column(String(50), nullable=False)
    scholarship_required = Column(Boolean, default=False)
    
    work_experience = Column(Float, default=0.0)
    gap_years = Column(Integer, default=0)
    neet_score = Column(Integer, nullable=True)
    passport_available = Column(Boolean, default=False)
    
    ip_address = Column(String(50), nullable=True)
    status = Column(String(20), default="pending")  # pending, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to result
    result = relationship("EligibilityResult", back_populates="request", uselist=False, cascade="all, delete-orphan")


class EligibilityResult(Base):
    __tablename__ = "eligibility_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    request_id = Column(String(36), ForeignKey("eligibility_requests.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    overall_score = Column(Integer, nullable=False)
    admission_probability = Column(String(20), nullable=False)  # Low, Medium, High
    scholarship_potential = Column(String(20), nullable=False)  # Low, Medium, High
    visa_readiness = Column(String(20), nullable=False)         # Low, Medium, High
    
    strengths = Column(JSON, nullable=False)                   # List[str]
    weaknesses = Column(JSON, nullable=False)                  # List[str]
    suggested_improvements = Column(JSON, nullable=False)      # List[str]
    recommended_countries = Column(JSON, nullable=False)       # List[str]
    recommended_universities = Column(JSON, nullable=False)    # List[dict] -> name, location, reasoning
    suggested_next_steps = Column(JSON, nullable=False)        # List[str]
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to request
    request = relationship("EligibilityRequest", back_populates="result")


class Service(Base):
    __tablename__ = "services"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(String(1000), nullable=False)
    short_description = Column(String(250), nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String(10), default="INR")
    icon = Column(String(50), nullable=False)  # Lucide icon name
    badge = Column(String(50), nullable=True)   # Popular, Best Value, etc.
    active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    features = Column(JSON, nullable=False)    # List[str]
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    orders = relationship("Order", back_populates="service")


class Order(Base):
    __tablename__ = "orders"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=True)  # Nullable for guest checkout
    service_id = Column(String(36), ForeignKey("services.id"), nullable=False)
    razorpay_order_id = Column(String(100), unique=True, index=True, nullable=False)
    amount = Column(Float, nullable=False)  # Store in rupees (e.g. 999.00)
    currency = Column(String(10), default="INR")
    payment_status = Column(String(20), default="pending")  # pending, paid, failed
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    service = relationship("Service", back_populates="orders")
    payment = relationship("Payment", back_populates="order", uselist=False)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=False, unique=True)
    razorpay_payment_id = Column(String(100), unique=True, index=True, nullable=False)
    razorpay_signature = Column(String(250), nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(50), nullable=False)
    status = Column(String(50), default="captured")  # captured, failed, refunded
    transaction_date = Column(DateTime, default=datetime.utcnow)
    receipt_number = Column(String(100), nullable=False)

    # Relationships
    order = relationship("Order", back_populates="payment")


class SOPDocument(Base):
    __tablename__ = "sop_documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=True)  # Nullable for guest/local testing
    title = Column(String(150), nullable=False)
    target_country = Column(String(100), nullable=False)
    target_university = Column(String(150), nullable=False)
    target_course = Column(String(150), nullable=False)
    content = Column(String(30000), nullable=False)  # Rich text HTML or markdown format
    ai_model = Column(String(50), default="gpt-4o-mini")
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    versions = relationship("SOPVersion", back_populates="document", cascade="all, delete-orphan")


class SOPVersion(Base):
    __tablename__ = "sop_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("sop_documents.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    content = Column(String(30000), nullable=False)
    changes = Column(String(250), nullable=False)  # e.g., "Initial Draft", "Rewrote paragraph 2"
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("SOPDocument", back_populates="versions")


class VisaDocumentCheck(Base):
    __tablename__ = "visa_document_checks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=True)  # Nullable for guest/local testing
    country = Column(String(100), nullable=False)  # Canada, UK, USA, etc.
    visa_type = Column(String(50), default="Student Visa")  # Student, Work, Visitor
    readiness_score = Column(Integer, default=0)
    status = Column(String(30), default="Needs Improvement")  # Ready, Needs Improvement, Critical Issues
    ai_response = Column(JSON, nullable=True)  # Full parsed ChatGPT JSON report
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    uploaded_documents = relationship("UploadedDocument", back_populates="check", cascade="all, delete-orphan")
    analyses = relationship("DocumentAnalysis", back_populates="check", cascade="all, delete-orphan")


class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    check_id = Column(String(36), ForeignKey("visa_document_checks.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(String(100), nullable=False)  # Passport, Bank Statements, LOA, etc.
    filename = Column(String(200), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_path = Column(String(300), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    check = relationship("VisaDocumentCheck", back_populates="uploaded_documents")
    analysis = relationship("DocumentAnalysis", back_populates="uploaded_document", uselist=False)


class DocumentAnalysis(Base):
    __tablename__ = "document_analyses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    check_id = Column(String(36), ForeignKey("visa_document_checks.id", ondelete="CASCADE"), nullable=False)
    uploaded_document_id = Column(String(36), ForeignKey("uploaded_documents.id", ondelete="SET NULL"), nullable=True)
    document_name = Column(String(150), nullable=False)
    status = Column(String(20), default="Warning")  # Passed, Warning, Failed
    issues = Column(JSON, nullable=False)  # List[str]
    suggestions = Column(JSON, nullable=False)  # List[str]
    confidence_score = Column(Float, default=1.0)
    critical = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    check = relationship("VisaDocumentCheck", back_populates="analyses")
    uploaded_document = relationship("UploadedDocument", back_populates="analysis")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user")
    type = Column(String(30), default="info")  # info, success, warning
    title = Column(String(150), nullable=False)
    message = Column(String(1000), nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user")
    consultant_name = Column(String(100), nullable=False)
    date_time = Column(DateTime, nullable=False)
    meeting_link = Column(String(300), nullable=False)
    status = Column(String(30), default="upcoming")  # upcoming, completed, cancelled
    notes = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserSetting(Base):
    __tablename__ = "user_settings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user", unique=True, index=True)
    email_notifications = Column(Boolean, default=True)
    sms_notifications = Column(Boolean, default=False)
    marketing_emails = Column(Boolean, default=False)
    privacy_profile_public = Column(Boolean, default=False)
    language = Column(String(50), default="English")
    created_at = Column(DateTime, default=datetime.utcnow)


class DashboardActivity(Base):
    __tablename__ = "dashboard_activities"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user")
    activity_type = Column(String(50), nullable=False)  # Payment, SOP Draft, Visa Audit
    description = Column(String(250), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class University(Base):
    __tablename__ = "universities"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False, unique=True)
    country = Column(String(100), nullable=False)
    world_ranking = Column(Integer, nullable=True)
    tuition_fee_range = Column(String(100), nullable=False)  # e.g., "$25,000 - $45,000 CAD"
    average_living_cost = Column(String(100), nullable=False)  # e.g., "$15,000 CAD"
    admission_rate = Column(String(50), nullable=True)  # e.g., "43%"
    created_at = Column(DateTime, default=datetime.utcnow)


class UniversityMatch(Base):
    __tablename__ = "university_matches"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=True, default="guest_user")
    profile_data = Column(JSON, nullable=False)  # Stores Student Input dictionary
    recommendations = Column(JSON, nullable=False)  # Stores ChatGPT ranked recommendations array
    created_at = Column(DateTime, default=datetime.utcnow)


class SavedUniversity(Base):
    __tablename__ = "saved_universities"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user")
    name = Column(String(200), nullable=False)
    country = Column(String(100), nullable=False)
    course = Column(String(200), nullable=False)
    tuition_fee = Column(String(100), nullable=False)
    match_percentage = Column(Integer, default=90)
    created_at = Column(DateTime, default=datetime.utcnow)


class UniversityComparison(Base):
    __tablename__ = "university_comparisons"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user")
    name = Column(String(150), nullable=False)  # e.g. "My USA Choices"
    data = Column(JSON, nullable=False)  # List of compared universities details dictionary
    created_at = Column(DateTime, default=datetime.utcnow)


class Application(Base):
    __tablename__ = "applications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user")
    university = Column(String(200), nullable=False)
    country = Column(String(100), nullable=False)
    course = Column(String(200), nullable=False)
    degree = Column(String(100), nullable=False)
    intake = Column(String(100), nullable=False)
    tuition_fee = Column(String(100), nullable=True)
    application_fee = Column(String(100), nullable=True)
    deadline = Column(String(100), nullable=True)
    current_status = Column(String(50), default="Interested")  # pipeline stage
    priority = Column(String(30), default="Medium")  # High, Medium, Low
    notes = Column(String(2000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tasks = relationship("ApplicationTask", back_populates="application", cascade="all, delete-orphan")
    documents = relationship("ApplicationDocument", back_populates="application", cascade="all, delete-orphan")
    notes_list = relationship("ApplicationNote", back_populates="application", cascade="all, delete-orphan")
    timeline = relationship("ApplicationTimeline", back_populates="application", cascade="all, delete-orphan")
    calendar_items = relationship("ApplicationCalendarItem", back_populates="application", cascade="all, delete-orphan")


class ApplicationTask(Base):
    __tablename__ = "application_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    application_id = Column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(250), nullable=False)
    status = Column(String(30), default="pending")  # pending, completed
    due_date = Column(String(100), nullable=True)
    priority = Column(String(30), default="Medium")
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    application = relationship("Application", back_populates="tasks")


class ApplicationDocument(Base):
    __tablename__ = "application_documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    application_id = Column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    document_name = Column(String(150), nullable=False)  # Passport, SOP, Resume, etc.
    status = Column(String(30), default="Pending")  # Uploaded, Pending, Expired, Rejected, Approved
    file_path = Column(String(300), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    application = relationship("Application", back_populates="documents")


class ApplicationNote(Base):
    __tablename__ = "application_notes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    application_id = Column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(String(5000), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    application = relationship("Application", back_populates="notes_list")


class ApplicationTimeline(Base):
    __tablename__ = "application_timeline"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    application_id = Column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    event_title = Column(String(150), nullable=False)
    event_description = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    application = relationship("Application", back_populates="timeline")


class ApplicationCalendarItem(Base):
    __tablename__ = "application_calendar"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    application_id = Column(String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=True)
    event_title = Column(String(250), nullable=False)
    event_type = Column(String(50), nullable=False)  # Deadline, Visa Appointment, etc.
    event_date = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    application = relationship("Application", back_populates="calendar_items")


class VisaProfile(Base):
    __tablename__ = "visa_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user")
    country = Column(String(100), nullable=False)
    visa_type = Column(String(100), nullable=False)
    current_stage = Column(String(100), default="Application")  # Application, Documents, Biometrics, Interview, Approved
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    readiness_reports = relationship("VisaReadinessReport", back_populates="profile", cascade="all, delete-orphan")
    checklist_items = relationship("VisaChecklist", back_populates="profile", cascade="all, delete-orphan")
    tasks = relationship("VisaTask", back_populates="profile", cascade="all, delete-orphan")
    interviews = relationship("VisaInterview", back_populates="profile", cascade="all, delete-orphan")
    financials = relationship("VisaFinancial", back_populates="profile", cascade="all, delete-orphan")
    timeline_items = relationship("VisaTimelineItem", back_populates="profile", cascade="all, delete-orphan")
    recommendations = relationship("VisaRecommendation", back_populates="profile", cascade="all, delete-orphan")


class VisaReadinessReport(Base):
    __tablename__ = "visa_readiness_reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("visa_profiles.id", ondelete="CASCADE"), nullable=False)
    overall_score = Column(Integer, default=50)
    risk_level = Column(String(50), default="Medium")  # Low, Medium, High
    critical_issues = Column(JSON, nullable=True)  # List of critical risks
    suggested_improvements = Column(JSON, nullable=True)  # List of improvement tasks
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    profile = relationship("VisaProfile", back_populates="readiness_reports")


class VisaChecklist(Base):
    __tablename__ = "visa_checklists"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("visa_profiles.id", ondelete="CASCADE"), nullable=False)
    item_name = Column(String(200), nullable=False)
    status = Column(String(50), default="Pending")  # Pending, Completed, Rejected, Needs Review
    notes = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    profile = relationship("VisaProfile", back_populates="checklist_items")


class VisaTask(Base):
    __tablename__ = "visa_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("visa_profiles.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(250), nullable=False)
    due_date = Column(String(100), nullable=True)
    status = Column(String(30), default="pending")  # pending, completed
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    profile = relationship("VisaProfile", back_populates="tasks")


class VisaInterview(Base):
    __tablename__ = "visa_interviews"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("visa_profiles.id", ondelete="CASCADE"), nullable=False)
    questions = Column(JSON, nullable=False)  # List of Question logs: question, answer, feedback, score, rating, suggestions
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    profile = relationship("VisaProfile", back_populates="interviews")


class VisaFinancial(Base):
    __tablename__ = "visa_financials"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("visa_profiles.id", ondelete="CASCADE"), nullable=False)
    tuition_fee = Column(Float, default=0.0)
    living_expenses = Column(Float, default=0.0)
    scholarship_amount = Column(Float, default=0.0)
    education_loan = Column(Float, default=0.0)
    savings = Column(Float, default=0.0)
    required_funds = Column(Float, default=0.0)
    available_funds = Column(Float, default=0.0)
    funding_gap = Column(Float, default=0.0)
    readiness_score = Column(Integer, default=50)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    profile = relationship("VisaProfile", back_populates="financials")


class VisaTimelineItem(Base):
    __tablename__ = "visa_timelines"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("visa_profiles.id", ondelete="CASCADE"), nullable=False)
    event_title = Column(String(200), nullable=False)
    event_date = Column(String(100), nullable=False)
    status = Column(String(50), default="Pending")  # Pending, Completed
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    profile = relationship("VisaProfile", back_populates="timeline_items")


class VisaRecommendation(Base):
    __tablename__ = "visa_recommendations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("visa_profiles.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(String(1000), nullable=False)
    actionable = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    profile = relationship("VisaProfile", back_populates="recommendations")


class Scholarship(Base):
    __tablename__ = "scholarships"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(250), nullable=False)
    provider = Column(String(250), nullable=False)
    country = Column(String(100), nullable=False)
    university = Column(String(250), nullable=True)
    funding_amount = Column(String(150), nullable=False)
    coverage = Column(String(150), nullable=False)
    eligibility_criteria = Column(String(2000), nullable=False)
    difficulty_level = Column(String(50), default="Medium")  # High, Medium, Low
    deadline = Column(String(100), nullable=True)
    website_placeholder = Column(String(300), default="https://auraroutes.com/scholarships")
    created_at = Column(DateTime, default=datetime.utcnow)


class ScholarshipMatch(Base):
    __tablename__ = "scholarship_matches"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user")
    profile_data = Column(JSON, nullable=False)  # Student profile details dictionary
    recommendations = Column(JSON, nullable=False)  # List of recommended scholarships matched
    created_at = Column(DateTime, default=datetime.utcnow)


class SavedScholarship(Base):
    __tablename__ = "saved_scholarships"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user")
    scholarship_id = Column(String(36), nullable=True)
    name = Column(String(250), nullable=False)
    provider = Column(String(250), nullable=False)
    country = Column(String(100), nullable=False)
    funding_amount = Column(String(150), nullable=False)
    match_percentage = Column(Integer, default=80)
    deadline = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FundingPlan(Base):
    __tablename__ = "funding_plans"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user")
    tuition_fee = Column(Float, default=0.0)
    living_cost = Column(Float, default=0.0)
    travel_cost = Column(Float, default=0.0)
    visa_cost = Column(Float, default=0.0)
    insurance = Column(Float, default=0.0)
    misc_expenses = Column(Float, default=0.0)
    scholarship_amount = Column(Float, default=0.0)
    loan_amount = Column(Float, default=0.0)
    savings = Column(Float, default=0.0)
    funding_gap = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    total_available = Column(Float, default=0.0)
    readiness_score = Column(Integer, default=50)
    suggested_plan = Column(String(5000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ScholarshipDeadline(Base):
    __tablename__ = "scholarship_deadlines"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user")
    event_title = Column(String(250), nullable=False)
    event_type = Column(String(100), nullable=False)  # Deadline, Interview Date, etc.
    event_date = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ScholarshipReport(Base):
    __tablename__ = "scholarship_reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user")
    report_data = Column(JSON, nullable=False)  # Complete matching layout dictionary
    created_at = Column(DateTime, default=datetime.utcnow)


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(150), nullable=False)
    event = Column(String(100), nullable=False, unique=True)
    template = Column(String(1000), nullable=False)
    active = Column(Boolean, default=True)


class WhatsAppNotification(Base):
    __tablename__ = "whatsapp_notifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user")
    event_type = Column(String(100), nullable=False)
    phone_number = Column(String(30), nullable=False)
    template_name = Column(String(150), nullable=False)
    message = Column(String(2000), nullable=False)
    status = Column(String(50), default="Pending")  # Pending, Processing, Sent, Failed, Retry, Cancelled
    retry_count = Column(Integer, default=0)
    provider_message_id = Column(String(150), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserNotificationPreference(Base):
    __tablename__ = "user_notification_preferences"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user")
    enable_whatsapp = Column(Boolean, default=True)
    categories = Column(JSON, nullable=False)  # JSON array lists of enabled events, e.g. ["payments", "sop"]
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    is_pinned = Column(Boolean, default=False)
    is_favorite = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    files = relationship("ChatFile", back_populates="session", cascade="all, delete-orphan")
    context = relationship("ChatContext", back_populates="session", uselist=False, cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(String(10000), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")
    feedbacks = relationship("ChatFeedback", back_populates="message", cascade="all, delete-orphan")


class ChatFile(Base):
    __tablename__ = "chat_files"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(250), nullable=False)
    file_type = Column(String(100), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="files")


class ChatContext(Base):
    __tablename__ = "chat_contexts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    student_profile_snapshot = Column(JSON, nullable=True)
    eligibility_report_snapshot = Column(JSON, nullable=True)
    sop_snapshot = Column(JSON, nullable=True)
    visa_report_snapshot = Column(JSON, nullable=True)
    scholarship_report_snapshot = Column(JSON, nullable=True)
    application_status = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="context")


class ChatFeedback(Base):
    __tablename__ = "chat_feedbacks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    message_id = Column(String(36), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1 for thumbs up, -1 for thumbs down
    comment = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    message = relationship("ChatMessage", back_populates="feedbacks")


class AIUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=False, index=True)
    prompt_tokens = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    model_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class StudentJourney(Base):
    __tablename__ = "student_journey"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), unique=True, index=True, nullable=False)
    overall_progress = Column(Float, default=0.0)
    current_stage = Column(String(50), default="Eligibility")
    health_score = Column(Integer, default=100)
    start_date = Column(DateTime, default=datetime.utcnow)
    expected_completion_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    stages = relationship("JourneyStage", back_populates="journey", cascade="all, delete-orphan")
    tasks = relationship("JourneyTask", back_populates="journey", cascade="all, delete-orphan")
    activities = relationship("JourneyActivity", back_populates="journey", cascade="all, delete-orphan")
    visa_tracker = relationship("VisaTracker", back_populates="journey", uselist=False, cascade="all, delete-orphan")


class JourneyStage(Base):
    __tablename__ = "journey_stage"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    journey_id = Column(String(36), ForeignKey("student_journey.id", ondelete="CASCADE"), nullable=False)
    stage_name = Column(String(50), nullable=False)
    status = Column(String(30), default="Not Started")  # Not Started, In Progress, Completed, Blocked
    completion_percentage = Column(Float, default=0.0)
    notes = Column(String(2000), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    journey = relationship("StudentJourney", back_populates="stages")


class JourneyTask(Base):
    __tablename__ = "journey_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    journey_id = Column(String(36), ForeignKey("student_journey.id", ondelete="CASCADE"), nullable=False)
    stage_name = Column(String(50), nullable=False)
    title = Column(String(250), nullable=False)
    priority = Column(String(20), default="Medium")  # High, Medium, Low
    due_date = Column(String(100), nullable=True)
    completed = Column(Boolean, default=False)
    reminder = Column(Boolean, default=False)
    notes = Column(String(1000), nullable=True)
    is_premium = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    journey = relationship("StudentJourney", back_populates="tasks")


class JourneyActivity(Base):
    __tablename__ = "journey_activity"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    journey_id = Column(String(36), ForeignKey("student_journey.id", ondelete="CASCADE"), nullable=False)
    activity_type = Column(String(50), nullable=False)
    description = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    journey = relationship("StudentJourney", back_populates="activities")


class VisaTracker(Base):
    __tablename__ = "visa_tracker"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    journey_id = Column(String(36), ForeignKey("student_journey.id", ondelete="CASCADE"), nullable=False, unique=True)
    visa_type = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    current_stage = Column(String(50), default="Submitted")  # Biometrics, Interview, Submitted, Processing, Approved, Rejected
    biometrics_date = Column(String(100), nullable=True)
    interview_date = Column(String(100), nullable=True)
    submission_date = Column(String(100), nullable=True)
    readiness_score = Column(Integer, default=0)
    expected_approval_date = Column(String(100), nullable=True)
    status = Column(String(30), default="Pending")  # Pending, Submitted, Approved, Rejected
    notes = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    journey = relationship("StudentJourney", back_populates="visa_tracker")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=False, index=True)
    event_title = Column(String(250), nullable=False)
    event_type = Column(String(50), nullable=False)  # Application Deadline, Scholarship Deadline, Consultation, Visa Date, Biometrics, IELTS, Travel
    event_date = Column(String(100), nullable=False)
    reference_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class StudentReminder(Base):
    __tablename__ = "student_reminders"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=False, index=True)
    title = Column(String(250), nullable=False)
    message = Column(String(1000), nullable=False)
    reminder_type = Column(String(50), nullable=False)  # Deadline, Missing Documents, Consultation, Visa, Interview, Payment, Scholarship
    trigger_date = Column(String(100), nullable=False)
    is_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# UNIVERSITY & COURSE EXPLORER — Extended Models
# ============================================================

class ExplorerUniversity(Base):
    """Full-featured university record for the Explorer module."""
    __tablename__ = "explorer_universities"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    slug = Column(String(200), unique=True, index=True, nullable=False)
    name = Column(String(250), nullable=False)
    short_name = Column(String(100), nullable=True)
    country = Column(String(100), nullable=False, index=True)
    city = Column(String(100), nullable=False)
    university_type = Column(String(50), default="Public")
    founded_year = Column(Integer, nullable=True)
    student_population = Column(Integer, nullable=True)

    logo_url = Column(String(500), nullable=True)
    hero_image_url = Column(String(500), nullable=True)
    gallery_images = Column(JSON, nullable=True)
    website = Column(String(300), nullable=True)
    description = Column(String(5000), nullable=True)
    highlights = Column(JSON, nullable=True)
    ai_summary = Column(String(3000), nullable=True)

    qs_ranking = Column(Integer, nullable=True)
    the_ranking = Column(Integer, nullable=True)
    us_news_ranking = Column(Integer, nullable=True)
    national_ranking = Column(Integer, nullable=True)

    acceptance_rate = Column(Float, nullable=True)
    ielts_requirement = Column(Float, nullable=True)
    toefl_requirement = Column(Integer, nullable=True)
    pte_requirement = Column(Integer, nullable=True)
    gre_requirement = Column(Integer, nullable=True)
    gmat_requirement = Column(Integer, nullable=True)
    min_gpa = Column(Float, nullable=True)

    tuition_min = Column(Float, nullable=True)
    tuition_max = Column(Float, nullable=True)
    tuition_currency = Column(String(10), default="USD")
    tuition_display = Column(String(150), nullable=True)
    living_cost_annual = Column(Float, nullable=True)
    living_cost_display = Column(String(150), nullable=True)
    application_fee = Column(Float, nullable=True)

    scholarship_available = Column(Boolean, default=False)
    scholarship_details = Column(JSON, nullable=True)
    employment_rate = Column(Float, nullable=True)
    average_salary_post_study = Column(String(150), nullable=True)
    top_employers = Column(JSON, nullable=True)

    visa_difficulty = Column(String(30), default="Medium")
    campus_type = Column(String(30), default="Urban")
    accommodation_available = Column(Boolean, default=True)
    accommodation_cost_display = Column(String(100), nullable=True)

    popular_courses = Column(JSON, nullable=True)
    intake_months = Column(JSON, nullable=True)
    total_programs = Column(Integer, nullable=True)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(String(500), nullable=True)

    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    courses = relationship("ExplorerCourse", back_populates="university", cascade="all, delete-orphan")
    reviews = relationship("UniversityReview", back_populates="university", cascade="all, delete-orphan")
    bookmarks = relationship("UniversityBookmark", back_populates="university", cascade="all, delete-orphan")


class ExplorerCourse(Base):
    """Course/Programme record linked to a specific university."""
    __tablename__ = "explorer_courses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    slug = Column(String(300), unique=True, index=True, nullable=False)
    university_id = Column(String(36), ForeignKey("explorer_universities.id", ondelete="CASCADE"), nullable=False)
    university_name = Column(String(250), nullable=False)
    country = Column(String(100), nullable=False)

    name = Column(String(250), nullable=False)
    degree = Column(String(100), nullable=False)
    field = Column(String(150), nullable=False)
    duration_years = Column(Float, nullable=True)
    duration_display = Column(String(100), nullable=True)
    credits = Column(Integer, nullable=True)
    mode = Column(String(50), default="Full-time")

    tuition_display = Column(String(150), nullable=True)
    tuition_annual = Column(Float, nullable=True)
    tuition_currency = Column(String(10), default="USD")

    ielts_requirement = Column(Float, nullable=True)
    toefl_requirement = Column(Integer, nullable=True)
    pte_requirement = Column(Integer, nullable=True)
    gre_requirement = Column(Integer, nullable=True)
    gmat_requirement = Column(Integer, nullable=True)
    min_gpa = Column(Float, nullable=True)
    work_experience_years = Column(Integer, nullable=True)
    other_requirements = Column(JSON, nullable=True)

    scholarship_available = Column(Boolean, default=False)
    scholarship_amount = Column(String(150), nullable=True)

    career_outcomes = Column(JSON, nullable=True)
    salary_estimate_display = Column(String(150), nullable=True)
    employment_rate = Column(Float, nullable=True)

    intake_months = Column(JSON, nullable=True)
    application_deadline = Column(String(150), nullable=True)

    description = Column(String(3000), nullable=True)
    curriculum_highlights = Column(JSON, nullable=True)

    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    university = relationship("ExplorerUniversity", back_populates="courses")
    bookmarks = relationship("CourseBookmark", back_populates="course", cascade="all, delete-orphan")


class ExplorerCountry(Base):
    """Country overview for study destination pages."""
    __tablename__ = "explorer_countries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    flag_emoji = Column(String(10), nullable=True)
    hero_image_url = Column(String(500), nullable=True)
    description = Column(String(5000), nullable=True)

    living_cost_monthly_display = Column(String(150), nullable=True)
    living_cost_monthly_usd = Column(Float, nullable=True)
    avg_rent_display = Column(String(150), nullable=True)
    avg_food_display = Column(String(150), nullable=True)
    avg_transport_display = Column(String(150), nullable=True)

    student_visa_name = Column(String(150), nullable=True)
    visa_processing_time = Column(String(100), nullable=True)
    visa_fee_display = Column(String(100), nullable=True)
    visa_requirements_summary = Column(JSON, nullable=True)
    visa_difficulty = Column(String(30), default="Medium")

    work_rights_during_study = Column(String(300), nullable=True)
    work_hours_per_week = Column(Integer, nullable=True)
    post_study_work_visa = Column(String(200), nullable=True)
    post_study_work_duration = Column(String(100), nullable=True)

    average_salary_display = Column(String(150), nullable=True)
    top_industries = Column(JSON, nullable=True)
    popular_courses = Column(JSON, nullable=True)

    climate = Column(String(200), nullable=True)
    official_language = Column(String(100), nullable=True)
    currency = Column(String(50), nullable=True)

    government_scholarships = Column(JSON, nullable=True)
    ai_summary = Column(String(3000), nullable=True)

    total_universities = Column(Integer, nullable=True)
    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UniversityBookmark(Base):
    __tablename__ = "university_bookmarks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=False, index=True)
    university_id = Column(String(36), ForeignKey("explorer_universities.id", ondelete="CASCADE"), nullable=False)
    collection_name = Column(String(100), default="My Shortlist")
    created_at = Column(DateTime, default=datetime.utcnow)

    university = relationship("ExplorerUniversity", back_populates="bookmarks")


class CourseBookmark(Base):
    __tablename__ = "course_bookmarks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=False, index=True)
    course_id = Column(String(36), ForeignKey("explorer_courses.id", ondelete="CASCADE"), nullable=False)
    collection_name = Column(String(100), default="My Courses")
    created_at = Column(DateTime, default=datetime.utcnow)

    course = relationship("ExplorerCourse", back_populates="bookmarks")


class CountryBookmark(Base):
    __tablename__ = "country_bookmarks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=False, index=True)
    country_slug = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ExplorerRecentSearch(Base):
    __tablename__ = "explorer_recent_searches"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=False, index=True)
    query = Column(String(300), nullable=False)
    search_type = Column(String(50), default="global")
    created_at = Column(DateTime, default=datetime.utcnow)


class UniversityReview(Base):
    __tablename__ = "university_reviews"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    university_id = Column(String(36), ForeignKey("explorer_universities.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(100), nullable=False)
    rating = Column(Integer, nullable=False)
    pros = Column(JSON, nullable=True)
    cons = Column(JSON, nullable=True)
    review_text = Column(String(3000), nullable=True)
    program_studied = Column(String(250), nullable=True)
    graduation_year = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    university = relationship("ExplorerUniversity", back_populates="reviews")


class ExplorerComparison(Base):
    __tablename__ = "explorer_comparisons"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=False, index=True)
    name = Column(String(200), nullable=True)
    university_slugs = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)














# ============================================================
# KNOWLEDGE CENTER � Article and Content Models
# ============================================================


class KCCategory(Base):
    """Knowledge Center category taxonomy."""
    __tablename__ = "kc_categories"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    slug = Column(String(200), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=True)
    icon = Column(String(100), nullable=True)
    color = Column(String(50), nullable=True)
    hero_color = Column(String(100), nullable=True)
    parent_id = Column(String(36), ForeignKey("kc_categories.id"), nullable=True)
    display_order = Column(Integer, default=0)
    article_count = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    articles = relationship("KCArticle", back_populates="category")


class KCArticle(Base):
    """Full knowledge center article with rich content blocks and SEO metadata."""
    __tablename__ = "kc_articles"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    slug = Column(String(300), unique=True, index=True, nullable=False)
    title = Column(String(500), nullable=False)
    subtitle = Column(String(500), nullable=True)
    excerpt = Column(String(1000), nullable=True)
    category_id = Column(String(36), ForeignKey("kc_categories.id"), nullable=True)
    category_name = Column(String(200), nullable=True)
    country = Column(String(100), nullable=True, index=True)
    tags = Column(JSON, nullable=True)
    content_blocks = Column(JSON, nullable=True)
    table_of_contents = Column(JSON, nullable=True)
    faqs = Column(JSON, nullable=True)
    hero_image_url = Column(String(500), nullable=True)
    reading_time_minutes = Column(Integer, default=5)
    word_count = Column(Integer, default=0)
    difficulty = Column(String(50), default="Beginner")
    author_name = Column(String(200), default="Aura Routes AI Team")
    author_role = Column(String(200), default="Study Abroad Expert")
    author_avatar = Column(String(500), nullable=True)
    published_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    seo_title = Column(String(500), nullable=True)
    seo_description = Column(String(500), nullable=True)
    seo_keywords = Column(JSON, nullable=True)
    canonical_url = Column(String(500), nullable=True)
    og_image = Column(String(500), nullable=True)
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    bookmark_count = Column(Integer, default=0)
    share_count = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)
    is_published = Column(Boolean, default=True)
    is_ai_generated = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    category = relationship("KCCategory", back_populates="articles")
    bookmarks = relationship("KCBookmark", back_populates="article", cascade="all, delete-orphan")
    reading_history = relationship("KCReadingHistory", back_populates="article", cascade="all, delete-orphan")
    likes = relationship("KCArticleLike", back_populates="article", cascade="all, delete-orphan")


class KCTag(Base):
    __tablename__ = "kc_tags"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    slug = Column(String(200), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    article_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)


class KCBookmark(Base):
    __tablename__ = "kc_bookmarks"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=False, index=True)
    article_id = Column(String(36), ForeignKey("kc_articles.id", ondelete="CASCADE"), nullable=False)
    collection_name = Column(String(200), default="My Saves")
    created_at = Column(DateTime, default=datetime.utcnow)
    article = relationship("KCArticle", back_populates="bookmarks")


class KCReadingHistory(Base):
    __tablename__ = "kc_reading_history"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=False, index=True)
    article_id = Column(String(36), ForeignKey("kc_articles.id", ondelete="CASCADE"), nullable=False)
    progress_percent = Column(Integer, default=0)
    last_read_at = Column(DateTime, default=datetime.utcnow)
    completed = Column(Boolean, default=False)
    article = relationship("KCArticle", back_populates="reading_history")


class KCArticleLike(Base):
    __tablename__ = "kc_article_likes"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=False, index=True)
    article_id = Column(String(36), ForeignKey("kc_articles.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    article = relationship("KCArticle", back_populates="likes")


class KCAIGeneratedDraft(Base):
    __tablename__ = "kc_ai_generated_drafts"
    id = Column(String(36), primary_key=True, default=generate_uuid)
    topic = Column(String(300), nullable=False)
    category_slug = Column(String(200), nullable=True)
    country = Column(String(100), nullable=True)
    generated_title = Column(String(500), nullable=True)
    generated_slug = Column(String(300), nullable=True)
    generated_content = Column(JSON, nullable=True)
    status = Column(String(50), default="draft")
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)


# ============================================================
# COMMUNICATION CENTER — Unified Inbox & Support Models
# ============================================================

class EmailLog(Base):
    """Logs of transactional emails sent to the student."""
    __tablename__ = "email_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user", index=True)
    recipient_email = Column(String(200), nullable=False)
    subject = Column(String(300), nullable=False)
    body_html = Column(String(10000), nullable=False)
    status = Column(String(50), default="Sent")  # Sent, Failed
    attachments = Column(JSON, nullable=True)     # List of dicts: {name, url, size}
    created_at = Column(DateTime, default=datetime.utcnow)


class SupportTicket(Base):
    """Customer support tickets created by students."""
    __tablename__ = "support_tickets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user", index=True)
    title = Column(String(300), nullable=False)
    category = Column(String(100), default="General")  # General, Technical, Payments, Visa, University, Scholarships
    priority = Column(String(50), default="Medium")     # Low, Medium, High, Urgent
    status = Column(String(50), default="Open")         # Open, InProgress, Resolved, Closed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("TicketMessage", back_populates="ticket", cascade="all, delete-orphan")


class TicketMessage(Base):
    """In-ticket conversational message logs."""
    __tablename__ = "ticket_messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    ticket_id = Column(String(36), ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(String(100), nullable=False)
    sender_role = Column(String(50), default="student")  # student, admin, agent
    message = Column(String(4000), nullable=False)
    attachments = Column(JSON, nullable=True)            # List of URLs or dicts
    created_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("SupportTicket", back_populates="messages")


class Announcement(Base):
    """Global system announcements."""
    __tablename__ = "announcements"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(300), nullable=False)
    content = Column(String(5000), nullable=False)
    category = Column(String(100), default="Update")  # Update, Scholarship, Visa, News, Deadline
    priority = Column(String(50), default="Info")     # Info, Important, Critical
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DownloadItem(Base):
    """Unified file download log for generated documents, SOPs, receipts, etc."""
    __tablename__ = "downloads"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user", index=True)
    title = Column(String(300), nullable=False)
    file_type = Column(String(100), nullable=False)  # SOP, VisaReport, EligibilityReport, ScholarshipReport, Invoice, Receipt, Other
    file_url = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CommunicationActivity(Base):
    """Aggregated timeline activity of all communication items."""
    __tablename__ = "communication_activity"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), default="guest_user", index=True)
    activity_type = Column(String(100), nullable=False)  # notification, email, whatsapp, appointment, ticket, announcement, download
    title = Column(String(300), nullable=False)
    reference_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# MASTER PROFILE & SETTINGS MODELS
# ============================================================

class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    email = Column(String(100), unique=True, index=True, nullable=True)
    phone = Column(String(20), nullable=True)
    nationality = Column(String(100), nullable=True)
    country_residence = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    gender = Column(String(20), nullable=True)
    date_of_birth = Column(String(20), nullable=True)
    passport_number = Column(String(50), nullable=True)
    passport_expiry = Column(String(20), nullable=True)
    emergency_contact_name = Column(String(100), nullable=True)
    emergency_contact_relation = Column(String(100), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)
    photo_url = Column(String(300), nullable=True)
    verification_status = Column(String(20), default="Unverified")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    academic_profile = relationship("AcademicProfile", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    study_preferences = relationship("StudyPreference", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    financial_profile = relationship("FinancialProfile", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    language_preferences = relationship("LanguagePreference", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    notification_preferences = relationship("NotificationPreference", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    security_settings = relationship("SecuritySetting", back_populates="profile", uselist=False, cascade="all, delete-orphan")
    connected_accounts = relationship("ConnectedAccount", back_populates="profile", cascade="all, delete-orphan")


class AcademicProfile(Base):
    __tablename__ = "academic_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, unique=True)
    highest_qualification = Column(String(100), nullable=True)
    gpa_10th = Column(Float, nullable=True)
    gpa_12th = Column(Float, nullable=True)
    cgpa_bachelors = Column(Float, nullable=True)
    cgpa_masters = Column(Float, nullable=True)
    grad_year = Column(Integer, nullable=True)
    university = Column(String(200), nullable=True)
    college = Column(String(200), nullable=True)
    backlogs = Column(Integer, default=0)
    research_papers = Column(JSON, default=list)
    projects = Column(JSON, default=list)
    work_experience = Column(JSON, default=list)
    internships = Column(JSON, default=list)
    certifications = Column(JSON, default=list)

    # Exam scores
    ielts_score = Column(Float, nullable=True)
    ielts_expiry = Column(String(20), nullable=True)
    toefl_score = Column(Float, nullable=True)
    toefl_expiry = Column(String(20), nullable=True)
    pte_score = Column(Float, nullable=True)
    pte_expiry = Column(String(20), nullable=True)
    duolingo_score = Column(Float, nullable=True)
    duolingo_expiry = Column(String(20), nullable=True)
    gre_score = Column(Float, nullable=True)
    gre_expiry = Column(String(20), nullable=True)
    gmat_score = Column(Float, nullable=True)
    gmat_expiry = Column(String(20), nullable=True)
    sat_score = Column(Float, nullable=True)
    sat_expiry = Column(String(20), nullable=True)
    neet_score = Column(Float, nullable=True)
    neet_expiry = Column(String(20), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="academic_profile")


class StudyPreference(Base):
    __tablename__ = "study_preferences"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, unique=True)
    preferred_countries = Column(JSON, default=list)
    preferred_universities = Column(JSON, default=list)
    preferred_courses = Column(JSON, default=list)
    degree_level = Column(String(100), nullable=True)
    budget = Column(String(100), nullable=True)
    target_intake = Column(String(100), nullable=True)
    scholarship_required = Column(Boolean, default=False)
    preferred_city = Column(String(100), nullable=True)
    preferred_language = Column(String(50), nullable=True)
    career_goals = Column(String(2000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="study_preferences")


class FinancialProfile(Base):
    __tablename__ = "financial_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, unique=True)
    annual_family_income = Column(String(100), nullable=True)
    savings = Column(Float, default=0.0)
    education_loan = Column(Float, default=0.0)
    sponsor = Column(String(100), nullable=True)
    currency = Column(String(10), default="INR")
    financial_readiness = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="financial_profile")


class LanguagePreference(Base):
    __tablename__ = "language_preferences"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, unique=True)
    preferred_language = Column(String(50), default="English")
    supported_languages = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="language_preferences")


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, unique=True)
    email = Column(Boolean, default=True)
    whatsapp = Column(Boolean, default=True)
    sms = Column(Boolean, default=False)
    in_app = Column(Boolean, default=True)
    ai_updates = Column(Boolean, default=True)
    consultation = Column(Boolean, default=True)
    payments = Column(Boolean, default=True)
    scholarships = Column(Boolean, default=True)
    visa = Column(Boolean, default=True)
    application = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="notification_preferences")


class SecuritySetting(Base):
    __tablename__ = "security_settings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, unique=True)
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_method = Column(String(50), default="email")
    two_factor_secret = Column(String(100), nullable=True)
    login_history = Column(JSON, default=list)
    active_sessions = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="security_settings")


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)  # google, linkedin, github
    provider_user_id = Column(String(100), nullable=False)
    email = Column(String(100), nullable=True)
    connected_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("Profile", back_populates="connected_accounts")


class StudentDocument(Base):
    __tablename__ = "student_documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), index=True, nullable=False)
    category = Column(String(50), nullable=False)  # Passport, Academic, Financial, Visa, Certificates
    filename = Column(String(200), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_path = Column(String(300), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
