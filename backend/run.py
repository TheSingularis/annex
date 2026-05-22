import os
import shutil
from app import create_app, db

DATA_DIR = "/app/data"
ENV_FILE = os.path.join(DATA_DIR, ".env")
ENV_EXAMPLE = os.path.join(os.path.dirname(__file__), ".env.example")


def init_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(ENV_FILE) and os.path.exists(ENV_EXAMPLE):
        shutil.copy(ENV_EXAMPLE, ENV_FILE)


init_data_dir()

app = create_app()

# Always run on startup regardless of how the app is launched (gunicorn or direct)
with app.app_context():
    db.create_all()
    from app.app_settings import migrate_from_db
    migrate_from_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
