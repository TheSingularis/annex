"""
Live resolver: composes extraction.py + resolution.py + the existing fuzzy
cascade (shared via app.metadata._resolve_from_parsed) into the same
{confidence, match, candidates} shape app.metadata's resolve_metadata used
to produce directly. This is what app.tasks._run_import calls for every real
import decision -- promoted after a shadow-mode observation window (see
/root/.claude/plans/jolly-greeting-karp.md) showed 270/273 agreement with
the old resolver, with the 3 disagreements being either a since-fixed sync
gap or genuine improvements from exact-ID resolution.
"""
from dataclasses import asdict, replace

from app.matching import extraction, resolution
from app.metadata import _resolve_from_parsed


def resolve_metadata_v2(
    torrent_name: str, category: str, hint_author: str = "", is_comic: bool = False
) -> dict:
    parsed = extraction.extract(torrent_name, is_comic=is_comic)

    # Use file-tag author only when the filename gave us nothing -- mirrors
    # resolve_metadata's own hint_author handling.
    if hint_author and not parsed.author:
        parsed = replace(parsed, author=hint_author.strip())

    exact = resolution.resolve(parsed.isbn, parsed.asin, category)
    if exact:
        exact = {**exact, "score": 1.0, "match_method": "exact_id"}
        return {"confidence": 1.0, "match": exact, "candidates": [exact]}

    return _resolve_from_parsed(asdict(parsed), category, is_comic)
