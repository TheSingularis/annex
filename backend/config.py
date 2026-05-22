import os
from dotenv import load_dotenv

# Load from appdata first (persists across container updates on Unraid),
# then fall back to a local .env for development.
load_dotenv("/app/data/.env")
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:////app/data/annex.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    AUDIOBOOK_WATCH_PATH = os.environ.get("AUDIOBOOK_WATCH_PATH", "")
    EBOOK_WATCH_PATH = os.environ.get("EBOOK_WATCH_PATH", "")

    ABS_HOST = os.environ.get("ABS_HOST", "http://localhost:13378")
    ABS_API_KEY = os.environ.get("ABS_API_KEY", "")
    ABS_AUDIOBOOK_LIBRARY_ID = os.environ.get("ABS_AUDIOBOOK_LIBRARY_ID", "")
    ABS_EBOOK_LIBRARY_ID = os.environ.get("ABS_EBOOK_LIBRARY_ID", "")

    AUDIOBOOK_LIBRARY_PATH = os.environ.get("AUDIOBOOK_LIBRARY_PATH", "/mnt/library/audiobooks")
    EBOOK_LIBRARY_PATH = os.environ.get("EBOOK_LIBRARY_PATH", "/mnt/library/ebooks")

    CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", 0.85))
    POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", 60))

    AUDIOBOOK_EXTENSIONS = {".m4b", ".mp3", ".flac", ".ogg", ".opus", ".aac"}
    EBOOK_EXTENSIONS = {".epub", ".mobi", ".pdf", ".azw3"}
