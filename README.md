# Enhanced Document Converter v2.1

A powerful, production-ready document conversion system that combines Microsoft's **MarkItDown** with **Mistral AI's OCR** capabilities for optimal document processing. Features 8 specialized conversion modes, advanced table extraction, intelligent caching, and comprehensive batch processing.

## Features

### Core Capabilities

- **8 Conversion Modes**: From simple batch processing to advanced hybrid pipelines
- **Dual-Engine Processing**: MarkItDown (local, fast) + Mistral AI (cloud, accurate)
- **Advanced Table Extraction**: pdfplumber + camelot with multiple output formats
- **Intelligent Caching**: Hash-based caching to avoid reprocessing
- **Batch Processing**: Concurrent file processing with metadata tracking
- **Multi-Format Support**: PDF, DOCX, PPTX, XLSX, images, audio/video
- **OCR Quality Assessment**: Automated quality scoring and weak page detection
- **Per-Page OCR Improvement**: Automatic re-OCR of weak results

### Supported Formats

| Category | Formats |
|----------|---------|
| **Documents** | PDF, DOCX, DOC, PPTX, PPT, XLSX, XLS |
| **Web** | HTML, HTM, XML |
| **Data** | CSV, JSON |
| **Images** | PNG, JPG, JPEG, GIF, BMP, TIFF |
| **Books** | EPUB |
| **Audio/Video** | MP3, WAV, M4A, FLAC (requires plugins) |

## Quick Start

### Windows

```bash
# Double-click or run:
run_converter.bat
```

The script will:
1. Create virtual environment
2. Install all dependencies
3. Check configuration
4. Launch interactive menu

### macOS/Linux

```bash
chmod +x quick_start.sh
./quick_start.sh
```

### Manual Installation

```bash
# Create virtual environment
python -m venv env

# Activate environment
# Windows:
env\Scripts\activate
# macOS/Linux:
source env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run converter
python main.py
```

## 8 Conversion Modes

### Mode 1: HYBRID Mode (Intelligent Processing)

**Best for**: Maximum accuracy, complex PDFs, critical documents

Combines MarkItDown + advanced table extraction + Mistral OCR for comprehensive analysis:
- MarkItDown text extraction
- Advanced table extraction (pdfplumber + camelot with tuned parameters)
- **Mistral OCR analysis (works on ALL PDFs - both scanned and text-based)**
- Quality assessment provides transparency into OCR performance
- Creates `<filename>_combined.md` with all results and quality metrics

**Mistral OCR Capabilities**:
- ~95% accuracy across diverse document types
- Works on both scanned documents AND text-based PDFs
- Understands complex elements: tables, equations, multi-column layouts
- Extracts embedded images alongside text
- Quality score displayed for transparency (0-100)

**Output Files**:
- `<name>_combined.md`: Comprehensive aggregated report with quality summary
- `<name>.md`: MarkItDown conversion
- `<name>_mistral_ocr.md`: Mistral OCR results with page-by-page breakdown
- `<name>_tables_all.md`: All extracted tables with post-processing
- `<name>_ocr_metadata.json`: Structured metadata (if enabled)

**Usage**:
```bash
python main.py --mode hybrid
```

---

### Mode 2: ENHANCED BATCH (Maximum Performance)

**Best for**: Processing large batches, production workflows

Features:
- Concurrent processing with configurable workers
- Intelligent caching to skip already-processed files
- Comprehensive metadata tracking
- Performance optimization

**Output Files**:
- All files from HYBRID mode for each file
- `logs/metadata/batch_metadata.json`: Processing statistics

**Usage**:
```bash
python main.py --mode enhanced_batch
```

---

### Mode 3: MarkItDown Only (Fast, Local)

**Best for**: Quick conversions, no API costs, offline processing

Features:
- Local processing without API calls
- Fast conversion for standard documents
- Supports all MarkItDown formats

**Output Files**:
- `<name>.md`: Markdown with YAML frontmatter
- `<name>.txt`: Plain text export (if enabled)

**Usage**:
```bash
python main.py --mode markitdown
```

---

### Mode 4: Mistral OCR Only (High Accuracy)

**Best for**: When you want pure OCR analysis without MarkItDown or table extraction

Features:
- State-of-the-art OCR using Mistral AI's dedicated OCR model (mistral-ocr-latest)
- **Works on ALL PDFs** (both scanned documents and text-based PDFs)
- ~95% accuracy across diverse document types
- Understands tables, equations, multi-column layouts, and complex formatting
- Quality assessment of OCR results
- Image extraction with base64 encoding
- Files API with signed URLs for all documents

