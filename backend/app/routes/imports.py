import json
from pathlib import Path
from flask import Blueprint, request, jsonify
from app import db
from app.models import Import
from app.tasks import import_item, _finalize_import
from app.metadata import resolve_metadata
from app.fileops import discover_files

imports_bp = Blueprint("imports", __name__)


@imports_bp.get("/")
def list_imports():
    status = request.args.get("status")
    query = Import.query.order_by(Import.created_at.desc())
    if status:
        query = query.filter_by(status=status)
    return jsonify([i.to_dict() for i in query.all()])


@imports_bp.get("/<int:import_id>")
def get_import(import_id):
    record = Import.query.get_or_404(import_id)
    return jsonify(record.to_dict())


@imports_bp.post("/scan")
def trigger_scan():
    from app.tasks import scan_watch_dirs
    scan_watch_dirs.delay()
    return jsonify({"status": "scan queued"})


@imports_bp.post("/manual")
def manual_import():
    data = request.get_json(force=True)
    path = data.get("path", "").strip()
    category = data.get("category", "").lower()
    author = data.get("author", "").strip()
    title = data.get("title", "").strip()

    if not path or category not in ("audiobook", "ebook"):
        return jsonify({"error": "path and category (audiobook|ebook) are required"}), 400

    if not Path(path).exists():
        return jsonify({"error": f"Path does not exist: {path}"}), 400

    name = title or Path(path).name
    record = Import(
        hash=None,
        name=name,
        category=category,
        content_path=path,
        status="pending",
    )
    db.session.add(record)
    db.session.commit()

    if author and title:
        files = discover_files(path, category)
        if not files:
            record.status = "failed"
            record.error_message = "No matching files found at path"
            db.session.commit()
            return jsonify({"error": record.error_message}), 400

        # Still query APIs to pick up series data
        meta = resolve_metadata(f"{author} {title}", category)
        top = meta["candidates"][0] if meta["candidates"] else {}
        match = {
            "author": author,
            "title": title,
            "series": top.get("series", ""),
            "series_seq": top.get("series_seq", ""),
        }
        record.metadata_confidence = 1.0
        try:
            _finalize_import(record, match, files)
        except Exception as e:
            record.status = "failed"
            record.error_message = str(e)
            db.session.commit()
            return jsonify({"error": str(e)}), 500
    else:
        import_item.delay(record.id)

    return jsonify(record.to_dict()), 201


@imports_bp.post("/<int:import_id>/approve")
def approve_import(import_id):
    record = Import.query.get_or_404(import_id)
    if record.status != "needs_review":
        return jsonify({"error": "Import is not in needs_review state"}), 400

    data = request.get_json(force=True)
    author = data.get("author", "").strip()
    title = data.get("title", "").strip()
    series = data.get("series", "").strip()
    series_seq = data.get("series_seq", "").strip()

    # Allow selecting a candidate by index instead of typing manually
    candidate_index = data.get("candidate_index")
    if candidate_index is not None and record.candidates_json:
        candidates = json.loads(record.candidates_json)
        try:
            chosen = candidates[int(candidate_index)]
            author = author or chosen.get("author", "")
            title = title or chosen.get("title", "")
            series = series or chosen.get("series", "")
            series_seq = series_seq or chosen.get("series_seq", "")
        except (IndexError, ValueError):
            return jsonify({"error": "Invalid candidate_index"}), 400

    if not author or not title:
        return jsonify({"error": "author and title are required"}), 400

    files = discover_files(record.content_path, record.category)
    if not files:
        record.status = "failed"
        record.error_message = "No matching files found at original path"
        db.session.commit()
        return jsonify({"error": record.error_message}), 400

    # If series wasn't explicitly set, query APIs to fill it in
    if not series and not series_seq:
        meta = resolve_metadata(f"{author} {title}", record.category)
        top = meta["candidates"][0] if meta["candidates"] else {}
        series = top.get("series", "")
        series_seq = top.get("series_seq", "")

    match = {"author": author, "title": title, "series": series, "series_seq": series_seq}
    try:
        _finalize_import(record, match, files)
    except Exception as e:
        record.status = "failed"
        record.error_message = str(e)
        db.session.commit()
        return jsonify({"error": str(e)}), 500

    return jsonify(record.to_dict())


@imports_bp.post("/clear")
def clear_imports():
    data = request.get_json(force=True) or {}
    statuses = data.get("statuses")  # list of status strings, or omit for all
    query = Import.query
    if statuses:
        query = query.filter(Import.status.in_(statuses))
    count = query.delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"deleted": count})


@imports_bp.post("/<int:import_id>/retry")
def retry_import(import_id):
    record = Import.query.get_or_404(import_id)
    if record.status not in ("failed", "needs_review"):
        return jsonify({"error": "Only failed or needs_review imports can be retried"}), 400

    record.status = "pending"
    record.error_message = None
    db.session.commit()
    import_item.delay(record.id)
    return jsonify(record.to_dict())
