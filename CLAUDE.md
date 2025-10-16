# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Enhanced Document Converter v2.1** - A sophisticated Python document processing tool that intelligently combines **Microsoft MarkItDown** (local processing) with **Mistral Document AI OCR** (cloud-based AI) for high-quality document conversion to Markdown and plain text.

**Key Strategy**: Dual-engine approach that uses each tool where it excels - MarkItDown for fast local conversion, Mistral OCR for high-accuracy text extraction from images and complex PDFs.

## Quick Start

### Setup and Running
```bash
# Windows (recommended)
run_converter.bat              # Auto-setup: creates venv, installs dependencies, launches app

# macOS/Linux
bash quick_start.sh            # Setup: creates venv, installs dependencies, runs smoke test
source env/bin/activate        # Then activate and run
python main.py

# Manual setup
python -m venv env
env\Scripts\activate           # Windows
source env/bin/activate        # macOS/Linux
pip install -r requirements.txt
cp .env.example .env           # Configure MISTRAL_API_KEY
python main.py
```

### System Requirements
- **Python**: 3.10+ (required by MarkItDown)
- **Ghostscript**: Critical for optimal PDF table extraction (prevents column truncation in wide tables)
  - Windows: Download from ghostscript.com, add to PATH
  - macOS: `brew install ghostscript`
  - Linux: `sudo apt-get install ghostscript`
  - Verify: `gs --version` (or `gswin64c --version` on Windows)
- **Poppler**: Required for PDF-to-image conversion and improved OCR fallback
  - Windows: Download binaries, set `POPPLER_PATH` in .env
  - macOS: `brew install poppler`
  - Linux: Usually pre-installed
- **ffmpeg** (optional): For audio/video transcription

## High-Level Architecture

### Processing Pipeline Overview

The converter uses an intelligent multi-strategy approach:

```
Input Files → Strategy Selection → Processing Engine(s) → Output + Caching
```

**Core Strategy Selection** (`utils.py:get_enhanced_file_strategy`):
- **Office docs** (.docx, .pptx, .xlsx) → MarkItDown only
- **Images** (.jpg, .png, .tiff) → Mistral OCR only
- **PDFs** → Hybrid (MarkItDown + Local Tables + Mistral OCR)
- **Audio/Video** → Transcription mode
- **Text/Web** (.html, .md, .txt) → MarkItDown only

### Module Architecture

The codebase is organized into logical layers:

```
main.py (Orchestration)
    ↓
    ├─→ config.py (Environment & Configuration)
    │
    ├─→ local_converter.py (MarkItDown Integration)
    │   ├─ run_markitdown_enhanced() - Primary conversion
    │   ├─ extract_tables_to_markdown() - PDF table extraction
    │   └─ pdfs_to_images() - PDF rendering
    │
    ├─→ mistral_converter.py (Mistral OCR Integration)
    │   ├─ mistral_ocr_file_enhanced() - OCR processing
    │   └─ process_mistral_response_enhanced() - Response handling
    │
    └─→ utils.py (Shared Infrastructure)
        ├─ IntelligentCache - Content-based caching
        ├─ ConcurrentProcessor - Parallel file processing
        ├─ MetadataTracker - Session & performance tracking
        └─ ErrorRecoveryManager - Retry logic
```

### Hybrid Processing Pipeline (Mode 1 - Recommended for PDFs)

The most powerful feature - combines strengths of multiple engines:

1. **File Analysis**: Determine complexity, size, optimal strategy
2. **MarkItDown Processing**: Extract main text content and structure
3. **Local Table Extraction**:
   - Uses `pdfplumber` (line-based detection)
   - Falls back to `camelot` (lattice/stream modes with Ghostscript)
   - Reshapes financial tables (month normalization, deduplication)
4. **Mistral OCR Processing**: High-accuracy text and layout extraction
5. **Intelligent Gating**: Collapses MarkItDown content when OCR tables are superior
6. **Combined Output**: Creates `_combined.md` with all sections

**Output Files for PDFs**:
- `<name>_combined.md` - Aggregated report (main output)
- `<name>_tables_all.md` - All detected tables
- `<name>_tables_full.md` - Coalesced cross-page table
- `<name>_tables_wide.md` - Wide format (for month-based financial data)
- `<name>_mistral_ocr.md` - OCR-only content
- `.txt` versions for all above

### Intelligent Caching System

**Location**: `cache/` directory
**Implementation**: `utils.py:IntelligentCache`

**Cache Key Strategy**:
```python
SHA256(file_size + file_mtime + content_sample) +
processing_method +
SHA256(parameters)
= Unique cache identifier
```

**Benefits**:
- Prevents redundant API calls (saves costs)
- Content-based (detects file changes)
- Time-aware expiration (24h default, configurable via `CACHE_DURATION_HOURS`)
- Reduces processing time by 90%+ on cache hits

**Management**: Safe to delete `cache/` directory anytime - will regenerate

### Table Extraction Pipeline

**Critical Architecture Decision**: Multi-engine approach to handle various PDF types

