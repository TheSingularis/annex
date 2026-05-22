from pathlib import Path


def read_author(files: list[Path]) -> str:
    """
    Try to read the author from audio file metadata tags.
    Checks the first few files and returns the first non-empty result.
    """
    for f in files[:3]:
        try:
            author = _read_from_file(f)
            if author and len(author) > 1:
                return author.strip()
        except Exception:
            continue
    return ""


def _read_from_file(path: Path) -> str:
    ext = path.suffix.lower()

    if ext in (".m4b", ".m4a", ".mp4", ".aac"):
        return _read_mp4(path)
    elif ext == ".mp3":
        return _read_mp3(path)
    elif ext in (".flac", ".ogg", ".opus"):
        return _read_vorbis(path)
    return ""


def _read_mp4(path: Path) -> str:
    from mutagen.mp4 import MP4
    audio = MP4(str(path))
    if not audio.tags:
        return ""
    # Prefer explicit author tag, then album artist (usually author), then artist (may be narrator)
    for tag in ("©aut", "aART", "©ART"):
        val = audio.tags.get(tag)
        if val and str(val[0]).strip():
            return str(val[0]).strip()
    return ""


def _read_mp3(path: Path) -> str:
    from mutagen.id3 import ID3, ID3NoHeaderError
    try:
        tags = ID3(str(path))
    except ID3NoHeaderError:
        return ""
    # TPE2 (album artist) is more often the author than TPE1 (lead performer/narrator)
    for tag in ("TPE2", "TPE1", "TCOM"):
        frame = tags.get(tag)
        if frame and frame.text and str(frame.text[0]).strip():
            return str(frame.text[0]).strip()
    return ""


def _read_vorbis(path: Path) -> str:
    try:
        if path.suffix.lower() == ".flac":
            from mutagen.flac import FLAC
            audio = FLAC(str(path))
            tags = audio.tags or {}
        else:
            from mutagen.oggvorbis import OggVorbis
            audio = OggVorbis(str(path))
            tags = audio.tags or {}
    except Exception:
        return ""
    for key in ("albumartist", "album_artist", "artist", "composer"):
        val = tags.get(key)
        if val and str(val[0]).strip():
            return str(val[0]).strip()
    return ""
