# Enhanced Document Converter

This project provides a practical, cross‑platform document conversion tool that leverages **Microsoft MarkItDown** for fast, local conversion of various document types and **Mistral Document AI OCR** for high‑accuracy text extraction from images and complex PDFs. It is designed for quality results and an easy, predictable workflow on Windows and macOS.

## Quick Start

- Windows (recommended):
  - Run `run_converter.bat` (creates `env`, installs deps, launches app)
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
  - **Mistral OCR Only**: For high-accuracy OCR on images and scanned or complex PDFs.
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
- **Mistral OCR Only**: OCR for PDFs and images (uses Files API with `purpose="ocr"` and per‑page improvements where needed).
- **Batch Process Directory**: Simple batch by type.
- **Enhanced Batch**: Advanced concurrent processing with caching/metadata.
- **Convert PDFs to Images**: Renders each page to PNG under `output_images/<pdfname>_pages/`.

### Modes at a Glance

| Mode (menu)             | Flag                | Best for                           | Outputs (typical) |
|-------------------------|---------------------|------------------------------------|-------------------|
| Hybrid (1)              | `--mode hybrid`     | Best default; PDFs with tables/OCR | `output_md/<name>_combined.md`, `output_txt/` |
| Enhanced Batch (2)      | `--mode enhanced`   | Many files; concurrency + caching  | `output_md/`, `output_txt/`, `output_images/`, `logs/metadata/` |
| MarkItDown Only (3)     | `--mode markitdown` | Office/web/text files (local only) | `output_md/<name>.md`, `output_txt/<name>.txt` |
| Mistral OCR Only (4)    | `--mode ocr`        | Images and scanned PDFs            | `output_md/<name>_mistral_ocr.md`, `output_images/<name>_ocr/` (if images) + txt |
| Batch Process (5)       | `--mode batch`      | Simple batch by type               | `output_md/`, `output_txt/` |
| PDF → Images (6)        | n/a                 | Export pages as PNG                | `output_images/<pdfname>_pages/` |
| System Status (7)       | n/a                 | Environment and cache overview     | console only      |

### Input and Output

-   Place your files to be converted in the `input/` directory.
-   The converted Markdown files will be placed in the `output_md/` directory.
-   Plain text versions of the output will be in the `output_txt/` directory.
-   Images extracted during OCR will be in the `output_images/` directory.

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
- Optional (MarkItDown extras): `MARKITDOWN_USE_LLM`, `MARKITDOWN_LLM_MODEL`, `OPENAI_API_KEY`, `AZURE_DOC_INTEL_ENDPOINT`, `AZURE_DOC_INTEL_KEY`.

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
