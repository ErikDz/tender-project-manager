import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (two levels up from backend/app/)
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret")
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # Supabase
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "http://localhost:54321")
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    # LLM
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
    LLM_MODEL = os.environ.get("LLM_MODEL", "google/gemini-3-flash-preview")

    # File storage
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./uploads")
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max upload

    # CORS
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
