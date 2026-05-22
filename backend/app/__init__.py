import os
from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from celery import Celery
from config import Config

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend_dist")

db = SQLAlchemy()
migrate = Migrate()
celery = Celery()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)

    celery.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
        beat_schedule={
            "poll-qbittorrent": {
                "task": "app.tasks.poll_qbittorrent",
                "schedule": app.config["POLL_INTERVAL_SECONDS"],
            }
        },
    )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    from app.routes.imports import imports_bp
    from app.routes.config import config_bp

    app.register_blueprint(imports_bp, url_prefix="/api/imports")
    app.register_blueprint(config_bp, url_prefix="/api/config")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        dist = os.path.realpath(FRONTEND_DIST)
        target = os.path.realpath(os.path.join(dist, path))
        if path and target.startswith(dist) and os.path.isfile(target):
            return send_from_directory(dist, path)
        return send_from_directory(dist, "index.html")

    return app
