import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./events.db")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
COLLECTION_INTERVAL_MINUTES = int(os.getenv("COLLECTION_INTERVAL_MINUTES", "60"))
DISASTER_INTERVAL_MINUTES = int(os.getenv("DISASTER_INTERVAL_MINUTES", "15"))
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")
LLM_BATCH_SIZE = int(os.getenv("LLM_BATCH_SIZE", "5"))
CALENDARIFIC_API_KEY = os.getenv("CALENDARIFIC_API_KEY", "")
