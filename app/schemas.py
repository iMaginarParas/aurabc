from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# Step schemas to represent client-side multi-step outputs

class PersonalInfoSchema(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=8, max_length=20)
    country_residence: str
    nationality: str

class AcademicProfileSchema(BaseModel):
    qualification: str
    gpa_10th: float = Field(..., ge=0.0)
    gpa_12th: float = Field(..., ge=0.0)
    cgpa_bachelors: Optional[float] = Field(None, ge=0.0)
    cgpa_masters: Optional[float] = Field(None, ge=0.0)
    grad_year: int = Field(..., ge=1980, le=2035)

class EnglishProficiencySchema(BaseModel):
    english_exam: str  # IELTS, TOEFL, PTE, Duolingo, None
    english_score: Optional[float] = None

class StudyPreferencesSchema(BaseModel):
    preferred_country: str
    preferred_course: str
    preferred_intake: str
    budget_range: str
    scholarship_required: bool = False

class AdditionalInfoSchema(BaseModel):
    work_experience: float = Field(0.0, ge=0.0)
    gap_years: int = Field(0, ge=0)
    neet_score: Optional[int] = Field(None, ge=0)
    passport_available: bool = False

# Unified form request schema
class EligibilityRequestCreate(BaseModel):
    personal_info: PersonalInfoSchema
    academic_profile: AcademicProfileSchema
    english_proficiency: EnglishProficiencySchema
    study_preferences: StudyPreferencesSchema
    additional_info: AdditionalInfoSchema

# University Recommendation sub-schema
class UniversityRecommendation(BaseModel):
    name: str
    location: str
    reasoning: str

# Expected Strict ChatGPT Response Format
class AIResultEvaluation(BaseModel):
    overall_score: int = Field(..., ge=0, le=100)
    admission_probability: str  # Low, Medium, High
    scholarship_potential: str  # Low, Medium, High
    visa_readiness: str         # Low, Medium, High
    strengths: List[str]
    weaknesses: List[str]
    suggested_improvements: List[str]
    recommended_countries: List[str]
    recommended_universities: List[UniversityRecommendation]
    suggested_next_steps: List[str]

# Response structures matching database models

class EligibilityResultResponse(BaseModel):
    id: str
    request_id: str
    overall_score: int
    admission_probability: str
    scholarship_potential: str
    visa_readiness: str
    strengths: List[str]
    weaknesses: List[str]
    suggested_improvements: List[str]
    recommended_countries: List[str]
    recommended_universities: List[Dict[str, Any]]
    suggested_next_steps: List[str]
    created_at: datetime

    class Config:
        from_attributes = True

class EligibilityRequestResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    phone: str
    country_residence: str
    nationality: str
    qualification: str
    gpa_10th: float
    gpa_12th: float
    cgpa_bachelors: Optional[float]
    cgpa_masters: Optional[float]
    grad_year: int
    english_exam: str
    english_score: Optional[float]
    preferred_country: str
    preferred_course: str
    preferred_intake: str
    budget_range: str
    scholarship_required: bool
    work_experience: float
    gap_years: int
    neet_score: Optional[int]
    passport_available: bool
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# Aggregated evaluation response
class EligibilityCheckResponse(BaseModel):
    request: EligibilityRequestResponse
    result: Optional[EligibilityResultResponse] = None

# Admin Paginated Logs wrapper
class PaginatedHistoryResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    requests: List[EligibilityRequestResponse]


# SERVICE CATALOG SCHEMAS
class ServiceResponse(BaseModel):
    id: str
    slug: str
    title: str
    description: str
    short_description: str
    price: float
    currency: str
    icon: str
    badge: Optional[str] = None
    active: bool
    display_order: int
    features: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ORDER SCHEMAS
class OrderCreate(BaseModel):
    service_id: str
    user_id: Optional[str] = None


class OrderResponse(BaseModel):
    id: str
    user_id: Optional[str]
    service_id: str
    razorpay_order_id: str
    amount: float
    currency: str
    payment_status: str
    created_at: datetime
    service: Optional[ServiceResponse] = None

    class Config:
        from_attributes = True


