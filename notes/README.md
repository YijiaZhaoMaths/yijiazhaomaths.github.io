# Notes directory

Upload PDF notes to this directory using these filenames:

- `geometric-satake-notes.pdf`
- `perverse-sheaves-notes.pdf`
- `springer-theory-notes.pdf`

After GitHub Pages finishes deploying, the corresponding download buttons on the website will become available automatically.

Record each note's public update time in `metadata.json` using an ISO 8601 timestamp with the Beijing-time offset. The recommended format is `YYYY-MM-DDTHH:mm+08:00`, for example:

```json
{
  "file": "geometric-satake-notes.pdf",
  "updated": "2026-09-23T21:30+08:00"
}
```

The website displays the timestamp through the minute and explicitly labels it as Beijing Time (UTC+8). If `updated` is left empty, the website will use the PDF response's `Last-Modified` header when GitHub Pages provides it. Notes without either value remain sortable but are placed after notes with known dates.
