import json

from app import db
from app.models import Import


def _make_imported_record(**overrides):
    defaults = dict(
        name="The Beast by Jenika Snow.epub", category="ebook", content_path="/tmp/x",
        status="imported", resolved_author="Robert Lawrence Stine", resolved_title="The Beast",
        resolved_series="", resolved_series_seq="",
        target_path="/library/Ebooks/AnnexLibrary/Robert Lawrence Stine/The Beast",
        metadata_confidence=1.0, candidates_json='[{"title": "The Beast"}]',
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


def test_reset_import_clears_stale_confidence_and_candidates(db_app):
    # Regression: a record read between reset and its next retry completing
    # previously showed the old (wrong) confidence/candidates until the
    # retry overwrote them, which looked like a live inconsistency bug
    # during triage but was just these fields not being cleared on reset.
    record = _make_imported_record()

    resp = db_app.test_client().post(f"/api/imports/{record.id}/reset")
    data = resp.get_json()

    assert data["metadata_confidence"] is None
    assert data["candidates_json"] is None


def test_reset_import_rejects_non_imported_status(db_app):
    record = _make_imported_record(status="needs_review", target_path=None,
                                    resolved_author=None, resolved_title=None)

    resp = db_app.test_client().post(f"/api/imports/{record.id}/reset")

    assert resp.status_code == 400
    assert Import.query.get(record.id).status == "needs_review"


def test_reset_import_deletes_tracked_files_and_prunes_empty_dir(db_app, tmp_path):
    target_dir = tmp_path / "Robert Lawrence Stine" / "The Beast"
    target_dir.mkdir(parents=True)
    linked_file = target_dir / "The Beast.epub"
    linked_file.write_text("content")
    record = _make_imported_record(
        target_path=str(target_dir),
        linked_files_json=json.dumps([str(linked_file)]),
    )

    resp = db_app.test_client().post(f"/api/imports/{record.id}/reset")
    data = resp.get_json()

    assert resp.status_code == 200
    assert data["linked_files_json"] is None
    assert not linked_file.exists()
    assert not target_dir.exists()


def test_reset_import_does_not_delete_unrelated_content_in_shared_dir(db_app, tmp_path):
    target_dir = tmp_path / "Robert Lawrence Stine" / "The Beast"
    target_dir.mkdir(parents=True)
    linked_file = target_dir / "The Beast.epub"
    linked_file.write_text("content")
    (target_dir / "cover.jpg").write_text("scanner-generated, not tracked")
    record = _make_imported_record(
        target_path=str(target_dir),
        linked_files_json=json.dumps([str(linked_file)]),
    )

    db_app.test_client().post(f"/api/imports/{record.id}/reset")

    assert not linked_file.exists()
    assert target_dir.exists()
    assert (target_dir / "cover.jpg").exists()


def test_reset_import_without_linked_files_json_still_resets_db_only(db_app):
    # Legacy records imported before linked_files_json existed have nothing
    # to clean up on disk -- reset must still succeed (DB-only, as before).
    record = _make_imported_record(linked_files_json=None)

    resp = db_app.test_client().post(f"/api/imports/{record.id}/reset")

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "needs_review"
