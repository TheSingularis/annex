from datetime import datetime, timezone
from app import db


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
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
