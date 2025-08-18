# Enhanced Document Converter v2.1

This project provides a practical, cross‑platform document conversion tool that leverages **Microsoft MarkItDown** for fast, local conversion of various document types and **Mistral Document AI OCR** for high‑accuracy text extraction from images and complex PDFs. It is designed for quality results and an easy, predictable workflow on Windows and macOS.

## Quick Start

- Windows (recommended):
  - Run `run_converter.bat` (creates `env`, upgrades pip/setuptools/wheel, installs/updates deps with eager strategy, shows a dot progress indicator during install, logs to `logs/pip_install.log`, then launches the app)
- macOS/Linux:
  - Run `bash quick_start.sh` (creates `env`, installs deps, runs smoke test)
- Manual:
  - `python -m venv env && env\Scripts\activate` (Windows) or `source env/bin/activate` (macOS/Linux)
  - `pip install -r requirements.txt`
  - `cp .env.example .env` and set `MISTRAL_API_KEY`
  - `python main.py`

## Features

- **Multiple Conversion Modes**:
  - **Hybrid Mode**: Intelligently combines the strengths of Markitdown and Mistral OCR for the highest quality output.
  - **Markitdown Only**: For fast, local conversion of formats like `.docx`, `.pptx`, `.html`, etc.
  - **Mistral OCR Only**: For high-accuracy OCR on images, scanned PDFs, and now `.docx` and `.pptx` files.
  - **Transcription Mode**: Uses Markitdown's powerful transcription features to process audio files (`.mp3`, `.wav`) and YouTube URLs.
- **Advanced Table Extraction**: Uses `pdfplumber` and `camelot` to find and extract tables from PDFs, and reshapes them into a clean, usable format.
- **Modular and Extensible**: The codebase is organized into logical modules for configuration, utilities, and converters, making it easy to maintain and extend.
- **Robust and Performant**:
  - Caching for OCR results to avoid re-processing files.
  - Automatic retry logic for network requests.
  - Large file support for the Mistral API (uploads files instead of sending them in-request).
- **Easy to Configure**: All settings are managed through a `.env` file.

## Setup

