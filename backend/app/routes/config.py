from flask import Blueprint, jsonify, current_app

config_bp = Blueprint("config", __name__)


@config_bp.get("/")
def get_config():
    git_sha = current_app.config["GIT_SHA"]
    return jsonify({
        "confidence_threshold": current_app.config["CONFIDENCE_THRESHOLD"],
        "poll_interval_seconds": current_app.config["POLL_INTERVAL_SECONDS"],
        "version": git_sha[:7] if git_sha != "dev" else "dev",
    })
