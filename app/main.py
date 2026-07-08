import logging
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import engine, Base, SessionLocal
from .api.endpoints import router as eligibility_router
from .api.payments import router as payments_router
from .api.sop import router as sop_router
from .api.visa_checker import router as visa_checker_router
from .api.dashboard import router as dashboard_router
from .api.chat import router as chat_router
from .api.university_matcher import router as university_matcher_router
from .api.applications import router as applications_router
from .api.visa_success import router as visa_success_router
from .api.scholarships import router as scholarships_router
from .api.notifications import router as notifications_router
from .api.journey import router as journey_router
from .api.explorer import router as explorer_router
from .api.knowledge import router as knowledge_router
from .api.communication import router as communication_router
from .api.profile import router as profile_router
from .services.payment_service import seed_initial_services, seed_dashboard_defaults, seed_universities, seed_applications, seed_scholarships, seed_whatsapp_defaults
from .services.explorer_service import seed_explorer_data
from .services.knowledge_service import seed_knowledge_data
from .services.communication_service import seed_communication_data

# Configure Logger logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables automatically if they do not exist
try:
    logger.info("Initializing database schemas...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully.")
    
    # Trigger seeder
    db = SessionLocal()
    try:
        seed_initial_services(db)
        seed_dashboard_defaults(db)
        seed_universities(db)
        seed_applications(db)
        seed_scholarships(db)
        seed_whatsapp_defaults(db)
        seed_explorer_data(db)
        seed_knowledge_data(db)
        seed_communication_data(db)
    finally:
        db.close()
except Exception as e:
    logger.error(f"Failed to initialize database tables or seed services: {str(e)}")

app = FastAPI(
    title="Aura Routes AI Engine",
    description="FastAPI Backend for Aura Routes AI Eligibility Checker & Service Payments",
    version="1.0.0"
)

# Parse CORS Origins lists
origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add secure HTTP response headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https:;"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

# Enforce unified global unhandled exception formatting
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled system exception: {str(exc)}", exc_info=True)
    app_env = os.getenv("APP_ENV", "production").lower()
    
    # Hide details in production to safeguard database/schema structure
    err_detail = "An internal server error occurred. Support has been notified."
    if app_env == "development":
        err_detail = str(exc)
        
    return JSONResponse(
        status_code=500,
        content={"detail": err_detail}
    )

# Register routes
app.include_router(eligibility_router)
app.include_router(payments_router)
app.include_router(sop_router)
app.include_router(visa_checker_router)
app.include_router(dashboard_router)
app.include_router(chat_router)
app.include_router(university_matcher_router)
app.include_router(applications_router)
app.include_router(visa_success_router)
app.include_router(scholarships_router)
app.include_router(notifications_router)
app.include_router(journey_router)
app.include_router(explorer_router)
app.include_router(knowledge_router)
app.include_router(communication_router)
app.include_router(profile_router)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "Aura AI Engine"}
