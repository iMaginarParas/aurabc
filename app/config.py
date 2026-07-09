import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./aura.db"
    openai_api_key: str = ""
    cors_origins: str = "http://localhost:3000"
    supabase_url: str = ""

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8", 
        extra="ignore"
    )

settings = Settings()
