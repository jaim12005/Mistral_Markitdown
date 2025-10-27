# Dependencies Guide

Complete reference for all dependencies used in Enhanced Document Converter v2.1.

## Table of Contents

- [Installation Quick Start](#installation-quick-start)
- [Core Dependencies](#core-dependencies)
- [MarkItDown Optional Extras](#markitdown-optional-extras)
- [Enhanced Features](#enhanced-features)
- [Development Dependencies](#development-dependencies)
- [System Requirements](#system-requirements)
- [Troubleshooting](#troubleshooting)

---

## Installation Quick Start

### Minimal Installation (Required Only)

```bash
pip install -r requirements.txt
```

Provides:
- ✓ Core document conversion (PDF, DOCX, PPTX, XLSX, HTML, images)
- ✓ Mistral AI OCR
- ✓ Advanced table extraction
- ✓ All 8 conversion modes (except audio/YouTube transcription)

### Full Installation (All Features)

```bash
pip install -r requirements.txt -r requirements-optional.txt
```

Adds:
- ✓ Audio/video transcription
- ✓ YouTube transcript fetching
- ✓ Azure Document Intelligence
- ✓ Outlook MSG file support

### Development Installation

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Adds:
- ✓ Testing framework (pytest)
- ✓ Linters (flake8, black, pylint)
- ✓ Type checking (mypy)
- ✓ Documentation tools

---

## Core Dependencies

These are **REQUIRED** for basic operation and are installed via `requirements.txt`.

### Document Processing Core

| Package | Version | Purpose | Documentation |
|---------|---------|---------|---------------|
| **markitdown** | ≥0.1.3 | Microsoft's document-to-markdown converter | [GitHub](https://github.com/microsoft/markitdown) |
| **mistralai** | ≥1.0.0 | Mistral AI SDK for OCR and document AI | [Docs](https://docs.mistral.ai) |
| **python-dotenv** | ≥1.0.0 | Environment variable management | [PyPI](https://pypi.org/project/python-dotenv/) |

**MarkItDown Auto-Installed Dependencies:**
- `beautifulsoup4` - HTML parsing
- `charset-normalizer` - Character encoding detection
- `defusedxml` - Secure XML parsing
- `magika` - File type detection
- `markdownify` - HTML to Markdown conversion
- `requests` - HTTP client
- `pdfminer-six` - PDF text extraction
- `mammoth` - DOCX to HTML/Markdown

### Advanced Table Extraction

| Package | Version | Purpose | System Requirements |
|---------|---------|---------|---------------------|
| **pdfplumber** | ≥0.10.0 | Fast PDF table extraction (baseline) | None |
| **camelot-py[cv]** | ≥0.11.0 | Advanced table extraction (lattice + stream modes) | Ghostscript binary |
| **opencv-python** | ≥4.8.0 | Image processing for visual table detection | None |

**Camelot Tuning:**
- Lattice mode: Detects grid lines (`line_scale=40`, `shift_text=['l','t']`)
- Stream mode: Detects whitespace (`edge_tol=50`, `row_tol=5`)
- Financial document optimization: Fixes merged currency cells, normalizes headers

### Image Processing

| Package | Version | Purpose | System Requirements |
|---------|---------|---------|---------------------|
| **pdf2image** | ≥1.16.0 | Convert PDF pages to PNG images (Mode 7) | Poppler binaries |
| **Pillow** | ≥10.0.0 | Image optimization and preprocessing | None |

### Performance & Utilities

| Package | Version | Purpose |
|---------|---------|---------|
| **aiofiles** | ≥23.0.0 | Async file I/O for concurrent batch processing |
| **psutil** | ≥5.9.0 | System resource monitoring |
| **requests** | ≥2.31.0 | HTTP client (if not installed by MarkItDown) |
| **urllib3** | ≥2.0.0 | HTTP connection pooling |
| **tabulate** | ≥0.9.0 | Table formatting for console output |

### Office Document Support

| Package | Version | Purpose | MarkItDown Extra |
|---------|---------|---------|------------------|
| **lxml** | ≥4.9.0 | XML processing for DOCX | [docx] |
| **python-pptx** | ≥0.6.23 | PowerPoint file support | [pptx] |
| **openpyxl** | ≥3.1.2 | Modern Excel (.xlsx) support | [xlsx] |
| **xlrd** | ≥2.0.1 | Legacy Excel (.xls) support | [xls] |

---

## MarkItDown Optional Extras

These are **OPTIONAL** and provide extended capabilities. Install via `requirements-optional.txt`.

### Audio Transcription

**MarkItDown Extra:** `pip install markitdown[audio-transcription]`

| Package | Version | Purpose |
|---------|---------|---------|
| **pydub** | ≥0.25.1 | Audio file processing and format conversion |
| **SpeechRecognition** | ≥3.10.0 | Speech-to-text conversion |
| **ffmpeg-python** | ≥0.2.0 | FFmpeg Python wrapper (optional) |

**System Requirements:**
- **ffmpeg binary** must be installed:
  - Windows: Download from [ffmpeg.org](https://www.gyan.dev/ffmpeg/builds/)
  - macOS: `brew install ffmpeg`
  - Linux: `apt-get install ffmpeg`

**Configuration:**
- Set `MARKITDOWN_ENABLE_PLUGINS=true` in `.env`

**Supported Formats:**
- Audio: MP3, WAV, M4A, FLAC
- Video: MP4, AVI (extracts audio track)

### YouTube Transcription

**MarkItDown Extra:** `pip install markitdown[youtube-transcription]`

| Package | Version | Purpose |
|---------|---------|---------|
| **youtube-transcript-api** | ≥0.6.1 | Fetch YouTube video transcripts/subtitles |

**Configuration:**
- Set `MARKITDOWN_ENABLE_PLUGINS=true` in `.env`

**Usage:**
```bash
markitdown https://www.youtube.com/watch?v=VIDEO_ID > transcript.md
```

### Azure Document Intelligence

**MarkItDown Extra:** `pip install markitdown[az-doc-intel]`

| Package | Version | Purpose |
|---------|---------|---------|
| **azure-ai-documentintelligence** | ≥1.0.0 | Azure AI Document Intelligence client |
| **azure-identity** | ≥1.15.0 | Azure authentication |

**Configuration:**
1. Create Azure Document Intelligence resource at [portal.azure.com](https://portal.azure.com/)
2. Set in `.env`:
   ```ini
   AZURE_DOC_INTEL_ENDPOINT="https://YOUR_RESOURCE.cognitiveservices.azure.com/"
   AZURE_DOC_INTEL_KEY="your_api_key_here"
   ```

**Benefits:**
- Enhanced PDF layout analysis
- Better table extraction for complex documents
- Improved OCR for scanned documents

### Outlook Message Files

**MarkItDown Extra:** `pip install markitdown[outlook]`

| Package | Version | Purpose |
|---------|---------|---------|
| **olefile** | ≥0.47 | Parse Outlook .msg files |

**Supported Formats:**
- `.msg` - Outlook message files

---

## Enhanced Features

These dependencies are **NOT** part of MarkItDown but are used for enhanced functionality specific to this project.

### Intelligent Caching System

- **SHA-256 file hashing** for change detection
- **24-hour cache persistence** (configurable)
- **$0 API costs** on cache hits
- No additional dependencies (uses Python stdlib `hashlib`)

### OCR Quality Assessment

- **Automated 0-100 scoring** using heuristics
- **Weak page detection** and automatic re-processing
- **Consecutive duplicate cleaning** (removes OCR artifacts)
- No additional dependencies (pure Python implementation)

### Concurrent Batch Processing

- **ThreadPoolExecutor** for concurrent file processing
- **Configurable workers** via `MAX_CONCURRENT_FILES`
- **Metadata tracking** with processing statistics
- Dependencies: `aiofiles` (for async I/O)

---

## Development Dependencies

Install via `requirements-dev.txt` for development and testing.

### Testing Framework

| Package | Version | Purpose |
|---------|---------|---------|
| **pytest** | ≥7.4.0 | Test framework |
| **pytest-cov** | ≥4.1.0 | Code coverage |
| **pytest-mock** | ≥3.11.0 | Mocking utilities |
| **pytest-asyncio** | ≥0.21.0 | Async test support |
| **pytest-xdist** | ≥3.3.0 | Parallel test execution |

### Code Quality

| Package | Version | Purpose |
|---------|---------|---------|
| **flake8** | ≥6.1.0 | Linting |
| **black** | ≥23.7.0 | Code formatting |
| **isort** | ≥5.12.0 | Import sorting |
| **pylint** | ≥3.0.0 | Static analysis |

### Type Checking

| Package | Version | Purpose |
|---------|---------|---------|
| **mypy** | ≥1.5.0 | Static type checker |
| **types-requests** | ≥2.31.0 | Type stubs for requests |
| **types-Pillow** | ≥10.0.0 | Type stubs for Pillow |

### Development Tools

| Package | Version | Purpose |
|---------|---------|---------|
| **ipython** | ≥8.14.0 | Interactive Python shell |
| **ipdb** | ≥0.13.13 | Interactive debugger |
| **pre-commit** | ≥3.3.0 | Git pre-commit hooks |

---

## System Requirements

### Required System Binaries

| Binary | Required For | Installation |
|--------|-------------|-------------|
| **Poppler** | PDF to image conversion (Mode 7) | [Windows](https://github.com/oschwartz10612/poppler-windows/releases), macOS: `brew install poppler`, Linux: `apt-get install poppler-utils` |
| **Ghostscript** | Camelot table extraction | [Download](https://ghostscript.com/releases/gsdnld.html) or `brew install ghostscript` |
| **ffmpeg** | Audio transcription (optional) | [Download](https://ffmpeg.org/download.html) or `brew install ffmpeg` |

### Python Version

- **Python 3.10+** required
- Tested on: 3.10, 3.11, 3.12

### Operating Systems

- ✓ Windows 10/11
- ✓ macOS 11+
- ✓ Linux (Ubuntu 20.04+, Debian, RHEL)

---

## Troubleshooting

### Common Issues

#### "MISTRAL_API_KEY not set"

**Solution:**
1. Copy `.env.example` to `.env`
2. Get API key from https://console.mistral.ai/api-keys/
3. Set `MISTRAL_API_KEY` in `.env`

#### "pdf2image: Unable to get page count" (Windows)

**Cause:** Poppler not installed or path not configured

**Solution:**
1. Download Poppler: https://github.com/oschwartz10612/poppler-windows/releases
2. Extract to `C:\Program Files\poppler-XX.XX.X\`
3. Set in `.env`: `POPPLER_PATH="C:/Program Files/poppler-23.08.0/Library/bin"`

#### "Camelot table extraction failed"

**Cause:** Ghostscript not installed (required for PDF rendering)

**Solution:**
1. Download Ghostscript: https://ghostscript.com/releases/gsdnld.html
2. Install and ensure it's in system PATH
3. Restart terminal/IDE

#### "Audio transcription not working"

**Cause:** Missing ffmpeg binary or plugins not enabled

**Solution:**
1. Install ffmpeg binary (see System Requirements above)
2. Install optional dependencies: `pip install -r requirements-optional.txt`
3. Set in `.env`: `MARKITDOWN_ENABLE_PLUGINS=true`

#### "ImportError: No module named 'mammoth'"

**Cause:** MarkItDown not installed with [docx] extra

**Solution:**
- MarkItDown auto-installs mammoth as a core dependency
- Ensure `markitdown>=0.1.3` is installed: `pip install --upgrade markitdown`

### Dependency Conflicts

If you encounter dependency conflicts:

```bash
# Create fresh virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-optional.txt  # Optional
pip install -r requirements-dev.txt  # Development only
```

### Verifying Installation

Check all dependencies are installed correctly:

```bash
# Run system status check
python main.py --mode status

# Run test suite
pytest tests/ -v

# Verify MarkItDown installation
python -c "from markitdown import MarkItDown; print('MarkItDown OK')"

# Verify Mistral SDK
python -c "from mistralai import Mistral; print('Mistral SDK OK')"
```

---

## Package Purpose Quick Reference

| What I Want To Do | Install This |
|-------------------|-------------|
| Basic document conversion | `requirements.txt` |
| Audio/video transcription | `requirements-optional.txt` (audio section) |
| YouTube transcript fetching | `requirements-optional.txt` (YouTube section) |
| Azure Document Intelligence | `requirements-optional.txt` (Azure section) |
| Outlook MSG files | `requirements-optional.txt` (Outlook section) |
| Development/testing | `requirements-dev.txt` |
| Everything at once | `pip install markitdown[all] mistralai python-dotenv` + `requirements.txt` |

---

**Last Updated:** 2025-01-15  
**Version:** 2.1.1

For more information, see [README.md](README.md) and [CONTRIBUTING.md](CONTRIBUTING.md).
