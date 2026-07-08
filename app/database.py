from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import settings

# If DATABASE_URL starts with "postgres://", replace with "postgresql://" for SQLAlchemy compatibility
db_url = settings.database_url
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# SQLite config override to support thread checking if using local fallback database
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine = create_engine(db_url, connect_args=connect_args)
else:
    engine = create_engine(
        db_url,
        pool_size=10,       # Supabase Nano hard limit: 15 connections total
        max_overflow=4,     # Burst headroom — total ceiling = 14 (safe under 15)
        pool_recycle=1800,  # Recycle connections every 30 min
        pool_pre_ping=True  # Verify connection alive before using from pool
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