**Why Use This Mode**:
- You want Mistral AI's advanced document understanding
- You need image extraction from documents
- You want structured JSON metadata output
- You prefer AI-powered analysis over traditional text extraction

**Output Files**:
- `<name>_mistral_ocr.md`: Page-by-page OCR results
- `<name>_mistral_ocr.txt`: Plain text export
- `<name>_ocr_metadata.json`: Structured JSON (if enabled)
- `output_images/<name>_ocr/`: Extracted images

**Usage**:
```bash
python main.py --mode mistral_ocr
```

---

### Mode 5: Transcription (Audio/Video)

**Best for**: Audio/video transcription, YouTube videos

Features:
- Audio/video file transcription
- YouTube URL support
- Requires MarkItDown plugins

**Requirements**:
- Set `MARKITDOWN_ENABLE_PLUGINS=true` in `.env`
- Install audio transcription plugins

**Output Files**:
- `<name>_transcription.md`: Transcribed text
- `<name>_transcription.txt`: Plain text export

**Usage**:
```bash
python main.py --mode transcription
```

---

### Mode 6: Standard Batch Process

**Best for**: Simple batch operations, mixed file types

Features:
- Simple batch processing by file type
- Automatic method selection
- No advanced features (faster)

**Output Files**:
- Varies by file type (MarkItDown or Mistral OCR outputs)

**Usage**:
```bash
python main.py --mode batch
```

---

### Mode 7: Convert PDFs to Images

**Best for**: Page rendering, image extraction, thumbnails

Features:
- Renders each PDF page to PNG
- Configurable DPI
- Requires Poppler

**Output Files**:
- `output_images/<pdf_name>_pages/page_001.png`
- `output_images/<pdf_name>_pages/page_002.png`
- etc.

**Usage**:
```bash
python main.py --mode pdf_to_images
```

---

### Mode 8: Show System Status

**Best for**: Monitoring, troubleshooting, cache management

Displays:
- Configuration status
- Cache statistics (hits, misses, size)
- Output file counts
- Input file inventory
- Configured models
- System recommendations

**Usage**:
```bash
python main.py --mode status
```

## Configuration

All configuration is done via `.env` file. See `.env.example` for all options.

### Required Configuration

```ini
# REQUIRED: Get your API key from https://console.mistral.ai/
MISTRAL_API_KEY="your_mistral_api_key_here"
```

### Key Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `MISTRAL_OCR_MODEL` | `mistral-ocr-latest` | OCR model to use |
| `MISTRAL_INCLUDE_IMAGES` | `true` | Extract images from documents |
| `SAVE_MISTRAL_JSON` | `true` | Save OCR metadata JSON for quality assessment |
| `CACHE_DURATION_HOURS` | `24` | Cache validity period |
| `MAX_CONCURRENT_FILES` | `5` | Batch processing concurrency |
| `GENERATE_TXT_OUTPUT` | `true` | Create .txt files |

See `.env.example` for 40+ configuration options.

## Troubleshooting

### "MISTRAL_API_KEY not set"

1. Copy `.env.example` to `.env`
2. Get API key from https://console.mistral.ai/api-keys/
3. Set `MISTRAL_API_KEY` in `.env`

### "MarkItDown not installed"

```bash
pip install markitdown
```

### "pdf2image: Unable to get page count"

Install Poppler and set `POPPLER_PATH` in `.env` (Windows only).

## Documentation Links

### Core Dependencies
- **MarkItDown**: https://github.com/microsoft/markitdown
- **Mistral Document AI**: https://docs.mistral.ai/capabilities/document_ai/basic_ocr/
- **Mistral Python SDK**: https://github.com/mistralai/client-python
- **Camelot**: https://camelot-py.readthedocs.io/
- **pdf2image**: https://github.com/Belval/pdf2image

## Latest Updates

### Version 2.1 (Current)
- ✅ 8 specialized conversion modes
- ✅ Hybrid processing pipeline with OCR quality assessment
- ✅ Intelligent caching system
- ✅ Advanced table extraction (pdfplumber + camelot)
- ✅ Automated OCR quality scoring and weak page re-processing
- ✅ Comprehensive batch processing with metadata tracking
- ✅ Cross-platform support (Windows, macOS, Linux)

---

**Enhanced Document Converter v2.1** - Combining the best of local and cloud processing for optimal document conversion.
