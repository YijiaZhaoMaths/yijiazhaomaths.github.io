#!/usr/bin/env python3
"""Regenerate the no-JavaScript notes list from notes/metadata.json."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "index.html"
METADATA_PATH = ROOT / "notes" / "metadata.json"
START = "<!-- NOTES_NOSCRIPT_START -->"
END = "<!-- NOTES_NOSCRIPT_END -->"


def render(metadata: dict) -> str:
    cards = []
    for note in metadata["notes"]:
        filename = html.escape(note["file"], quote=True)
        href = html.escape(note.get("downloadUrl") or f"notes/{quote(note['file'])}", quote=True)
        attributes = ' target="_blank" rel="noopener noreferrer"' if note.get("downloadUrl") else " download"
        cards.append(
            "            <article class=\"note-card noscript-note-card\">"
            f"<div><span class=\"note-category\">{html.escape(note['category']['zh'])}</span>"
            f"<h3>{html.escape(note['title']['zh'])}<span class=\"note-title-en\" lang=\"en\">{html.escape(note['title']['en'])}</span></h3>"
            f"<p>{html.escape(note['description']['zh'])}</p></div><div class=\"note-footer\">"
            f"<span class=\"note-status\"><code>{filename}</code></span>"
            f"<a class=\"note-download\" href=\"{href}\"{attributes}>下载 PDF</a></div></article>"
        )
    body = "\n".join(cards) if cards else "            <p class=\"notes-empty\">目前还没有公开笔记。</p>"
    return (
        "        <noscript>\n"
        "          <div class=\"notes-grid\" aria-label=\"无需 JavaScript 的笔记列表\">\n"
        f"{body}\n"
        "          </div>\n"
        "        </noscript>"
    )


def generated_page() -> tuple[str, str]:
    page = INDEX_PATH.read_text(encoding="utf-8")
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    if page.count(START) != 1 or page.count(END) != 1:
        raise SystemExit("index.html must contain exactly one no-script marker pair")
    prefix, remaining = page.split(START, 1)
    _, suffix = remaining.split(END, 1)
    result = f"{prefix}{START}\n{render(metadata)}\n        {END}{suffix}"
    return page, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail instead of writing when the generated block is stale.")
    arguments = parser.parse_args()
    current, expected = generated_page()
    if arguments.check:
        if current != expected:
            raise SystemExit("The no-JavaScript notes list is stale. Run tests/sync_noscript.py.")
        print("No-JavaScript notes list is synchronized.")
        return
    INDEX_PATH.write_text(expected, encoding="utf-8")
    print("Updated the no-JavaScript notes list.")


if __name__ == "__main__":
    main()
