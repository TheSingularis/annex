import os
import re
import shutil
from pathlib import Path
from flask import current_app


_ILLEGAL_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize(name: str) -> str:
    name = _ILLEGAL_CHARS_RE.sub("", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "Unknown"


def build_target_dir(category: str, author: str, title: str, series: str = "", series_seq: str = "") -> Path:
    from app.app_settings import load as load_settings
    s = load_settings()
    if category == "audiobook":
        base = Path(s.get("audiobook_library_path") or current_app.config["AUDIOBOOK_LIBRARY_PATH"])
    else:
        base = Path(s.get("ebook_library_path") or current_app.config["EBOOK_LIBRARY_PATH"])

    author_dir = sanitize(author) or "Unknown Author"
    title_dir = sanitize(title) or "Unknown Title"

    if series:
        series_dir = sanitize(series)
        if series_seq:
            title_dir = f"{series_seq} - {title_dir}"
        return base / author_dir / series_dir / title_dir

    return base / author_dir / title_dir


def discover_files(content_path: str, category: str) -> list[Path]:
    path = Path(content_path)
    if category == "audiobook":
        extensions = current_app.config["AUDIOBOOK_EXTENSIONS"]
    else:
        extensions = current_app.config["EBOOK_EXTENSIONS"]

    if path.is_file():
        return [path] if path.suffix.lower() in extensions else []

    return sorted(
        f for f in path.rglob("*")
        if f.is_file() and f.suffix.lower() in extensions
    )


def hardlink_files(source_files: list[Path], target_dir: Path, title: str) -> list[Path]:
    """
    Links source_files into target_dir via hardlink, falling back to copy
    if source and destination are on different devices (common on Unraid).
    Single file: renamed to {title}{ext}. Multiple files: original names kept.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    linked = []

    for src in source_files:
        if len(source_files) == 1:
            dst = target_dir / f"{sanitize(title)}{src.suffix.lower()}"
        else:
            dst = target_dir / src.name

        if dst.exists():
            current_app.logger.info(f"Link target already exists, skipping: {dst}")
            linked.append(dst)
            continue

        try:
            os.link(src, dst)
        except OSError as e:
            if e.errno != 18:  # 18 = EXDEV (cross-device link)
                raise
            current_app.logger.info(f"Cross-device: copying instead of hardlinking {src.name}")
            shutil.copy2(src, dst)

        linked.append(dst)

    return linked
