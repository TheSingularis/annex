from app import db
from app.models import Import, ShadowMatch


def _make_import():
    record = Import(name="Dune", category="ebook", content_path="/tmp/x", status="needs_review")
    db.session.add(record)
    db.session.commit()
    return record


def test_shadow_match_summary_empty(db_app):
    resp = db_app.test_client().get("/api/imports/shadow-matches")
    assert resp.status_code == 200
    assert resp.get_json() == {"total": 0, "agree": 0, "disagree": 0, "errors": 0, "matches": []}


def test_shadow_match_summary_counts(db_app):
    record = _make_import()
    db.session.add(ShadowMatch(import_id=record.id, agrees=True))
    db.session.add(ShadowMatch(import_id=record.id, agrees=False))
    db.session.add(ShadowMatch(import_id=record.id, error="api exploded"))
    db.session.commit()

    resp = db_app.test_client().get("/api/imports/shadow-matches")
    data = resp.get_json()

    assert data["total"] == 3
    assert data["agree"] == 1
    assert data["disagree"] == 1
    assert data["errors"] == 1
    assert len(data["matches"]) == 3
