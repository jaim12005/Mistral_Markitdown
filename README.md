# Enhanced Document Converter

![Tests](https://github.com/jaim12005/Mistral_Markitdown/actions/workflows/test.yml/badge.svg)
![Linting](https://github.com/jaim12005/Mistral_Markitdown/actions/workflows/lint.yml/badge.svg)
![Security](https://github.com/jaim12005/Mistral_Markitdown/actions/workflows/security.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A document conversion system combining Microsoft **MarkItDown** (local) with **Mistral AI OCR** (cloud) for optimal document processing. Features smart auto-routing, advanced PDF table extraction, intelligent caching, and concurrent batch processing.

## Getting Started

### Prerequisites

- Python 3.10+
- Mistral API key (optional — only needed for cloud OCR/QnA/Batch features): https://console.mistral.ai/api-keys/
  - Without a key, local MarkItDown conversion (mode 2) and PDF-to-images (mode 4) work fully.

### Installation

```bash
python -m venv env
source env/bin/activate   # Windows: env\Scripts\activate
pip install -r requirements.txt
```

Or install as a package:

```bash
pip install .
```

Or use the platform scripts:

```bash
# macOS/Linux
chmod +x scripts/quick_start.sh && ./scripts/quick_start.sh

# Windows
scripts\run_converter.bat
```

Optional extras (audio transcription, YouTube, markitdown-ocr; see `requirements-optional.txt`):

```bash
pip install -r requirements-optional.txt
```

### Configuration

Create a `.env` file in the project root (see `.env.example` for all options):

```ini
MISTRAL_API_KEY="your_api_key_here"
```

### Usage

Place files in `input/`, then run:

```bash
python main.py              # Interactive menu
python main.py --mode smart # CLI: auto-route by file type
python main.py --test       # Verify setup
```

## Conversion Modes

| #   | Mode                      | API?       | Description                                                                         |
| --- | ------------------------- | ---------- | ----------------------------------------------------------------------------------- |
| 1   | **Convert (Smart)**       | If key set | Auto-picks MarkItDown or Mistral OCR per file type. PDFs also get table extraction. |
| 2   | **Convert (MarkItDown)**  | No         | Force local conversion. Fast, free, supports 30+ formats.                           |
| 3   | **Convert (Mistral OCR)** | Yes        | Force cloud OCR. Best for scanned docs, complex layouts, equations.                 |
| 4   | **PDF to Images**         | No         | Render each PDF page to PNG/JPEG at configurable DPI.                               |
| 5   | **Document QnA**          | Yes        | Ask questions about a document in natural language.                                 |
| 6   | **Batch OCR**             | Yes        | Submit to Mistral Batch API at 50% cost reduction.                                  |
| 7   | **System Status**         | No         | Cache stats, config info, diagnostics.                                              |
| 8   | **Maintenance**           | No         | Clear expired cache, clean up old Mistral uploads.                                  |

Smart mode prints its routing decisions before processing:

```
Routing plan:
  scan.pdf                    -> Mistral OCR (scanned + table extraction)
  report.docx                 -> MarkItDown (local)
  notes.txt                   -> MarkItDown (local)
```

All conversion modes process multiple files concurrently when more than one is selected.

### CLI Reference

```bash
python main.py --mode smart        # Smart auto-routing (recommended)
python main.py --mode markitdown   # Force MarkItDown
python main.py --mode mistral_ocr  # Force Mistral OCR
python main.py --mode pdf_to_images
python main.py --mode qna
python main.py --mode batch_ocr
python main.py --mode status
python main.py --mode maintenance  # Clear cache and old uploads
python main.py --no-interactive    # Process all files in input/ without prompts
```

## Supported Formats

| Category  | Formats                                         |
| --------- | ----------------------------------------------- |
| Documents | PDF, DOCX, DOC, PPTX, PPT, XLSX, XLS, RTF, MSG  |
| Web       | HTML, HTM, XML, RSS                             |
| Data      | CSV, JSON, TXT                                  |
| Images    | PNG, JPG, JPEG, GIF, BMP, TIFF, WEBP, AVIF      |
| Books     | EPUB                                            |
| Notebooks | IPYNB (Jupyter)                                 |
| Archives  | ZIP (recursive extraction)                      |
| Audio     | MP3, WAV, M4A, FLAC (requires plugins + ffmpeg) |

## Architecture

### Dual-Engine Design

- **MarkItDown** -- fast, local, free. Handles standard document formats natively.
- **Mistral OCR** -- AI-powered cloud OCR via the Files API with signed URLs. Understands complex layouts, tables, equations, multi-column text with ~95% accuracy.

### Processing Pipeline (Smart Mode)

1. Route each file to MarkItDown or Mistral OCR based on content analysis (text layer detection for PDFs, extension for other types)
2. For PDFs: run pdfplumber-based multi-strategy table extraction with automatic post-processing
3. OCR quality assessment (0-100 scoring) with automatic weak page re-processing
4. Results cached by SHA-256 content hash (24-hour TTL, second run = $0)

### Cost Optimization

- **Caching**: SHA-256 file hashing with 24-hour persistence. Reprocessing the same files costs nothing.
- **Batch OCR**: 50% cost reduction for 10+ documents via Mistral Batch API.
- **Auto-cleanup**: Old uploaded files removed from Mistral after 7 days (configurable).

## Key Features

### PDF Table Extraction

Advanced multi-strategy extraction for any tabular data:

- **pdfplumber line-based** (grid tables) + **pdfplumber text-based** (borderless tables)
- Automatic post-processing: split-header repair, merged cell detection, page artifact removal, cross-page table coalescing
- Financial extras: merged currency cell splitting (`"$ 1,234.56 $ 5,678.90"` → two cells), month header normalization
- Deduplication and cross-page table coalescing

### OCR Quality Assessment

Automated 0-100 scoring evaluates every OCR result:

- Text density, token uniqueness, repeated phrase detection, average line length (aggregate stats still report digit counts)
- Pages scoring below threshold are automatically re-processed
- Quality score included in output for transparency
- Thread-safe Mistral client singleton ensures safe concurrent usage

Configure via `.env`:

```ini
ENABLE_OCR_QUALITY_ASSESSMENT=true
ENABLE_OCR_WEAK_PAGE_IMPROVEMENT=true
```

### Structured Data Extraction

Extract structured JSON from documents using predefined schemas:

```ini
MISTRAL_ENABLE_STRUCTURED_OUTPUT=true
MISTRAL_DOCUMENT_SCHEMA_TYPE=auto   # invoice, financial_statement, contract, form, generic
MISTRAL_ENABLE_BBOX_ANNOTATION=false
MISTRAL_ENABLE_DOCUMENT_ANNOTATION=false
```

Built-in schemas for invoices, financial statements, contracts, forms, and generic documents. Custom schemas can be added in `schemas.py`.

### Document QnA

Interactive natural language queries against document content:

```bash
python main.py --mode qna
# Select a file, then ask questions interactively
```

Uses Mistral chat completion with `document_url` content type. Configurable model, system prompt, and page/image limits.

When using **public URL** mode, the app performs client-side HTTPS/DNS validation as a **best-effort** guard only (it cannot prevent DNS rebinding or all SSRF cases). Prefer uploading local files for QnA, or restrict network egress, in high-assurance environments.

#### Streaming QnA

For real-time token-by-token output, use the streaming variant:

```python
from mistral_converter import query_document_stream

success, stream, error = query_document_stream(
    "https://arxiv.org/pdf/1805.04770",
    "What is the main contribution of this paper?"
)

if success:
    for chunk in stream:
        if chunk.data.choices and chunk.data.choices[0].delta.content:
            print(chunk.data.choices[0].delta.content, end="", flush=True)
    print()
```

The interactive QnA mode (mode 5) uses streaming by default.

### MarkItDown LLM Descriptions

MarkItDown can use Mistral's vision models for AI-powered image descriptions within documents:

```ini
MARKITDOWN_ENABLE_LLM_DESCRIPTIONS=false
MARKITDOWN_LLM_MODEL=pixtral-large-latest
```

## System Requirements

### Python Dependencies

| File                        | Purpose                                                                |
| --------------------------- | ---------------------------------------------------------------------- |
| `requirements.txt`          | Core: MarkItDown, Mistral SDK, Pydantic, pdfplumber, pdf2image, Pillow |
| `requirements-dev.txt`      | Dev: pytest, flake8, black, isort, pip-audit                           |
| `requirements-optional.txt` | Optional: audio transcription, YouTube, OpenAI client, markitdown-ocr  |

### System Binaries

| Binary   | Required For             | Install                                                                                                                    |
| -------- | ------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| Poppler  | PDF to images            | `brew install poppler` / `apt install poppler-utils` / [Windows binary](https://github.com/oschwartz10612/poppler-windows) |
| ffmpeg   | Audio transcription      | `brew install ffmpeg` / `apt install ffmpeg`                                                                               |
| ExifTool | EXIF metadata extraction | Optional, set `MARKITDOWN_EXIFTOOL_PATH`                                                                                   |

On Windows, set the Poppler path in `.env`:

```ini
POPPLER_PATH="C:/path/to/poppler/bin"
```

## Output Structure

```
output_md/       # Markdown files (.md)
output_txt/      # Plain text exports (.txt)
output_images/   # Extracted images and PDF page renders
logs/            # Processing logs and batch metadata
cache/           # OCR result cache (SHA-256 indexed)
```

## Configuration

All settings are in `.env`. See `.env.example` for the complete reference with 70+ documented options.

For the full configuration guide: **[CONFIGURATION.md](CONFIGURATION.md)**

## Documentation

| Guide                                            | Description                                   |
| ------------------------------------------------ | --------------------------------------------- |
| **[CONFIGURATION.md](CONFIGURATION.md)**         | Complete configuration reference              |
| **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** | Architecture and design details               |
| **[KNOWN_ISSUES.md](KNOWN_ISSUES.md)**           | Known issues, limitations, troubleshooting    |
| **[CONTRIBUTING.md](CONTRIBUTING.md)**           | Development setup and contribution guidelines |
| **[CHANGELOG.md](CHANGELOG.md)**                 | Release history and version changes           |
| **[SECURITY.md](SECURITY.md)**                   | Security policy and vulnerability reporting   |

## Upstream Alignment

- MarkItDown: `>=0.1.5` (https://github.com/microsoft/markitdown)
- Mistral Python SDK: `==2.1.3` (https://github.com/mistralai/client-python)
- Mistral OCR docs: https://docs.mistral.ai/capabilities/document_ai/basic_ocr/
- Mistral Batch API: https://docs.mistral.ai/capabilities/batch/

## License

See [LICENSE](LICENSE).
