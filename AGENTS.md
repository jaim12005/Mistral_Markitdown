# Repository Guidelines

## Project Structure
- `main.py`: Interactive CLI (modes: Hybrid, Enhanced Batch, MarkItDown only, OCR only, Batch, PDF→Images, Status). CLI flags: `--mode`, `--no-interactive`, `--test`.
- `local_converter.py`: MarkItDown integration; PDF table extraction (pdfplumber/camelot); PDF→image utility.
- `mistral_converter.py`: Mistral OCR integration using SDK v1 (Files API with `purpose="ocr"`, page targeting, image fallbacks).
- `utils.py`: Logging, helpers (md tables, md→txt), concurrency, caching/metadata tracking.
- `config.py`: Env/dir setup. Creates `input/`, `output_md/`, `output_txt/`, `output_images/`, `logs/`, `cache/`.
- `.env.example`: Copy to `.env` and set keys.

## Developer Setup
- Create venv: `python -m venv env && source env/bin/activate` (Windows: `env\Scripts\activate`).
- Install deps: `pip install -r requirements.txt` (scripts already run with `-U --upgrade-strategy eager`).
- Configure: `cp .env.example .env`; set `MISTRAL_API_KEY`; set `POPPLER_PATH` (Windows) for PDF→image and re‑OCR fallback.
- Run: `python main.py` (or use `run_converter.bat` / `bash quick_start.sh`).

### Windows installer behavior (`run_converter.bat`)
- Shows a dot progress indicator during installation steps.
- Upgrades `pip`, `setuptools`, and `wheel`; installs/updates deps with `--upgrade-strategy eager`.
- Logs installer output to `logs/pip_install.log` and writes installed versions to `logs/installed_versions.txt`.

## Architecture Notes
- OCR (Option 4):
  - PDFs and large images are uploaded via `files.upload(..., purpose="ocr")` and processed with `document={"type":"file","file_id":...}`.
  - Small images are sent as `image_url` data URLs.
  - Weak pages are re‑OCRed via `pages=[index]`; if Poppler is available we render the page to PNG and re‑OCR as an image.
- Hybrid (Option 1):
  - MarkItDown primary + PDF table extraction; OCR adds page‑by‑page analysis; a `_combined.md` is produced.
- Outputs:
  - Markdown (`output_md/`):
    - MarkItDown: `<name>.md`
    - PDF tables: `<name>_tables_all.md`, `<name>_tables_wide.md`, `<name>_tables.md`
    - Mistral OCR: `<name>_mistral_ocr.md`, plus `<name>_ocr_metadata.json`
    - Hybrid (PDFs): `<name>_combined.md`
  - Text (`output_txt/`): plain‑text exports matching the above Markdown files
  - Images (`output_images/`):
    - OCR‑extracted images under `<name>_ocr/` (with optional `.metadata.json` sidecars)
    - PDF→Images pages under `<pdfname>_pages/`

## Coding Style & Practices
- Python 3.10+, PEP8, 4 spaces, type hints where helpful. Use `pathlib.Path`.
- Minimize prints; use `utils.logline` for non‑user messages.
- Keep modules focused and changes narrow; do not change filenames/entrypoints unless intentional.

## Troubleshooting & Logs
- Cache: `cache/` stores OCR caches (24h). Delete to force re‑OCR.
- Logs: `logs/` holds session metadata and optional OCR JSONs (`SAVE_MISTRAL_JSON=true`). Safe to delete; regenerated next run.
- Common issues: missing `MISTRAL_API_KEY`, Poppler/Ghostscript not installed, old Python version.

## Commit & PR Guidelines
- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`.
- PRs: clear description (what/why), steps to test, screenshots or sample outputs for status screen.
- Update docs (`README.md`, `.env.example`, this file) when config/UX changes.

## Documentation Links
- MarkItDown (Microsoft): https://github.com/microsoft/markitdown
- Mistral Document AI – Basic OCR (overview): https://docs.mistral.ai/capabilities/document_ai/basic_ocr/
- Mistral – OCR with Image: https://docs.mistral.ai/capabilities/document_ai/basic_ocr/#ocr-with-image
- Mistral – OCR with PDF: https://docs.mistral.ai/capabilities/document_ai/basic_ocr/#ocr-with-pdf
- Mistral – Document AI OCR Processor: https://docs.mistral.ai/capabilities/document_ai/basic_ocr/#document-ai-ocr-processor
- Mistral Python Client (SDK v1): https://github.com/mistralai/client-python
- Mistral SDK – OCR endpoint reference: https://github.com/mistralai/client-python/blob/main/docs/sdks/ocr/README.md
- Mistral SDK – Files API + purpose=ocr: https://github.com/mistralai/client-python/blob/main/docs/sdks/files/README.md
- Mistral SDK – FilePurpose values: https://github.com/mistralai/client-python/blob/main/docs/models/filepurpose.md
- Camelot (PDF tables): https://camelot-py.readthedocs.io/
- pdf2image (Poppler): https://github.com/Belval/pdf2image

## Getting Started
- Clone and enter repo: `git clone <repo> && cd <repo>`
- Create venv + install deps: `python -m venv env && source env/bin/activate` (Windows: `env\Scripts\activate`), then `pip install -r requirements.txt`
- Configure: `cp .env.example .env` and set `MISTRAL_API_KEY` (and `POPPLER_PATH` on Windows if needed)
- Run:
  - Interactive: `python main.py`
  - Hybrid non-interactive: `python main.py --mode hybrid --no-interactive`
- Convenience:
  - Windows: `run_converter.bat`
  - macOS/Linux: `bash quick_start.sh`
