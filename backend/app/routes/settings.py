from flask import Blueprint, request, jsonify
from app import db
from app.models import AppSettings
from app.abs import ABSClient

settings_bp = Blueprint("settings", __name__)

ABS_KEYS = ["abs_host", "abs_api_key", "abs_audiobook_library_id", "abs_ebook_library_id"]


@settings_bp.get("/")
def get_settings():
    return jsonify({k: AppSettings.get(k) for k in ABS_KEYS})


@settings_bp.put("/")
def update_settings():
    data = request.get_json(force=True)
    for key in ABS_KEYS:
        if key in data:
            AppSettings.set(key, data[key].strip())
    return jsonify({k: AppSettings.get(k) for k in ABS_KEYS})


@settings_bp.get("/status")
def get_status():
    return jsonify({"abs": ABSClient().check_connection()})