# SIGNATURE VERIFICATION SCHEMA
class PaymentVerify(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    billing_name: str
    email: EmailStr


# PAYMENT SCHEMAS
class PaymentResponse(BaseModel):
    id: str
    order_id: str
    razorpay_payment_id: str
    amount: float
    payment_method: str
    status: str
    transaction_date: datetime
    receipt_number: str

    class Config:
        from_attributes = True


# PAGINATED TRANSACTION HISTORY FOR ADMIN
class PaginatedPaymentsResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    payments: List[PaymentResponse]


# SOP GENERATION SCHEMAS
class SOPStep1Personal(BaseModel):
    full_name: str
    date_of_birth: str
    nationality: str
    current_country: str
    email: EmailStr

class SOPStep2Academic(BaseModel):
    highest_qualification: str
    university: str
    cgpa_percentage: str
    graduation_year: str
    academic_achievements: Optional[str] = ""

class SOPStep3Experience(BaseModel):
    work_experience: str
    internships: Optional[str] = ""
    projects: Optional[str] = ""
    technical_skills: str
    certifications: Optional[str] = ""
    research_experience: Optional[str] = ""

class SOPStep4Target(BaseModel):
    country: str
    university: str
    degree: str
    course: str
    intake: str

class SOPStep5Goals(BaseModel):
    short_term_goals: str
    long_term_goals: str
    reason_course: str
    reason_university: str
    reason_country: str
    career_aspirations: str

class SOPStep6Additional(BaseModel):
    extracurriculars: Optional[str] = ""
    leadership: Optional[str] = ""
    volunteer_work: Optional[str] = ""
    awards: Optional[str] = ""
    challenges: Optional[str] = ""
    hobbies: Optional[str] = ""
    notes: Optional[str] = ""

class SOPGenerateRequest(BaseModel):
    personal_info: SOPStep1Personal
    academic_background: SOPStep2Academic
    professional_experience: SOPStep3Experience
    target_education: SOPStep4Target
    career_goals: SOPStep5Goals
    additional_info: SOPStep6Additional


class SOPDocumentSave(BaseModel):
    title: str
    content: str


class SOPRewriteRequest(BaseModel):
    content: str  # The full document or highlighted text
    instruction: str  # e.g., "more_professional", "shorten", "improve_grammar", etc.
    selected_text: Optional[str] = None  # Optional highlighted paragraph to target


class SOPVersionResponse(BaseModel):
    id: str
    document_id: str
    version_number: int
    content: str
    changes: str
    created_at: datetime

    class Config:
        from_attributes = True


class SOPDocumentResponse(BaseModel):
    id: str
    user_id: Optional[str]
    title: str
    target_country: str
    target_university: str
    target_course: str
    content: str
    ai_model: str
    version: int
    created_at: datetime
    updated_at: datetime
    versions: Optional[List[SOPVersionResponse]] = None

    class Config:
        from_attributes = True


# VISA CHECKER SCHEMAS
class UploadedDocumentResponse(BaseModel):
    id: str
    check_id: str
    document_type: str
    filename: str
    content_type: str
    file_size: int
    file_path: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentAnalysisResponse(BaseModel):
    id: str
    check_id: str
    uploaded_document_id: Optional[str]
    document_name: str
    status: str  # Passed, Warning, Failed
    issues: List[str]
    suggestions: List[str]
    confidence_score: float
    critical: bool
    created_at: datetime

    class Config:
        from_attributes = True


class VisaCheckStart(BaseModel):
    country: str
    visa_type: str  # Student Visa, Work Visa, Visitor Visa


class VisaCheckResponse(BaseModel):
    id: str
    user_id: Optional[str]
    country: str
    visa_type: str
    readiness_score: int
    status: str
    ai_response: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    uploaded_documents: List[UploadedDocumentResponse] = []
    analyses: List[DocumentAnalysisResponse] = []

    class Config:
        from_attributes = True


# STUDENT DASHBOARD SCHEMAS
class NotificationResponse(BaseModel):
    id: str
    user_id: str
    type: str  # info, success, warning
    title: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AppointmentResponse(BaseModel):
    id: str
    user_id: str
    consultant_name: str
    date_time: datetime
    meeting_link: str
    status: str  # upcoming, completed, cancelled
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserSettingResponse(BaseModel):
    id: str
    email_notifications: bool
    sms_notifications: bool
    marketing_emails: bool
    privacy_profile_public: bool
    language: str

    class Config:
        from_attributes = True


class UserSettingUpdate(BaseModel):
    email_notifications: bool
    sms_notifications: bool
    marketing_emails: bool
    privacy_profile_public: bool
    language: str


class DashboardActivityResponse(BaseModel):
    id: str
    activity_type: str
    description: str
    created_at: datetime

    class Config:
        from_attributes = True


class StudentProfileResponse(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    country_residence: str
    nationality: str
    qualification: str
    preferred_country: str
    preferred_course: str
    preferred_intake: str


class StudentProfileUpdate(BaseModel):
    full_name: str
    phone: str
    country_residence: str
    nationality: str
    qualification: str
    preferred_country: str
    preferred_course: str
    preferred_intake: str


class DashboardOverviewResponse(BaseModel):
    profile_completeness: int
    purchased_services: List[str]
    recent_activities: List[DashboardActivityResponse]
    upcoming_appointments: List[AppointmentResponse]
    unread_notifications_count: int
    total_drafts_count: int
    total_payments_count: int


# UNIVERSITY MATCHER SCHEMAS
class UniversityResponse(BaseModel):
    id: str
    name: str
    country: str
    world_ranking: Optional[int]
    tuition_fee_range: str
    average_living_cost: str
    admission_rate: Optional[str]

    class Config:
        from_attributes = True


class UniversityProfileInput(BaseModel):
    nationality: str
    current_country: str
    highest_qualification: str
    gpa_percentage: float
    graduation_year: int
    english_exam: str
    english_score: float
    neet_score: Optional[int] = None
    preferred_countries: List[str]
    degree_level: str
    course: str
    budget: str
    preferred_intake: str
    scholarship_required: bool


class UniversityRecommendationSchema(BaseModel):
    match_percentage: int
    university_name: str
    country: str
    course: str
    tuition_fee: str
    living_cost: str
    scholarship_opportunities: str
    admission_requirements: str
    visa_difficulty: str
    employment_opportunities: str
    ai_recommendation_summary: str


class UniversityMatchResponse(BaseModel):
    id: str
    profile_data: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class SaveUniversityRequest(BaseModel):
    name: str
    country: str
    course: str
    tuition_fee: str
    match_percentage: int


class SavedUniversityResponse(BaseModel):
    id: str
    user_id: str
    name: str
    country: str
    course: str
    tuition_fee: str
    match_percentage: int
    created_at: datetime

    class Config:
        from_attributes = True


class ComparisonRequest(BaseModel):
    name: str
    data: List[Dict[str, Any]]


class ComparisonResponse(BaseModel):
    id: str
    user_id: str
    name: str
    data: List[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


# APPLICATION MANAGEMENT SYSTEM SCHEMAS
class ApplicationTaskResponse(BaseModel):
    id: str
    application_id: str
    title: str
    status: str
    due_date: Optional[str] = None
    priority: str
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ApplicationDocumentResponse(BaseModel):
    id: str
    application_id: str
    document_name: str
    status: str
    file_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ApplicationNoteResponse(BaseModel):
    id: str
    application_id: str
    title: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ApplicationTimelineResponse(BaseModel):
    id: str
    application_id: str
    event_title: str
    event_description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ApplicationCalendarResponse(BaseModel):
    id: str
    application_id: Optional[str] = None
    event_title: str
    event_type: str
    event_date: str
    created_at: datetime

    class Config:
        from_attributes = True


class ApplicationResponse(BaseModel):
    id: str
    user_id: str
    university: str
    country: str
    course: str
    degree: str
    intake: str
    tuition_fee: Optional[str] = None
    application_fee: Optional[str] = None
    deadline: Optional[str] = None
    current_status: str
    priority: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    tasks: List[ApplicationTaskResponse] = []
    documents: List[ApplicationDocumentResponse] = []
    notes_list: List[ApplicationNoteResponse] = []
    timeline: List[ApplicationTimelineResponse] = []
    calendar_items: List[ApplicationCalendarResponse] = []

    class Config:
        from_attributes = True


class ApplicationCreate(BaseModel):
    university: str
    country: str
    course: str
    degree: str
    intake: str
    tuition_fee: Optional[str] = None
    application_fee: Optional[str] = None
    deadline: Optional[str] = None
    current_status: Optional[str] = "Interested"
    priority: Optional[str] = "Medium"
    notes: Optional[str] = None


class ApplicationUpdate(BaseModel):
    university: Optional[str] = None
    country: Optional[str] = None
    course: Optional[str] = None
    degree: Optional[str] = None
    intake: Optional[str] = None
    tuition_fee: Optional[str] = None
    application_fee: Optional[str] = None
    deadline: Optional[str] = None
    current_status: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = None


class TaskCreate(BaseModel):
    application_id: str
    title: str
    due_date: Optional[str] = None
    priority: Optional[str] = "Medium"
    notes: Optional[str] = None


class DocumentCreate(BaseModel):
    application_id: str
    document_name: str
    status: Optional[str] = "Pending"
    file_path: Optional[str] = None


class NoteCreate(BaseModel):
    application_id: str
    title: str
    content: str


# VISA SUCCESS CENTER SCHEMAS
class VisaProfileResponse(BaseModel):
    id: str
    user_id: str
    country: str
    visa_type: str
    current_stage: str
    created_at: datetime

    class Config:
        from_attributes = True


class VisaReadinessRequest(BaseModel):
    country: str
    academic_readiness: int
    financial_readiness: int
    document_readiness: int
    travel_readiness: int
    interview_readiness: int


class VisaReadinessResponse(BaseModel):
    id: str
    profile_id: str
    overall_score: int
    risk_level: str
    critical_issues: List[str]
    suggested_improvements: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


class VisaChecklistResponse(BaseModel):
    id: str
    profile_id: str
    item_name: str
    status: str
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class VisaTaskResponse(BaseModel):
    id: str
    profile_id: str
    title: str
    due_date: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class VisaInterviewQuestionSchema(BaseModel):
    question: str
    answer: str
    feedback: str
    score: int
    rating: str
    suggestions: str


class VisaInterviewResponse(BaseModel):
    id: str
    profile_id: str
    questions: List[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class VisaInterviewRequest(BaseModel):
    country: str
    question: str
    student_answer: str


class VisaFinancialRequest(BaseModel):
    country: str
    tuition_fee: float
    living_expenses: float
    scholarship_amount: float
    education_loan: float
    savings: float


class VisaFinancialResponse(BaseModel):
    id: str
    profile_id: str
    tuition_fee: float
    living_expenses: float
    scholarship_amount: float
    education_loan: float
    savings: float
    required_funds: float
    available_funds: float
    funding_gap: float
    readiness_score: int
    created_at: datetime

    class Config:
        from_attributes = True


class VisaTimelineItemResponse(BaseModel):
    id: str
    profile_id: str
    event_title: str
    event_date: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class VisaRecommendationResponse(BaseModel):
    id: str
    profile_id: str
    title: str
    message: str
    actionable: bool
    created_at: datetime

    class Config:
        from_attributes = True


class VisaDashboardResponse(BaseModel):
    profile: VisaProfileResponse
    readiness: Optional[VisaReadinessResponse] = None
    checklist: List[VisaChecklistResponse] = []
    tasks: List[VisaTaskResponse] = []
    financial: Optional[VisaFinancialResponse] = None
    timeline: List[VisaTimelineItemResponse] = []
    recommendations: List[VisaRecommendationResponse] = []


# SCHOLARSHIP FINDER SCHEMAS
class ScholarshipResponse(BaseModel):
    id: str
    name: str
    provider: str
    country: str
    university: Optional[str] = None
    funding_amount: str
    coverage: str
    eligibility_criteria: str
    difficulty_level: str
    deadline: Optional[str] = None
    website_placeholder: str
    created_at: datetime

    class Config:
        from_attributes = True


class ScholarshipProfileInput(BaseModel):
    # Personal Information
    nationality: str
    country_residence: str
    annual_family_income: str

    # Academic Information
    highest_qualification: str
    gpa_percentage: float
    english_exam: str
    english_score: float
    work_experience: float
    research_experience: bool
    publications: bool
    volunteer_work: bool
    leadership_experience: bool

    # Study Preferences
    preferred_countries: List[str]
    preferred_universities: List[str]
    course: str
    degree_level: str
    intake: str

    # Financial Information
    budget: float
    savings: float
    education_loan: float
    sponsor_support: float
    existing_scholarships: float


class ScholarshipMatchResponse(BaseModel):
    id: str
    user_id: str
    profile_data: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class SavedScholarshipResponse(BaseModel):
    id: str
    user_id: str
    scholarship_id: Optional[str] = None
    name: str
    provider: str
    country: str
    funding_amount: str
    match_percentage: int
    deadline: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FundingPlannerRequest(BaseModel):
    tuition_fee: float
    living_cost: float
    travel_cost: float
    visa_cost: float
    insurance: float
    misc_expenses: float
    scholarship_amount: float
    loan_amount: float
    savings: float


class FundingPlannerResponse(BaseModel):
    id: str
    user_id: str
    tuition_fee: float
    living_cost: float
    travel_cost: float
    visa_cost: float
    insurance: float
    misc_expenses: float
    scholarship_amount: float
    loan_amount: float
    savings: float
    funding_gap: float
    total_cost: float
    total_available: float
    readiness_score: int
    suggested_plan: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ScholarshipDeadlineResponse(BaseModel):
    id: str
    user_id: str
    event_title: str
    event_type: str
    event_date: str
    created_at: datetime

    class Config:
        from_attributes = True


# WHATSAPP AUTO NOTIFICATION SCHEMAS
class WhatsAppNotificationResponse(BaseModel):
    id: str
    user_id: str
    event_type: str
    phone_number: str
    template_name: str
    message: str
    status: str
    retry_count: int
    provider_message_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationTemplateResponse(BaseModel):
    id: str
    name: str
    event: str
    template: str
    active: bool

    class Config:
        from_attributes = True


class NotificationTemplateUpdate(BaseModel):
    template: str
    active: bool


class NotificationPreferenceResponse(BaseModel):
    id: str
    user_id: str
    enable_whatsapp: bool
    categories: List[str]

    class Config:
        from_attributes = True


class NotificationPreferenceUpdate(BaseModel):
    enable_whatsapp: bool
    categories: List[str]