1.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Create a virtual environment**:
    ```bash
    python -m venv env
    source env/bin/activate  # On Windows, use `env\Scripts\activate`
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure your environment**:
    -   Create a file named `.env` in the project root by copying the example file:
        ```bash
        cp .env.example .env
        ```
    -   Edit the `.env` file and add your **Mistral API Key**. You can also customize other settings as needed. See the `.env.example` file for a full list of options.

    ```ini
    # .env
    MISTRAL_API_KEY="your_mistral_api_key_here"
    # Optional: For PDF to image conversion, provide the path to your Poppler installation
    # POPPLER_PATH="C:/path/to/poppler-23.08.0/bin"
    ```

## Usage

The primary way to use the converter is through the interactive menu in `main.py`.

```bash
python main.py
```

This launches a menu where you can choose a mode:

- **Hybrid Mode**: Best default. Uses the optimal engine per file; for PDFs, it produces `<name>_combined.md` with MarkItDown content + tables + OCR analysis.
- **MarkItDown Only**: Fast local conversion (no API usage).
- **Mistral OCR Only**: OCR for PDFs, images, and Office documents (uses Files API with `purpose="ocr"` and per‑page improvements where needed).
- **Transcription Only**: Transcribes audio, video, and YouTube URLs to Markdown.
- **Batch Process Directory**: Simple batch by type.
- **Enhanced Batch**: Advanced concurrent processing with caching/metadata.
- **Convert PDFs to Images**: Renders each page to PNG under `output_images/<pdfname>_pages/`.

### Modes at a Glance

| Mode (menu)             | Flag                | Best for                           | Outputs (typical) |
|-------------------------|---------------------|------------------------------------|-------------------|
| Hybrid (1)              | `--mode hybrid`     | Best default; PDFs with tables/OCR | `output_md/<name>_combined.md`, `output_txt/` |
| Enhanced Batch (2)      | `--mode enhanced`   | Many files; concurrency + caching  | `output_md/`, `output_txt/`, `output_images/`, `logs/metadata/` |
| MarkItDown Only (3)     | `--mode markitdown` | Office/web/text files (local only) | `output_md/<name>.md`, `output_txt/<name>.txt` |
| Mistral OCR Only (4)    | `--mode ocr`        | Images, scanned PDFs, .docx, .pptx | `output_md/<name>_mistral_ocr.md`, `output_images/<name>_ocr/` (if images) + txt |
| Transcription Only (5)  | `--mode transcription` | Audio, video, and YouTube URLs    | `output_md/<name>_transcription.md`, `output_txt/<name>_transcription.txt` |
| Batch Process (6)       | `--mode batch`      | Simple batch by type               | `output_md/`, `output_txt/` |
| PDF → Images (7)        | n/a                 | Export pages as PNG                | `output_images/<pdfname>_pages/` |
| System Status (8)       | n/a                 | Environment and cache overview     | console only      |

### Input and Output

-   Place your files to be converted in the `input/` directory.
-   The converted Markdown files will be placed in the `output_md/` directory.
-   Plain text versions of the output will be in the `output_txt/` directory.
-   Images extracted during OCR will be in the `output_images/` directory.

## Output Files by Mode

Below is a quick reference of the files produced in each mode and where they are written. File names are shown as patterns using `<name>` for the original file stem.

### MarkItDown Only

- `output_md/<name>.md`
  - Enhanced Markdown with YAML frontmatter and standardized image links.
- `output_txt/<name>.txt`
  - Plain-text export of the Markdown for search/indexing.

### PDF Table Extraction (part of MarkItDown/Hybrid for PDFs)

- `output_md/<name>_tables_all.md`
  - Contains all detected/reshaped tables, each under "### Table N".
- `output_md/<name>_tables_wide.md`
  - The single "widest" table (most columns). Useful for month-wide financial statements.
- `output_md/<name>_tables.md`
  - A compact subset (commonly Account + key summary columns like Current Balance) for quick review.
  - Note: If reshaping fails, raw tables may be kept; quality depends on the PDF and detectors.

### Mistral OCR Only

- `output_md/<name>_mistral_ocr.md`
  - Page-by-page OCR Markdown. If `MISTRAL_INCLUDE_IMAGES=true`, images are embedded and linked.
- `output_md/<name>_ocr_metadata.json`
  - Structured JSON with page text blocks, image metadata (bbox, description), and summary.
- `output_txt/<name>_mistral_ocr.txt`
  - Plain-text export of the OCR Markdown.
- `output_images/<name>_ocr/`
  - Extracted images from OCR. Each image may have a corresponding `.metadata.json` sidecar with details.

### Transcription Mode

- `output_md/<name>_transcription.md`
  - Markdown file containing the transcribed text from an audio or video file.
- `output_txt/<name>_transcription.txt`
  - Plain-text export of the transcription.

### Hybrid Mode (Recommended for PDFs)

- `output_md/<name>_combined.md`
  - Aggregated report combining MarkItDown content, local table extraction, and OCR analysis.
- `output_txt/<name>_combined.txt`
  - Plain-text export of the combined Markdown.
- Also produced alongside (when applicable): the three table files above and OCR outputs listed under Mistral OCR.

### PDF → Images (Utility)

- `output_images/<pdfname>_pages/`
  - All pages rendered to PNG (requires Poppler). Useful for visual review and OCR fallback.

### Caches and Logs

- `cache/`
  - OCR cache entries to avoid reprocessing (duration configurable via `CACHE_DURATION_HOURS`).
- `logs/`
  - Session metadata and optional raw OCR JSON dumps (`SAVE_MISTRAL_JSON=true`). Safe to delete anytime.

## How it Works

### Hybrid Pipeline

The hybrid pipeline is the most powerful feature of this tool. For each file, it does the following:

1.  **Determines the best strategy**:
    -   For documents like `.docx`, `.pptx`, `.html`, it uses **Markitdown**.
    -   For images, it uses **Mistral OCR**.
    -   For PDFs, it uses **both**.

2.  **Processes with Markitdown**: Extracts the main text content and structure.

3.  **Processes with Local Table Extraction**: If the file is a PDF, it uses `pdfplumber` and `camelot` to find and extract tables.

4.  **Processes with Mistral OCR**: Extracts text and layout information with high accuracy.

5.  **Combines the results**: For PDFs, it creates a `_combined.md` file that includes:
    -   The main text content from Markitdown.
    -   A section with the extracted tables.
    -   The full, page-by-page OCR analysis from Mistral.

This approach uses each engine where it excels and produces clear, reusable Markdown.

### Architecture Overview

- `main.py`: Interactive CLI (modes 1–7) and CLI flags (`--mode`, `--no-interactive`, `--test`).
- `local_converter.py`: MarkItDown conversions, PDF table extraction (pdfplumber/camelot), PDF→image utility.
- `mistral_converter.py`: OCR integration using Mistral SDK v1 (Files API with `purpose="ocr"`, multi‑page handling, page re‑OCR).
- `utils.py`: Helpers (logging, markdown tables, txt export), intelligent concurrency and caching metadata.
- `config.py`: Env loading (`.env` preferred), constants, and directory creation.

## Quick Start Scripts

- Windows: run `run_converter.bat` to create `env`, install dependencies, and start the app.
- macOS/Linux: run `bash quick_start.sh` to set up and run a smoke test.

## Installer behavior and progress (Windows)

When you run `run_converter.bat`, the script ensures a clean, up‑to‑date environment and provides a simple visual progress indicator during installation steps:

- Upgrades core build tools: `pip`, `setuptools`, and `wheel`.
- Installs or upgrades all project dependencies using:
  - `pip install -U --upgrade-strategy eager -r requirements.txt`
- Shows a dot progress indicator while each step runs. The console prints dots until the step completes.
- Performs a post‑install check: `pip check`.
- Writes a full snapshot of installed versions to `logs/installed_versions.txt`.
- Writes detailed installer logs to `logs/pip_install.log`.
- Runs entirely with the local venv interpreter (`env\Scripts\python.exe`) without activating the venv, preventing PATH contamination.

If an installation step appears to stall, open `logs/pip_install.log` in your editor for real‑time details.

## Requirements and Notes

- Python 3.10+ is required (MarkItDown requires 3.10+).
- For best PDF table extraction with Camelot lattice mode, install Ghostscript and ensure it is on PATH (`gs`, `gswin64c.exe`, or `gswin32c.exe`).
- For PDF-to-image, install Poppler (macOS: `brew install poppler`; Windows: download binaries) and set `POPPLER_PATH` on Windows.
- Poppler improves OCR fallback quality: Option 4 re-renders weak PDF pages to images for a stronger re‑OCR pass when Poppler is available (set `POPPLER_PATH` on Windows); without Poppler it still reprocesses via `file_id` with `pages=[index]`.
- The Mistral integration uses the official `mistralai` SDK (v1). Set `MISTRAL_API_KEY` in `.env`.
- Optional: Enable MarkItDown image descriptions with an OpenAI-compatible key (`OPENAI_API_KEY`) and set `MARKITDOWN_USE_LLM=true`.

## Configuration Reference (.env)

- `MISTRAL_API_KEY`: Required for OCR (mode 4 and Hybrid OCR).
- `MISTRAL_OCR_MODEL` (default `mistral-ocr-latest`): OCR model id.
- `MISTRAL_INCLUDE_IMAGES` (true/false): Include base64 images in OCR response and embed in Markdown.
- `SAVE_MISTRAL_JSON` (true/false): Save raw OCR JSONs under `logs/` for troubleshooting.
- `POPPLER_PATH` (Windows only): Path to Poppler `bin` for PDF→image and per‑page OCR fallback.
- Optional (MarkItDown extras): `MARKITDOWN_USE_LLM`, `MARKITDOWN_LLM_MODEL`, `OPENAI_API_KEY`, `AZURE_DOC_INTEL_ENDPOINT`, `AZURE_DOC_INTEL_KEY`, `MARKITDOWN_ENABLE_PLUGINS`.

Note: All output folders (`input/`, `output_md/`, `output_txt/`, `output_images/`, `logs/`, `cache/`) are auto‑created and safe to delete. They regenerate on the next run.

## Troubleshooting

- 422 during OCR upload: The Files API must use `purpose="ocr"`. The code sets this; update and rerun if you see JSONL errors.
- “Mistral client not initialized”: Ensure `.env` has `MISTRAL_API_KEY` and you ran `run_converter.bat`/`quick_start.sh` or activated `env`.
- Weak first page OCR on PDFs: We automatically re‑OCR weak pages via `pages=[index]`, and if Poppler is available we render the page to an image and retry OCR.
- Poppler missing: Option 6 and image‑based re‑OCR fallbacks require Poppler. Set `POPPLER_PATH` on Windows.
- Camelot lattice mode not working: Install Ghostscript and ensure it’s on PATH.
- Where are images saved?: OCR images go to `output_images/`; Option 6 renders to `output_images/<pdfname>_pages/`.
- Clear cache/logs: Safe to delete `cache/` and `logs/`; they’ll be recreated. Deleting `cache/` forces fresh OCR.

## Security

- Do not commit `.env` or share API keys.
- Logs may include OCR content if `SAVE_MISTRAL_JSON=true`. Treat as sensitive.

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
