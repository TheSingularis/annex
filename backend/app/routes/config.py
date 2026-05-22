from flask import Blueprint, jsonify, current_app
from app.abs import ABSClient

config_bp = Blueprint("config", __name__)


@config_bp.get("/status")
def get_status():
    abs_status = ABSClient().check_connection()
    return jsonify({"abs": abs_status})


@config_bp.get("/")
def get_config():
    return jsonify({
        "audiobook_watch_path": current_app.config["AUDIOBOOK_WATCH_PATH"],
        "ebook_watch_path": current_app.config["EBOOK_WATCH_PATH"],
        "abs_host": current_app.config["ABS_HOST"],
        "audiobook_library_path": current_app.config["AUDIOBOOK_LIBRARY_PATH"],
        "ebook_library_path": current_app.config["EBOOK_LIBRARY_PATH"],
        "confidence_threshold": current_app.config["CONFIDENCE_THRESHOLD"],
        "poll_interval_seconds": current_app.config["POLL_INTERVAL_SECONDS"],
    })
