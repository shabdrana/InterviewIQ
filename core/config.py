"""Central configuration. Values come from environment variables / .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

APP_NAME = "InterviewIQ"


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def db_path() -> Path:
    p = Path(env("DATABASE_PATH", "data/interviewiq.db"))
    return p if p.is_absolute() else BASE_DIR / p


def mentor_code() -> str:
    return env("MENTOR_ACCESS_CODE", "change-me")


INTERVIEW_TYPES = ["HR", "Technical", "Behavioral", "General"]
DIFFICULTIES = ["Beginner", "Intermediate", "Advanced"]
EXPERIENCE_LEVELS = ["Fresher", "Experienced"]
DOMAINS = ["Python", "C++", "Java", "SQL", "DSA", "AI/ML"]
