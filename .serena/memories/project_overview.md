# Enhanced Document Converter v2.1 - Project Overview

## Purpose
A cross-platform document conversion tool that leverages Microsoft MarkItDown for fast local conversion and Mistral Document AI OCR for high-accuracy text extraction from images and complex PDFs. Designed for quality results and easy workflow on Windows and macOS.

## Key Features
- **Multiple Processing Modes**: Hybrid (recommended), MarkItDown-only, OCR-only, transcription, batch processing
- **Advanced Table Extraction**: Uses pdfplumber and camelot for PDF table extraction
- **Intelligent Caching**: OCR result caching to avoid reprocessing
- **Cross-platform Support**: Windows batch script and Unix shell script for setup
- **File Type Support**: Documents (.docx, .pptx), PDFs, images, audio/video files, HTML

## Core Architecture
- **main.py**: Interactive CLI with 8 processing modes, argument parsing, conversion orchestration
- **config.py**: Centralized configuration management with .env support
- **local_converter.py**: MarkItDown integration, PDF table extraction, PDF-to-image utilities
- **mistral_converter.py**: Mistral OCR API integration with Files API
- **utils.py**: Shared utilities, caching, concurrent processing, error recovery

## Tech Stack
- **Language**: Python 3.10+ (required by MarkItDown)
- **Core Libraries**: markitdown[all], mistralai>=1.0.0
- **Document Processing**: pdfplumber, pandas, camelot-py[cv]
- **Image Processing**: pdf2image, Pillow
- **External Dependencies**: Ghostscript (table extraction), Poppler (PDF-to-image), ffmpeg (transcription)

## Processing Strategy
The system uses intelligent file analysis:
- **Document files** (.docx, .pptx, .html): MarkItDown
- **Images** (.jpg, .png, .tiff): Mistral OCR
- **PDFs**: Hybrid approach combining both engines
- **Audio/Video**: MarkItDown transcription plugins

## Directory Structure
- `input/`: Source files for conversion
- `output_md/`: Markdown files with YAML front-matter
- `output_txt/`: Plain text versions for search/indexing  
- `output_images/`: Extracted images and OCR results
- `cache/`: OCR cache entries (configurable duration)
- `logs/`: Session metadata and error logs