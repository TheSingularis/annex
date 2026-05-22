from flask import Blueprint, jsonify, current_app

config_bp = Blueprint("config", __name__)


@config_bp.get("/")
def get_config():
    return jsonify({
        "confidence_threshold": current_app.config["CONFIDENCE_THRESHOLD"],
        "poll_interval_seconds": current_app.config["POLL_INTERVAL_SECONDS"],
    })
