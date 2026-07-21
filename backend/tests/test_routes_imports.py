from app import db
from app.models import Import


def _make_imported_record(**overrides):
    defaults = dict(
        name="The Beast by Jenika Snow.epub", category="ebook", content_path="/tmp/x",
        status="imported", resolved_author="Robert Lawrence Stine", resolved_title="The Beast",
        resolved_series="", resolved_series_seq="",
        target_path="/library/Ebooks/AnnexLibrary/Robert Lawrence Stine/The Beast",
    )
    defaults.update(overrides)
    record = Import(**defaults)
    db.session.add(record)
    db.session.commit()
    return record


def test_reset_import_reverts_wrong_imported_record_to_needs_review(db_app):
    record = _make_imported_record()

    resp = db_app.test_client().post(f"/api/imports/{record.id}/reset")
    data = resp.get_json()

    assert resp.status_code == 200
    assert data["status"] == "needs_review"
    assert data["resolved_author"] is None
    assert data["resolved_title"] is None
    assert data["target_path"] is None


def test_reset_import_rejects_non_imported_status(db_app):
    record = _make_imported_record(status="needs_review", target_path=None,
                                    resolved_author=None, resolved_title=None)

    resp = db_app.test_client().post(f"/api/imports/{record.id}/reset")

    assert resp.status_code == 400
    assert Import.query.get(record.id).status == "needs_review"