```
PDF Input
    ↓
1. pdfplumber extraction (line-based, fast)
    ↓
2. Camelot lattice mode (Ghostscript required)
    ↓
3. Camelot stream mode (fallback)
    ↓
4. Financial table reshaping:
   - Multi-row header reconstruction
   - Month column normalization (fuzzy matching)
   - Account code/title splitting
   - Amount normalization (handles OCR artifacts)
   - Cross-page deduplication
   - Spurious row filtering
    ↓
Output: Multiple formats (all, full, wide, compact)
```

**Why Ghostscript is Critical**: Without it, Camelot uses "stream mode" which often misses rightmost columns in wide tables, causing incomplete data extraction.

### Model Selection Strategy

**Auto-Selection** (`mistral_converter.py`, when `MISTRAL_AUTO_MODEL_SELECTION=true`):
- **PDFs with tables** → `mistral-ocr-latest`
- **Code documents** → `codestral-latest`
- **Images (complex)** → `pixtral-large-latest`
- **Multimodal** → `mistral-medium-latest`
- **Unknown** → Configurable default

**Priority Order** (configurable via `MISTRAL_PREFERRED_MODELS`):
1. `mistral-ocr-latest` - Best for PDFs with tables
2. `pixtral-large-latest` - Complex images
3. `mistral-medium-latest` - Multimodal documents
4. `codestral-latest` - Code-heavy documents

## Processing Modes

The application is menu-driven (no complex CLI commands). Place files in `input/`, run the app, select a mode:

### Mode Selection Guide

| Mode | Use Case | Processing Strategy | Typical Output |
|------|----------|-------------------|----------------|
| 1 | **Best default** - PDFs with tables/images | Hybrid (all engines) | `_combined.md` with all sections |
| 2 | Many files needing optimization | Concurrent + caching | Multiple outputs + metadata |
| 3 | Office/web docs, fast local only | MarkItDown only | `<name>.md` |
| 4 | Scanned PDFs, images, low-quality docs | Mistral OCR only | `<name>_mistral_ocr.md` + images |
| 5 | Audio, video, YouTube URLs | Transcription | `<name>_transcription.md` |
| 6 | Simple batch by file type | Standard batch | Multiple outputs |
| 7 | PDF visual review, OCR fallback | PDF→Images utility | `output_images/<name>_pages/` |
| 8 | Diagnostics, optimization tips | System status | Console summary |

### Mode Details

**Mode 1 - Hybrid (Intelligent Processing)**:
- Automatically selects optimal strategy per file
- For PDFs: Produces combined output with MarkItDown + tables + OCR
- Implements intelligent gating (collapses sections when OCR is superior)

**Mode 2 - Enhanced Batch (Maximum Performance)**:
- Concurrent processing with thread pools
- File categorization (API vs. local)
- Rate limiting for API calls (1/sec)
- Caching to avoid reprocessing
- Session metadata and recommendations

**Mode 4 - Mistral OCR Only**:
- Page-by-page OCR with quality assessment
- Automatic poor-quality page reprocessing
- Two-stage fallback: file_id retry → image rendering + retry
- Image extraction with metadata
- Structured data output (JSON metadata)

**Mode 8 - System Status**:
- Configuration verification (API keys, features)
- Cache statistics (hit rate, size, savings)
- Input directory analysis
- Performance recommendations
- System resource monitoring

## Configuration System

**Location**: `.env` file (copy from `.env.example`)

### Critical Settings

```bash
# Required for OCR modes
MISTRAL_API_KEY=sk-...

# Model selection (August 2025 models)
MISTRAL_OCR_MODEL=mistral-ocr-latest
MISTRAL_AUTO_MODEL_SELECTION=true
MISTRAL_PREFERRED_MODELS=mistral-ocr-latest,pixtral-large-latest,mistral-medium-latest,codestral-latest

# Processing options
MISTRAL_INCLUDE_IMAGES=true
MISTRAL_INCLUDE_IMAGE_ANNOTATIONS=true
GATE_MARKITDOWN_WHEN_OCR_GOOD=true

# Performance
CACHE_DURATION_HOURS=24
BATCH_SIZE=5
MAX_RETRIES=3
MARKITDOWN_WORKERS=4

# Optional: Enhanced features
MARKITDOWN_USE_LLM=false           # Requires OPENAI_API_KEY
MARKITDOWN_ENABLE_PLUGINS=false    # For audio/video transcription
MARKITDOWN_ADVANCED_TABLES=true
MARKITDOWN_PARALLEL_PROCESSING=true

# System paths (Windows)
POPPLER_PATH=C:/path/to/poppler-23.08.0/bin
```

### Environment Variable Helpers

**Implementation**: `config.py` provides type-safe helpers:
- `get_env_bool()` - Boolean configuration
- `get_env_int()` - Integer with defaults
- `get_env_list()` - Comma-separated lists
- `get_env_str()` - String configuration

**Fallback Parser**: If `python-dotenv` unavailable, uses built-in minimal key=value parser

## Important Processing Patterns

### Error Recovery Strategy

**Implementation**: `utils.py:ErrorRecoveryManager`

**Transient Errors** (automatically retried):
- HTTP 408, 429, 502-504
- Timeouts, connection resets
- Rate limits

