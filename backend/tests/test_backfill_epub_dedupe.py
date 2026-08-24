from pathlib import Path

from scripts.backfill_epub_dedupe import find_candidate_groups


def test_find_candidate_groups_flags_same_stem_duplicates(tmp_path):
    folder = tmp_path / "Book"
    folder.mkdir()
    (folder / "Book.epub").write_text("a")
    (folder / "Book.mobi").write_text("b")

    groups = list(find_candidate_groups(tmp_path))

    assert len(groups) == 1
    found_folder, files = groups[0]
    assert found_folder == folder
    assert {f.name for f in files} == {"Book.epub", "Book.mobi"}


def test_find_candidate_groups_ignores_different_titles_in_one_folder(tmp_path):
    # Regression: a folder holding several different books (e.g. an
    # anthology/series dumped in one directory) must never be treated as
    # "multiple formats of one book" just because it has >1 ebook file.
    folder = tmp_path / "The Expanse"
    folder.mkdir()
    (folder / "Leviathan Wakes.epub").write_text("a")
    (folder / "Calibans War.epub").write_text("b")
    (folder / "Abaddons Gate.epub").write_text("c")

    groups = list(find_candidate_groups(tmp_path))

    assert groups == []


def test_find_candidate_groups_handles_mixed_folder(tmp_path):
    # A series folder where one title has genuine format duplicates and the
    # others are standalone singles -- only the duplicate pair should surface.
    folder = tmp_path / "Series"
    folder.mkdir()
    (folder / "Book One.epub").write_text("a")
    (folder / "Book One.mobi").write_text("b")
    (folder / "Book Two.epub").write_text("c")
    (folder / "Book Three.epub").write_text("d")

    groups = list(find_candidate_groups(tmp_path))

    assert len(groups) == 1
    _, files = groups[0]
    assert {f.name for f in files} == {"Book One.epub", "Book One.mobi"}
