import json
import os

CONFIG_PATH = "/app/data/settings.json"

ABS_KEYS = ["abs_host", "abs_api_key", "abs_audiobook_library_id", "abs_ebook_library_id"]
PATH_KEYS = ["audiobook_watch_path", "ebook_watch_path", "audiobook_library_path", "ebook_library_path"]
ALL_KEYS = ABS_KEYS + PATH_KEYS


def _env_defaults() -> dict:
    return {
        "audiobook_watch_path": os.environ.get("AUDIOBOOK_WATCH_PATH", ""),
        "ebook_watch_path": os.environ.get("EBOOK_WATCH_PATH", ""),
        "audiobook_library_path": os.environ.get("AUDIOBOOK_LIBRARY_PATH", ""),
        "ebook_library_path": os.environ.get("EBOOK_LIBRARY_PATH", ""),
    }


def load() -> dict:
    defaults = _env_defaults()
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
            return {k: data.get(k, defaults.get(k, "")) for k in ALL_KEYS}
    except (FileNotFoundError, json.JSONDecodeError):
        return {k: defaults.get(k, "") for k in ALL_KEYS}


def save(updates: dict) -> dict:
    current = load()
    for k in ALL_KEYS:
        if k in updates:
            current[k] = str(updates[k]).strip()
    with open(CONFIG_PATH, "w") as f:
        json.dump(current, f, indent=2)
    return current


def migrate_from_db():
    """Migrate to settings.json — checks old abs_config.json first, then DB."""
    if os.path.exists(CONFIG_PATH):
        return
    # Migrate from old abs_config.json
    old_path = os.path.join(os.path.dirname(CONFIG_PATH), "abs_config.json")
    if os.path.exists(old_path):
        try:
            with open(old_path) as f:
                data = json.load(f)
            with open(CONFIG_PATH, "w") as f:
                json.dump(data, f, indent=2)
            return
        except Exception:
            pass
    # Migrate from DB
    try:
        from app.models import AppSettings
        cfg = AppSettings.get_abs_config()
        if any(cfg.values()):
            with open(CONFIG_PATH, "w") as f:
                json.dump(cfg, f, indent=2)
    except Exception:
        pass
