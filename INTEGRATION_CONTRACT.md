# Mistral_Markitdown Integration Contract

This document defines how `Mistral_Markitdown` should be used inside the broader OpenClaw web/document workflow stack.

## Position in the stack

`Mistral_Markitdown` is the document-normalization and OCR lane.

Recommended order:

1. Discovery + acquisition
   - Crawl4AI (or equivalent) gathers source URLs/files.
2. Document normalization lane (this repo)
   - Run `Mistral_Markitdown` for binary docs and OCR-heavy sources.
3. Structured extraction lane (optional)
   - Run LangExtract only when structured/source-grounded fields are required.
4. Summarization/answering
   - Use normalized markdown (and optional extracted JSON) for user-facing output.

## Trigger rules

Use `Mistral_Markitdown` when any of the following are true:

- Input is PDF/image/Office file and OCR or layout understanding matters.
- User asks for OCR, document QnA, or batch OCR.
- Source contains table-heavy or scan-heavy content where plain text extraction is weak.
- Previous text-only extraction quality is low or incomplete.

Skip or down-rank `Mistral_Markitdown` when:

- Input is already clean HTML/plain text and speed is the main goal.
- The task is a quick "latest" pulse where full OCR normalization adds unnecessary latency.

## Output handoff contract

Treat these artifacts as the normalized handoff payload:

- Markdown document: `output_md/<stem>_mistral_ocr.md`
- OCR metadata JSON: `output_md/<stem>_ocr_metadata.json`
- Optional text export: `output_txt/<stem>_mistral_ocr.txt`

Downstream tools should consume:

- `normalized_markdown_path`
- `ocr_metadata_path`
- `quality_score` (if present)
- `is_usable` / quality verdict (if present)
- `page_count`
- `conversion_method`

## Quality gate and fallback

Recommended gate:

- If OCR quality is below acceptable threshold or `is_usable` is false, do not silently trust output.
- Fallback options:
  1. Retry with alternative mode/profile (for large/mixed docs).
  2. Use MarkItDown-only lane for text-native docs.
  3. Return low-confidence status and continue with best-effort summary.

## Security and key management

- Keep API key in global runtime env: `~/.openclaw/.env`.
- Never commit keys into repo files.
- Avoid copying keys into chat logs or synced notes.

## Operational guidance

- For long/batch runs, prefer background/resumable execution.
- Keep lane optional; do not force for every request.
- Prefer deterministic handoff artifacts (file paths + metadata) over ad-hoc text blobs.

## Validation status

Live validation completed on 2026-02-10:

- Mistral API auth succeeded.
- `models.list` succeeded.
- End-to-end OCR lane succeeded on a generated test image.
- Expected artifacts were produced and readable in `output_md`.