**Retry Logic**:
- Exponential backoff: 1s → 2s → 4s
- Configurable max retries (default: 3)
- Random jitter to prevent thundering herd

**Mistral OCR Fallbacks** (per-page):
1. Initial OCR attempt
2. If weak quality → Retry with `pages=[index]` parameter
3. If still weak + Poppler available → Render page to image, retry OCR

### Concurrent Processing

**Implementation**: `utils.py:ConcurrentProcessor`

**Strategy**:
- **Local files**: Thread pool (configurable, default: 4-8 workers)
- **API files**: Sequential with rate limiting (1 req/sec)
- **Categorization**: Auto-detects which files need API calls

**Performance**: Typical 5-10x speedup for large local file batches

### Metadata Tracking

**Implementation**: `utils.py:MetadataTracker`

**Tracks**:
- Per-file processing metrics (time, size, strategy)
- Error patterns and frequency
- Cache hit rates and savings
- Session-level statistics
- Performance recommendations

**Output**: `logs/metadata/` directory, JSON format

## Output Directory Structure

```
output_md/          # Markdown output (primary)
output_txt/         # Plain text (search-friendly)
output_images/      # Extracted images from OCR, PDF page renders
logs/               # Session metadata, optional OCR JSON dumps
cache/              # Intelligent cache storage (pickle + metadata)
input/              # Source files (user-managed)
```

**All directories auto-created** - Safe to delete `logs/` and `cache/` anytime

## Dependencies and Versions

**Core** (from `requirements.txt`):
```
markitdown[all]>=0.1.3          # Microsoft's converter
mistralai>=1.0.0,<2.0.0         # Mistral SDK v1
pdfplumber>=0.10.0              # PDF text/table extraction
camelot-py[cv]>=0.11.0          # Advanced PDF table extraction
pandas>=2.0.0                   # Table manipulation
Pillow>=10.0.0                  # Image processing
pdf2image>=1.16.0               # PDF rendering
```

**Optional but Recommended**:
```
openai>=1.30.0                  # For LLM image captions
psutil>=5.9.0                   # System monitoring
ffmpeg-python>=0.2.0            # Audio/video transcription
beautifulsoup4>=4.12.0          # Enhanced HTML
```

## Development Patterns

### Adding a New Processing Mode

1. **Define mode function** in `main.py`
2. **Add to menu** in `show_menu_and_get_choice()`
3. **Implement strategy** using existing converters
4. **Update mode mapping** in `_mode_actions` dict
5. **Add metadata tracking** using `MetadataTracker`

### Extending Table Extraction

**Key Function**: `local_converter.py:extract_tables_to_markdown()`

**Reshape Logic**: `local_converter.py:reshape_financial_table()`
- Handles multi-row headers
- Normalizes month columns (fuzzy matching against `config.MONTHS`)
- Splits account codes from titles
- Normalizes amounts (removes OCR artifacts)

**To extend**: Modify reshape logic or add new table detection algorithms

### Adding a New Model

1. **Update** `.env.example` with model ID
2. **Add to** `MISTRAL_PREFERRED_MODELS` default in `config.py`
3. **Update** auto-selection logic in `mistral_converter.py:select_optimal_model()`
4. **Test** with representative files

## Troubleshooting Common Issues

**"Mistral client not initialized"**:
- Ensure `MISTRAL_API_KEY` set in `.env`
- Verify environment loaded (check with Mode 8)

**Incomplete table columns**:
- Install Ghostscript and verify on PATH
- Without Ghostscript, rightmost columns often missing

**Weak OCR results**:
- Check if Poppler installed (enables image-based fallback)
- Try Mode 4 with image preprocessing enabled

**Cache not working**:
- Check `cache/` directory exists
- Verify `CACHE_DURATION_HOURS` not set to 0
- Use Mode 8 to view cache statistics

**Slow processing**:
- Use Mode 2 for concurrent processing
- Increase `MARKITDOWN_WORKERS` for local files
- Check network latency for API calls

## Key Constants and Defaults

**File Size Thresholds**:
- `LARGE_FILE_THRESHOLD_MB=45` - Files larger are uploaded to Mistral API (not inline)
- `MARKITDOWN_MAX_FILE_SIZE_MB=100` - Maximum file size for local processing

**Timeouts**:
- `MISTRAL_HTTP_TIMEOUT=300` - API request timeout (5 minutes)

**Financial Table Constants** (`config.py`):
- `MONTHS` - Full month names for normalization
- `M_SHORT` - Short month names for fuzzy matching

## Latest Updates (August 2025)

**New Mistral Models**:
- `mistral-medium-2508` - Multimodal with images/text
- `codestral-2508` - Advanced coding model
- `pixtral-large-2411` - Frontier multimodal
- `magistral-medium-2507` - Frontier reasoning

**Enhanced Features**:
- Intelligent model selection
- Function calling support
- Structured outputs with JSON schema
- Image optimization and preprocessing
- Enhanced parallel processing

**MarkItDown v0.1.3**:
- MCP server integration
- Enhanced plugin system
- EPub support
- Improved audio/video transcription
