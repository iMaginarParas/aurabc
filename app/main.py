import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import engine, Base, SessionLocal
from .api.endpoints import router as eligibility_router
from .api.payments import router as payments_router
from .api.sop import router as sop_router
from .api.visa_checker import router as visa_checker_router
from .api.dashboard import router as dashboard_router
from .api.university_matcher import router as university_matcher_router
from .api.applications import router as applications_router
from .api.visa_success import router as visa_success_router
from .api.scholarships import router as scholarships_router
from .api.notifications import router as notifications_router
from .services.payment_service import seed_initial_services, seed_dashboard_defaults, seed_universities, seed_applications, seed_scholarships, seed_whatsapp_defaults

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

# Register routes
app.include_router(eligibility_router)
app.include_router(payments_router)
app.include_router(sop_router)
app.include_router(visa_checker_router)
app.include_router(dashboard_router)
app.include_router(university_matcher_router)
app.include_router(applications_router)
app.include_router(visa_success_router)
app.include_router(scholarships_router)
app.include_router(notifications_router)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "Aura AI Engine"}
