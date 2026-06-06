import os
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Google Gemini API
    GEMINI_API_KEY: str

    # Email SMTP (Gmail)
    SMTP_EMAIL: str
    SMTP_PASSWORD: str
    NOTIFICATION_EMAIL: str

    # Job Search Settings
    SEARCH_LOCATION: str = "Remote"
    SEARCH_COUNTRY: str = "USA"
    MIN_MATCH_SCORE: int = 75
    RESULTS_PER_SEARCH: int = 25

    # Database
    DATABASE_URL: str

    # Optional paths
    RESUME_PATH: str = "/opt/airflow/resume/curriculo.pdf"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate settings
try:
    settings = Settings()
except Exception as e:
    # Fallback to loading from env directly or environment variables inside Airflow container
    class AirflowSettings(BaseSettings):
        GEMINI_API_KEY: str = Field(default=os.getenv("GEMINI_API_KEY", ""))
        SMTP_EMAIL: str = Field(default=os.getenv("SMTP_EMAIL", ""))
        SMTP_PASSWORD: str = Field(default=os.getenv("SMTP_PASSWORD", ""))
        NOTIFICATION_EMAIL: str = Field(default=os.getenv("NOTIFICATION_EMAIL", ""))
        SEARCH_LOCATION: str = Field(default=os.getenv("SEARCH_LOCATION", "Remote"))
        SEARCH_COUNTRY: str = Field(default=os.getenv("SEARCH_COUNTRY", "USA"))
        MIN_MATCH_SCORE: int = Field(default=int(os.getenv("MIN_MATCH_SCORE", "75")))
        RESULTS_PER_SEARCH: int = Field(default=int(os.getenv("RESULTS_PER_SEARCH", "25")))
        DATABASE_URL: str = Field(default=os.getenv("DATABASE_URL", ""))
        RESUME_PATH: str = Field(default=os.getenv("RESUME_PATH", "/opt/airflow/resume/curriculo.pdf"))
        
        model_config = SettingsConfigDict(extra="ignore")
    settings = AirflowSettings()
