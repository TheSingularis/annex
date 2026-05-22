import json
import os

CONFIG_PATH = "/app/data/abs_config.json"
ABS_KEYS = ["abs_host", "abs_api_key", "abs_audiobook_library_id", "abs_ebook_library_id"]


def load() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
            return {k: data.get(k, "") for k in ABS_KEYS}
    except (FileNotFoundError, json.JSONDecodeError):
        return {k: "" for k in ABS_KEYS}


def save(updates: dict) -> dict:
    current = load()
    for k in ABS_KEYS:
        if k in updates:
            current[k] = str(updates[k]).strip()
    with open(CONFIG_PATH, "w") as f:
        json.dump(current, f, indent=2)
    return current


def migrate_from_db():
    """One-time: copy ABS config from AppSettings DB to file if file absent."""
    if os.path.exists(CONFIG_PATH):
        return
    try:
        from app.models import AppSettings
        cfg = AppSettings.get_abs_config()
        if any(cfg.values()):
            with open(CONFIG_PATH, "w") as f:
                json.dump(cfg, f, indent=2)
    except Exception:
        pass
