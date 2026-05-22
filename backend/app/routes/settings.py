from flask import Blueprint, request, jsonify
from app.app_settings import load, save
from app.abs import ABSClient

settings_bp = Blueprint("settings", __name__)


@settings_bp.get("/")
def get_settings():
    return jsonify(load())


@settings_bp.put("/")
def update_settings():
    data = request.get_json(force=True)
    return jsonify(save(data))


@settings_bp.get("/status")
def get_status():
    return jsonify({"abs": ABSClient().check_connection()})
