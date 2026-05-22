from flask import Blueprint, jsonify, current_app

config_bp = Blueprint("config", __name__)


@config_bp.get("/")
def get_config():
    """Return non-sensitive config values for the UI."""
    return jsonify({
        "qbit_host": current_app.config["QBIT_HOST"],
        "qbit_port": current_app.config["QBIT_PORT"],
        "abs_host": current_app.config["ABS_HOST"],
        "audiobook_library_path": current_app.config["AUDIOBOOK_LIBRARY_PATH"],
        "ebook_library_path": current_app.config["EBOOK_LIBRARY_PATH"],
        "confidence_threshold": current_app.config["CONFIDENCE_THRESHOLD"],
        "poll_interval_seconds": current_app.config["POLL_INTERVAL_SECONDS"],
    })
