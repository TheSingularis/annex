from app.fileops import hardlink_files


def test_hardlink_files_links_single_new_file(app, tmp_path):
    src = tmp_path / "src.epub"
    src.write_text("content")
    target_dir = tmp_path / "target"

    linked = hardlink_files([src], target_dir, "My Title")

    assert linked == [target_dir / "My Title.epub"]
    assert (target_dir / "My Title.epub").exists()


def test_hardlink_files_single_file_collision_returns_empty(app, tmp_path):
    # Regression: two different source downloads resolving to the same
    # title used to silently skip the second one but still report success
    # to the caller (the DB record then got marked "imported" even though
    # nothing new was linked).
    src = tmp_path / "src.epub"
    src.write_text("content")
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "My Title.epub").write_text("a different, pre-existing file")

    linked = hardlink_files([src], target_dir, "My Title")

    assert linked == []
    # The pre-existing file must be untouched, not overwritten.
    assert (target_dir / "My Title.epub").read_text() == "a different, pre-existing file"


def test_hardlink_files_multi_file_partial_collision_returns_only_new_ones(app, tmp_path):
    src1 = tmp_path / "01.mp3"
    src1.write_text("a")
    src2 = tmp_path / "02.mp3"
    src2.write_text("b")
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "01.mp3").write_text("already here")

    linked = hardlink_files([src1, src2], target_dir, "My Audiobook")

    assert linked == [target_dir / "02.mp3"]
