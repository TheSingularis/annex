"""
Idempotent ALTER TABLE for columns db.create_all() can't add to an existing
table (it only creates missing tables, never alters existing ones). Separate
from app.app_settings on purpose -- that module migrates settings.json, not
table schema.

SQLite-specific (PRAGMA table_info) by design, matching the existing
hand-rolled, no-abstraction precedent in app_settings.py -- not building
generic multi-DB migration tooling for one column pair. See
/root/.claude/plans/jolly-greeting-karp.md (Phase 4a).
"""
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app import db

# Columns to add to the imports table if missing. (table, column) -> SQL type.
_PENDING_COLUMNS = [
    ("imports", "isbn", "TEXT"),
    ("imports", "asin", "TEXT"),
]


def migrate_schema():
    """Safe under concurrent boot -- two gunicorn workers both import run.py
    and call this around the same time. A losing racer's duplicate-column
    error is swallowed, not raised; config.py's connect_args timeout (30s)
    handles simple lock contention before either side ever sees an error."""
    with db.engine.begin() as conn:
        for table, column, col_type in _PENDING_COLUMNS:
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            if column in existing:
                continue
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            except OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise
