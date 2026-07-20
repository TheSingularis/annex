from datetime import datetime, timezone
from app import db


class AppSettings(db.Model):
    __tablename__ = "app_settings"

    key = db.Column(db.Text, primary_key=True)
    value = db.Column(db.Text, nullable=False, default="")

    @classmethod
    def get(cls, key: str, default: str = "") -> str:
        row = cls.query.get(key)
        return row.value if row else default

    @classmethod
    def set(cls, key: str, value: str):
        row = cls.query.get(key)
        if row:
            row.value = value
        else:
            db.session.add(cls(key=key, value=value))
        db.session.commit()

    @classmethod
    def get_abs_config(cls) -> dict:
        return {
            "abs_host": cls.get("abs_host"),
            "abs_api_key": cls.get("abs_api_key"),
            "abs_audiobook_library_id": cls.get("abs_audiobook_library_id"),
            "abs_ebook_library_id": cls.get("abs_ebook_library_id"),
        }


class Import(db.Model):
    __tablename__ = "imports"

    id = db.Column(db.Integer, primary_key=True)
    hash = db.Column(db.Text, unique=True, nullable=True)  # null for manual imports
    name = db.Column(db.Text, nullable=False)
    category = db.Column(db.Text, nullable=False)  # audiobook | ebook
    content_path = db.Column(db.Text, nullable=False)
    status = db.Column(db.Text, nullable=False, default="pending")
    # pending | importing | imported | needs_review | failed

    metadata_confidence = db.Column(db.Float, nullable=True)
    resolved_author = db.Column(db.Text, nullable=True)
    resolved_title = db.Column(db.Text, nullable=True)
    resolved_series = db.Column(db.Text, nullable=True)
    resolved_series_seq = db.Column(db.Text, nullable=True)
    target_path = db.Column(db.Text, nullable=True)
    candidates_json = db.Column(db.Text, nullable=True)  # JSON top-3 candidates
    error_message = db.Column(db.Text, nullable=True)

    # Backfilled from the old resolver's already-computed match data (see
    # app.matching Phase 4a) -- zero new behavior, just persisting a value
    # that was previously discarded. asin has no live producer yet (only the
    # still-unwired app.matching.resolution path sets it) and stays NULL
    # until the Phase 4b cutover.
    isbn = db.Column(db.Text, nullable=True)
    asin = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "hash": self.hash,
            "name": self.name,
            "category": self.category,
            "content_path": self.content_path,
            "status": self.status,
            "metadata_confidence": self.metadata_confidence,
            "resolved_author": self.resolved_author,
            "resolved_title": self.resolved_title,
            "resolved_series": self.resolved_series,
            "resolved_series_seq": self.resolved_series_seq,
            "target_path": self.target_path,
            "candidates_json": self.candidates_json,
            "error_message": self.error_message,
            "isbn": self.isbn,
            "asin": self.asin,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ShadowMatch(db.Model):
    """Phase 4a observation record: the new matcher's (app.matching.orchestrator)
    output for a live import, alongside what the old resolver actually decided.
    Never read by any real import decision -- purely for offline comparison
    during the shadow-mode window. See
    /root/.claude/plans/jolly-greeting-karp.md (Phase 4a)."""

    __tablename__ = "shadow_matches"

    id = db.Column(db.Integer, primary_key=True)
    import_id = db.Column(db.Integer, db.ForeignKey("imports.id"), nullable=False)

    old_confidence = db.Column(db.Float, nullable=True)
    old_match_json = db.Column(db.Text, nullable=True)

    new_confidence = db.Column(db.Float, nullable=True)
    new_match_json = db.Column(db.Text, nullable=True)
    new_candidates_json = db.Column(db.Text, nullable=True)

    # Coarse title/author string comparison -- good enough for a human to
    # skim disagreements, not a precision metric.
    agrees = db.Column(db.Boolean, nullable=True)
    error = db.Column(db.Text, nullable=True)  # set if the new resolver raised

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "import_id": self.import_id,
            "old_confidence": self.old_confidence,
            "old_match_json": self.old_match_json,
            "new_confidence": self.new_confidence,
            "new_match_json": self.new_match_json,
            "new_candidates_json": self.new_candidates_json,
            "agrees": self.agrees,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
