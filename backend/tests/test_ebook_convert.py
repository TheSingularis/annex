import subprocess

import pytest

from app import ebook_convert
from app.ebook_convert import (
    EbookConversionError,
    convert_to_epub,
    needs_conversion,
    select_ebook_source,
)


# --- select_ebook_source ---

def test_select_ebook_source_prefers_native_epub_over_azw3_and_mobi(tmp_path):
    files = [tmp_path / "book.azw3", tmp_path / "book.epub", tmp_path / "book.mobi"]

    chosen, passthrough = select_ebook_source(files)

    assert chosen == tmp_path / "book.epub"
    assert passthrough == []  # losing azw3/mobi siblings dropped, not passed through


def test_select_ebook_source_prefers_azw3_over_mobi_when_no_epub(tmp_path):
    files = [tmp_path / "book.mobi", tmp_path / "book.azw3"]

    chosen, passthrough = select_ebook_source(files)

    assert chosen == tmp_path / "book.azw3"
    assert passthrough == []


def test_select_ebook_source_mobi_only(tmp_path):
    files = [tmp_path / "book.mobi"]

    chosen, passthrough = select_ebook_source(files)

    assert chosen == tmp_path / "book.mobi"
    assert passthrough == []


def test_select_ebook_source_pdf_passes_through_alongside_azw3(tmp_path):
    files = [tmp_path / "book.azw3", tmp_path / "book.pdf"]

    chosen, passthrough = select_ebook_source(files)

    assert chosen == tmp_path / "book.azw3"
    assert passthrough == [tmp_path / "book.pdf"]


def test_select_ebook_source_pdf_never_chosen(tmp_path):
    files = [tmp_path / "book.pdf"]

    chosen, passthrough = select_ebook_source(files)

    assert chosen is None
    assert passthrough == [tmp_path / "book.pdf"]


def test_select_ebook_source_comic_only_returns_none(tmp_path):
    files = [tmp_path / "issue1.cbz"]

    chosen, passthrough = select_ebook_source(files)

    assert chosen is None
    assert passthrough == [tmp_path / "issue1.cbz"]


# --- needs_conversion ---

def test_needs_conversion_true_for_azw3_and_mobi(tmp_path):
    assert needs_conversion(tmp_path / "book.azw3") is True
    assert needs_conversion(tmp_path / "book.mobi") is True


def test_needs_conversion_false_for_epub_pdf_and_none(tmp_path):
    assert needs_conversion(tmp_path / "book.epub") is False
    assert needs_conversion(tmp_path / "book.pdf") is False
    assert needs_conversion(None) is False


# --- convert_to_epub ---

def test_convert_to_epub_success(tmp_path, monkeypatch):
    source = tmp_path / "book.azw3"
    source.write_text("fake")
    workdir = tmp_path / "work"
    workdir.mkdir()

    def fake_run(cmd, **kwargs):
        (workdir / "book.epub").write_text("converted")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(ebook_convert.subprocess, "run", fake_run)

    result = convert_to_epub(source, workdir)

    assert result == workdir / "book.epub"
    assert result.exists()


def test_convert_to_epub_nonzero_exit_raises(tmp_path, monkeypatch):
    source = tmp_path / "book.azw3"
    source.write_text("fake")
    workdir = tmp_path / "work"
    workdir.mkdir()

    monkeypatch.setattr(
        ebook_convert.subprocess, "run",
        lambda cmd, **k: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="corrupt file"),
    )

    with pytest.raises(EbookConversionError, match="corrupt file"):
        convert_to_epub(source, workdir)


def test_convert_to_epub_missing_output_raises_even_on_zero_exit(tmp_path, monkeypatch):
    # Defensive: don't trust exit code 0 alone if ebook-convert didn't
    # actually produce the file it claimed to.
    source = tmp_path / "book.azw3"
    source.write_text("fake")
    workdir = tmp_path / "work"
    workdir.mkdir()

    monkeypatch.setattr(
        ebook_convert.subprocess, "run",
        lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
    )

    with pytest.raises(EbookConversionError):
        convert_to_epub(source, workdir)


def test_convert_to_epub_missing_binary_raises(tmp_path, monkeypatch):
    source = tmp_path / "book.azw3"
    workdir = tmp_path / "work"
    workdir.mkdir()

    def fake_run(cmd, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(ebook_convert.subprocess, "run", fake_run)

    with pytest.raises(EbookConversionError, match="not found"):
        convert_to_epub(source, workdir)


def test_convert_to_epub_timeout_raises(tmp_path, monkeypatch):
    source = tmp_path / "book.azw3"
    workdir = tmp_path / "work"
    workdir.mkdir()

    def fake_run(cmd, **k):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=300)

    monkeypatch.setattr(ebook_convert.subprocess, "run", fake_run)

    with pytest.raises(EbookConversionError, match="timed out"):
        convert_to_epub(source, workdir)
