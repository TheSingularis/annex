from sqlalchemy import text

from app import db
from app.db_migrations import migrate_schema


def _reset_imports_table_to_pre_phase4_schema():
    """db_app's db.create_all() builds the imports table from the *current*
    Import model, which already declares isbn/asin -- so it doesn't
    reproduce the pre-migration state migrate_schema() is meant to handle.
    Rebuild a minimal old-shape table by hand instead."""
    with db.engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS imports"))
        conn.execute(text(
            "CREATE TABLE imports ("
            "id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, "
            "content_path TEXT NOT NULL, status TEXT NOT NULL)"
        ))


def _imports_columns() -> set:
    with db.engine.begin() as conn:
        return {row[1] for row in conn.execute(text("PRAGMA table_info(imports)"))}


def test_migrate_schema_adds_missing_columns(db_app):
    _reset_imports_table_to_pre_phase4_schema()
    assert "isbn" not in _imports_columns()

    migrate_schema()

    cols = _imports_columns()
    assert "isbn" in cols
    assert "asin" in cols


def test_migrate_schema_is_idempotent(db_app):
    _reset_imports_table_to_pre_phase4_schema()

    migrate_schema()
    migrate_schema()  # must not raise on a second run

    cols = _imports_columns()
    assert "isbn" in cols
    assert "asin" in cols


def test_migrate_schema_handles_column_already_added_by_a_racing_process(db_app):
    """Simulates a losing racer in the 2x-gunicorn-worker boot race: one
    column already landed before this call runs. The loop must still add
    the other column without raising."""
    _reset_imports_table_to_pre_phase4_schema()
    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE imports ADD COLUMN isbn TEXT"))

    migrate_schema()

    cols = _imports_columns()
    assert "isbn" in cols
    assert "asin" in cols
