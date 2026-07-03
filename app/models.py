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









