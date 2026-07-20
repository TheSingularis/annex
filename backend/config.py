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
    # Multiple processes (gunicorn x2, celery worker x2, beat) share one
    # sqlite file; the sqlite3 default 5s lock-wait is too short for bursts
    # of concurrent commits (e.g. a scan discovering hundreds of new files).
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 30}}

    CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    AUDIOBOOK_WATCH_PATH = os.environ.get("AUDIOBOOK_WATCH_PATH", "")
    EBOOK_WATCH_PATH = os.environ.get("EBOOK_WATCH_PATH", "")

    AUDIOBOOK_LIBRARY_PATH = os.environ.get("AUDIOBOOK_LIBRARY_PATH", "/mnt/library/audiobooks")
    EBOOK_LIBRARY_PATH = os.environ.get("EBOOK_LIBRARY_PATH", "/mnt/library/ebooks")

    CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", 0.85))
    POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", 60))

    # Phase 4a shadow-mode toggle -- see /root/.claude/plans/jolly-greeting-karp.md.
    # Redeploy-to-toggle is acceptable for a temporary observation-window instrument.
    SHADOW_MATCHER_ENABLED = os.environ.get("SHADOW_MATCHER_ENABLED", "true").lower() == "true"

    GIT_SHA = os.environ.get("GIT_SHA", "dev")

    # Optional — enables ComicVine as a metadata source for western comics.
    # Manga matching (AniList) needs no key and is always active.
    COMICVINE_API_KEY = os.environ.get("COMICVINE_API_KEY", "")

    AUDIOBOOK_EXTENSIONS = {".m4b", ".mp3", ".flac", ".ogg", ".opus", ".aac"}
    # Comic/manga archive formats — matched via ComicVine/AniList instead of
    # OpenLibrary/Google Books (see metadata.py).
    COMIC_EXTENSIONS = {".cbz", ".cbr", ".cb7", ".cbt"}
    EBOOK_EXTENSIONS = {".epub", ".mobi", ".pdf", ".azw3"} | COMIC_EXTENSIONS
