# Quick Start Guide

Get started with Enhanced Document Converter v2.2.0 in 5 minutes.

## Prerequisites

- Python 3.10 or higher
- Mistral API key (for OCR/QnA/Batch features) - https://console.mistral.ai/api-keys/

## Step 1: Installation

### Windows
```cmd
run_converter.bat
```

### macOS/Linux
```bash
chmod +x quick_start.sh
./quick_start.sh
```

### Manual Installation
```bash
python -m venv env
source env/bin/activate  # Windows: env\Scripts\activate
pip install -r requirements.txt
```

Optional extras (audio/YouTube/Azure):
```bash
pip install -r requirements-optional.txt
```

## Step 2: Configure API Key

Create a `.env` file in the project root:

```ini
MISTRAL_API_KEY="your_api_key_here"
```

## Step 3: Add Documents

Place files in `input/`.

Common supported inputs:
- PDF, DOCX, PPTX, XLSX
- PNG, JPG, WEBP, AVIF, TIFF
- CSV, JSON, HTML, XML, TXT

## Step 4: Choose a Mode

The converter exposes 10 modes:

1. HYBRID (MarkItDown + tables + Mistral OCR)
2. ENHANCED BATCH (concurrent hybrid processing)
3. MarkItDown only (fast/local)
4. Mistral OCR only
5. Transcription (audio/video; plugins + ffmpeg)
6. Standard batch (simple routing by file type)
7. PDF to images
8. System status
9. Document QnA
10. Batch OCR management

If you want one safe default: use Mode 1 (HYBRID).

## Step 5: Process and Review Output

Output directories:
- `output_md/` markdown outputs
- `output_txt/` text exports (if enabled)
- `output_images/` extracted images / PDF page renders
- `logs/` run logs + batch metadata

## Common Fast Paths

Text-based PDF:
- Mode 3 for speed/cost

Scanned PDF or hard layout:
- Mode 4 or Mode 1

Large multi-file OCR job:
- Mode 10 (batch)

Interactive questions about a doc:
- Mode 9 (Document QnA)

## Troubleshooting

- Missing API key: set `MISTRAL_API_KEY` in `.env`
- No files found: add files to `input/`
- Low OCR quality: try Mode 3 for text-native PDFs, or Mode 1 for combined extraction

## Next Steps

- [README.md](README.md) for full feature guide
- [CONFIGURATION.md](CONFIGURATION.md) for all config options
- [DEPENDENCIES.md](DEPENDENCIES.md) for dependency/system requirements
- [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for edge cases and fixes

---

Version: 2.2.0
