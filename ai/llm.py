import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Load .env from project root (parent of ai/)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

openai_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    timeout=120.0  # 2 minute timeout for API calls
)

LLM_MODEL = os.environ.get("LLM_MODEL", "google/gemini-3-flash-preview")
