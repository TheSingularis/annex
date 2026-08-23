from app.fileops import hardlink_files, remove_linked_files


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


def test_remove_linked_files_deletes_files_and_prunes_empty_dir(app, tmp_path):
    target_dir = tmp_path / "Author" / "Title"
    target_dir.mkdir(parents=True)
    f = target_dir / "My Title.epub"
    f.write_text("content")

    remove_linked_files([f])

    assert not f.exists()
    assert not target_dir.exists()


def test_remove_linked_files_leaves_dir_with_other_content_in_place(app, tmp_path):
    # A scanner (e.g. Audiobookshelf) can write its own artifacts into a
    # target dir after import -- cover art, metadata.json. Those aren't
    # tracked by linked_files_json, so removing the wrongly-matched book
    # itself must not also guess-delete this leftover clutter or the dir.
    target_dir = tmp_path / "Author" / "Title"
    target_dir.mkdir(parents=True)
    f = target_dir / "My Title.epub"
    f.write_text("content")
    (target_dir / "cover.jpg").write_text("not tracked")

    remove_linked_files([f])

    assert not f.exists()
    assert target_dir.exists()
    assert (target_dir / "cover.jpg").exists()


def test_remove_linked_files_tolerates_already_missing_files(app, tmp_path):
    # A record's tracked file may already be gone (manual cleanup, a prior
    # partial reset) -- reset must still succeed, not raise.
    missing = tmp_path / "Author" / "Title" / "Ghost.epub"

    remove_linked_files([missing])  # must not raise
