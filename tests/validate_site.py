#!/usr/bin/env python3
"""Dependency-free structural checks for the static personal website."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unicodedata
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "index.html"
METADATA_PATH = ROOT / "notes" / "metadata.json"


def valid_pdf_filename(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    filename = unicodedata.normalize("NFC", value.strip())
    return (
        len(filename) <= 240
        and filename.casefold().endswith(".pdf")
        and filename not in {".", ".."}
        and "/" not in filename
        and "\\" not in filename
        and not any(ord(character) < 32 or ord(character) == 127 for character in filename)
    )


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.fragment_links: list[str] = []
        self.translation_errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.append(str(attributes["id"]))
        href = attributes.get("href")
        if href and href.startswith("#") and len(href) > 1:
            self.fragment_links.append(href[1:])
        for left, right in (
            ("data-zh", "data-en"),
            ("data-zh-html", "data-en-html"),
            ("data-aria-zh", "data-aria-en"),
        ):
            if (left in attributes) != (right in attributes):
                self.translation_errors.append(f"<{tag}> must pair {left} with {right}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"Validation failed: {message}")


def validate_metadata() -> dict:
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    require(metadata.get("schemaVersion") == 1, "metadata schemaVersion must be 1")
    columns = metadata.get("columns")
    require(isinstance(columns, list) and bool(columns), "metadata columns must be a non-empty array")
    column_ids: set[str] = set()
    for index, column in enumerate(columns):
        require(isinstance(column, dict), f"column {index} must be an object")
        column_id = column.get("id")
        require(isinstance(column_id, str) and bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", column_id)), f"column {index} has an invalid id")
        require(column_id not in column_ids, f"duplicate column id: {column_id}")
        column_ids.add(column_id)
        label = column.get("label")
        require(isinstance(label, dict), f"column {index} label must be localized")
        require(all(isinstance(label.get(language), str) and label[language].strip() for language in ("zh", "en")), f"column {index} label is incomplete")
        require(isinstance(column.get("visible", True), bool), f"column {index} visible must be boolean")
    require(isinstance(metadata.get("notes"), list), "metadata notes must be an array")
    seen: set[str] = set()
    for index, note in enumerate(metadata["notes"]):
        require(isinstance(note, dict), f"note {index} must be an object")
        filename = note.get("file")
        require(valid_pdf_filename(filename), f"note {index} has an unsafe PDF filename")
        key = filename.casefold()
        require(key not in seen, f"duplicate PDF filename: {filename}")
        seen.add(key)
        categories = note.get("categories")
        require(isinstance(categories, list) and bool(categories), f"note {index} needs categories")
        require(all(category in column_ids for category in categories), f"note {index} has an unknown category")
        require(len(categories) == len(set(categories)), f"note {index} repeats a category")
        download_url = note.get("downloadUrl")
        if download_url:
            parsed = urlsplit(download_url)
            require(parsed.scheme == "https" and bool(parsed.netloc), f"note {index} has an invalid remote download URL")
        digest = note.get("sha256")
        if digest:
            require(isinstance(digest, str) and bool(re.fullmatch(r"[a-f0-9]{64}", digest)), f"note {index} has an invalid SHA-256")
        page_count = note.get("pageCount")
        if page_count is not None:
            require(isinstance(page_count, int) and not isinstance(page_count, bool) and page_count > 0, f"note {index} has an invalid page count")
        author = note.get("author")
        if author:
            require(isinstance(author, str) and len(author.strip()) <= 180, f"note {index} has an invalid author")
        for field in ("category", "title", "description"):
            localized = note.get(field)
            require(isinstance(localized, dict), f"note {index} field {field} must be localized")
            for language in ("zh", "en"):
                require(isinstance(localized.get(language), str) and bool(localized[language].strip()), f"note {index} field {field}.{language} is empty")
    return metadata


def validate_html(metadata: dict) -> None:
    page = INDEX_PATH.read_text(encoding="utf-8")
    parser = SiteParser()
    parser.feed(page)
    duplicates = [identifier for identifier, count in Counter(parser.ids).items() if count > 1]
    require(not duplicates, f"duplicate HTML ids: {duplicates}")
    require(not parser.translation_errors, "; ".join(parser.translation_errors))
    missing_fragments = sorted(set(parser.fragment_links) - set(parser.ids))
    require(not missing_fragments, f"missing internal link targets: {missing_fragments}")
    require('data-zh="联系方式" data-en="Contact"' in page, "contact heading is missing")
    require("copy-help" not in page, "redundant manual copy-failure control remains")
    require("response.blob" not in page, "downloads must not buffer whole PDF files")
    require("notesPerPage: 6" in page, "note pagination size must remain explicit")
    require("availabilityConcurrency: 4" in page, "PDF availability concurrency limit is missing")
    require("scheduleVisibleNoteChecks" in page, "visible-note availability scheduler is missing")
    require(".filter((card) => card.isConnected)" in page, "PDF checks must be limited to mounted notes")
    require("checkedNoteDownloads = new WeakSet()" in page, "already checked PDF links must be remembered")
    require("renderNoteFilters" in page, "note filters must be generated from metadata columns")
    require("noteGrid.replaceChildren(fragment)" in page, "only visible note cards should be mounted")
    require("download.dataset.external" in page, "external PDF downloads must bypass cross-origin availability checks")
    require("requestIdleCallback" in page, "visible PDF checks should be deferred until the browser is idle")
    require("content-visibility: auto" in page, "below-the-fold sections should use rendering containment")
    require("note-document-info" in page, "optional PDF document information rendering is missing")
    require(not re.search(r"v1\.[0-9]+\.[0-9]+", page), "release number must not be visible in the website")
    require("NOTES_NOSCRIPT_START" in page and "NOTES_NOSCRIPT_END" in page, "no-script notes markers are missing")
    fallback = page.split("<!-- NOTES_NOSCRIPT_START -->", 1)[1].split("<!-- NOTES_NOSCRIPT_END -->", 1)[0]
    for note in metadata["notes"]:
        require(note["file"] in fallback, f"no-script fallback is missing {note['file']}")

    json_ld_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.DOTALL)
    require(json_ld_match is not None, "JSON-LD block is missing")
    json.loads(json_ld_match.group(1))

    script_start = page.rfind("<script>")
    script_end = page.rfind("</script>")
    require(script_start >= 0 and script_end > script_start, "main JavaScript block is missing")
    script = page[script_start + len("<script>") : script_end]
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as temporary:
        temporary.write(script)
        temporary.flush()
        subprocess.run(["node", "--check", temporary.name], check=True)


def main() -> None:
    require(INDEX_PATH.is_file(), "index.html is missing")
    require(METADATA_PATH.is_file(), "notes/metadata.json is missing")
    metadata = validate_metadata()
    validate_html(metadata)
    print(f"Site validation passed: {len(metadata['notes'])} note records.")


if __name__ == "__main__":
    main()
