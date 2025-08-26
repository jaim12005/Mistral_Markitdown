# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is the **Enhanced Document Converter v2.1** - a cross-platform document conversion tool that leverages Microsoft MarkItDown for local conversion and Mistral Document AI OCR for high-accuracy text extraction from images and complex PDFs.

## Quick Start Commands

### Setup and Installation
```bash
# Windows (recommended)
run_converter.bat          # Creates venv, installs deps, launches app

# macOS/Linux  
bash quick_start.sh         # Creates venv, installs deps, runs smoke test

# Manual setup
python -m venv env
env\Scripts\activate        # Windows
source env/bin/activate     # macOS/Linux
pip install -r requirements.txt
cp .env.example .env        # Configure MISTRAL_API_KEY
python main.py
```

### Development Commands
```bash
# Run the application
python main.py              # Interactive menu

# Command line modes
python main.py --mode hybrid            # Hybrid processing (recommended)
python main.py --mode markitdown        # Local-only conversion
python main.py --mode ocr               # Mistral OCR only
python main.py --mode enhanced          # Enhanced batch processing
python main.py --mode transcription     # Audio/video transcription
python main.py --mode batch             # Simple batch processing

# Non-interactive execution
python main.py --mode hybrid --no-interactive

# Test installation
python main.py --test       # Verify setup without processing
```

## Architecture Overview

### Core Components

**main.py** - Entry point with interactive CLI and conversion orchestration
- Interactive menu system (8 processing modes)
- Command-line argument parsing
- High-level conversion workflows

**config.py** - Centralized configuration management
- Environment variable loading (.env file support)
- Directory setup and path management
- API key and service configuration

**local_converter.py** - Microsoft MarkItDown integration and table extraction
- Enhanced MarkItDown wrapper with YAML front-matter
- PDF table extraction using pdfplumber and camelot
- PDF-to-image conversion utilities

**mistral_converter.py** - Mistral OCR API integration
- Files API integration with `purpose="ocr"`
- Multi-page OCR handling and weak page re-processing
- Response processing and metadata extraction

**utils.py** - Shared utilities and infrastructure
- Intelligent caching system with duration-based expiry
- Concurrent processing framework
- Markdown table formatting and text conversion
- Error recovery and retry mechanisms
- Performance monitoring and metadata tracking

### Processing Modes

1. **Hybrid Mode** (Recommended) - Intelligently combines MarkItDown and Mistral OCR
2. **Enhanced Batch** - Concurrent processing with caching and metadata
3. **MarkItDown Only** - Fast local conversion for office docs, HTML
4. **Mistral OCR Only** - High-accuracy OCR for images and scanned PDFs
5. **Transcription** - Audio/video transcription via MarkItDown plugins
6. **Standard Batch** - Simple batch processing by file type
7. **PDF to Images** - Extract PDF pages as PNG files
8. **System Status** - Performance metrics and configuration overview

### File Processing Strategy

The system uses intelligent file analysis to determine optimal processing:
- **Document files** (.docx, .pptx, .html): MarkItDown
- **Images** (.jpg, .png, .tiff): Mistral OCR  
- **PDFs**: Hybrid approach combining both engines
- **Audio/Video**: MarkItDown transcription plugins

### Output Structure

```
output_md/          # Markdown files with YAML front-matter
output_txt/         # Plain text versions for search/indexing
output_images/      # Extracted images and OCR results
cache/              # OCR cache entries (configurable duration)
logs/               # Session metadata and error logs
```

## Environment Configuration

### Required Variables
```bash
MISTRAL_API_KEY=your_api_key_here
```

### Optional Configuration
```bash
# Poppler path for PDF-to-image (Windows)
POPPLER_PATH=C:/path/to/poppler/bin

# MarkItDown LLM features
MARKITDOWN_USE_LLM=true
OPENAI_API_KEY=your_openai_key
MARKITDOWN_LLM_MODEL=gpt-4o-mini

# Azure Document Intelligence
AZURE_DOC_INTEL_ENDPOINT=your_endpoint
AZURE_DOC_INTEL_KEY=your_key

# Performance tuning
BATCH_SIZE=5
MISTRAL_HTTP_TIMEOUT=300
CACHE_DURATION_HOURS=24

# Advanced features
MISTRAL_INCLUDE_IMAGES=true
MISTRAL_INCLUDE_IMAGE_ANNOTATIONS=true
SAVE_MISTRAL_JSON=false
MARKITDOWN_ENABLE_PLUGINS=false
```

## Key Features and Capabilities

### Advanced Table Processing
- PDF table extraction using pdfplumber and camelot
- Financial table reshaping with account code splitting
- Multi-page table coalescing and deduplication
- Wide table handling without truncation

### Intelligent Caching
- OCR result caching to avoid reprocessing
- Configurable cache duration (24h default)
- Cache statistics and hit rate monitoring

### Error Recovery
- Automatic retry logic for network requests
- Weak page re-OCR using different methods
- Fallback processing strategies

### Performance Optimization
- Concurrent file processing
- Rate limiting and resource management
- Large file upload handling (>45MB via Files API)
- Processing time estimation and analytics

## Dependencies and System Requirements

### Core Requirements
- Python 3.10+ (required by MarkItDown)
- markitdown[all]>=0.1.0
- mistralai>=1.0.0

### Document Processing
- pdfplumber>=0.10.0 (PDF text/table extraction)
- pandas>=2.0.0 (data manipulation)
- camelot-py[cv]>=0.11.0 (advanced table extraction)

### Image Processing  
- pdf2image>=1.16.0 (PDF to image conversion)
- Pillow>=10.0.0 (image handling)

### External Dependencies
- **Ghostscript** - Required for camelot lattice mode (best table extraction)
- **Poppler** - Required for PDF-to-image conversion and OCR fallback
- **ffmpeg** - Required for audio/video transcription

## Common Development Tasks

### Testing Different Modes
```bash
# Test hybrid processing on sample files
cp sample.pdf input/
python main.py --mode hybrid

# Compare OCR vs MarkItDown results
python main.py --mode markitdown
python main.py --mode ocr

# Performance testing with enhanced batch
python main.py --mode enhanced
```

### Debugging OCR Issues
```bash
# Enable JSON logging
echo "SAVE_MISTRAL_JSON=true" >> .env

# Check logs directory for detailed responses
ls logs/

# Clear cache to force reprocessing
rm -rf cache/
```

### Table Extraction Troubleshooting
```bash
# Verify Ghostscript installation
gs --version          # Linux/macOS
gswin64c --version    # Windows

# Test Poppler installation  
pdftoppm --help       # Should show help if installed
```

## Development Notes

### Code Organization
- Modular architecture with clear separation of concerns
- Extensive error handling and logging throughout
- Type hints and comprehensive docstrings
- Configuration-driven behavior

### Testing Strategy
- Smoke test via `--test` flag
- Per-mode testing with sample files
- Cache and performance monitoring built-in
- System status reporting for troubleshooting

### Performance Considerations
- Large file handling via chunked uploads
- Intelligent caching reduces API calls
- Concurrent processing for batch operations  
- Resource monitoring and cleanup

### Security Notes
- API keys loaded from environment only
- No sensitive data in logs by default
- Cache entries contain OCR results (treat as sensitive)
- Files processed locally with secure API communication