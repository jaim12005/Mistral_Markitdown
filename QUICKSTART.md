# Quick Start Guide

Get started with Enhanced Document Converter v2.1.1 in 5 minutes.

## Prerequisites

- Python 3.10 or higher
- Mistral API key (for OCR features) - get one at https://console.mistral.ai/api-keys/

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

The script will:
1. Create virtual environment
2. Install dependencies
3. Prompt you to create `.env` file
4. Launch the converter

## Step 2: Configure API Key

When prompted, create a `.env` file:

```ini
# Required for OCR features
MISTRAL_API_KEY="your_api_key_here"
```

Get your key from: https://console.mistral.ai/api-keys/

## Step 3: Add Documents

Place files in the `input/` directory:
- PDFs
- Word documents (DOCX)
- PowerPoint (PPTX)
- Excel (XLSX)
- Images (PNG, JPG, WEBP, AVIF, TIFF, GIF, BMP)

## Step 4: Choose a Mode

The converter will show you 8 modes:

**For most users:**
- **Mode 1 (HYBRID)** - Best quality, uses MarkItDown + OCR + Table extraction
- **Mode 3 (MarkItDown Only)** - Fast, free, perfect for text-based PDFs

**For specific needs:**
- **Mode 4 (OCR Only)** - AI-powered document understanding
- **Mode 7 (PDF to Images)** - Convert PDF pages to images

## Step 5: Process Documents

1. Select your mode (e.g., type `1` for HYBRID)
2. Choose file(s) to process
3. Wait for processing to complete
4. Find results in `output_md/` directory

## Output Files

For each processed file, you'll get:

**Markdown Output:**
- `filename.md` - Converted markdown
- `filename_combined.md` - All results combined (HYBRID mode)
- `filename_tables_all.md` - Extracted tables

**Text Output** (if enabled):
- `filename.txt` - Plain text version

**Metadata** (if enabled):
- `filename_ocr_metadata.json` - Quality metrics

## Common Use Cases

### Text-Based PDF
```
Mode 3 → Select PDF → Done
Fast, free, accurate
```

### Scanned Document / Image
```
Mode 4 → Select file → Wait for OCR
AI extracts text from image
```

### Financial Document with Tables
```
Mode 1 → Select PDF → Get tables + text
Best quality, extracts structured data
```

### Batch Processing
```
Mode 2 → Select "Process ALL files"
Concurrent processing of multiple files
```

## Troubleshooting

### "MISTRAL_API_KEY not set"
- Create `.env` file in project root
- Add your API key from https://console.mistral.ai/
- Restart the converter

### "No files found in input directory"
- Add files to `input/` folder
- Supported: PDF, DOCX, PPTX, XLSX, PNG, JPG, WEBP, AVIF, TIFF, GIF, BMP

### Low OCR quality scores
- For text-based PDFs, use Mode 3 (MarkItDown) instead
- Mode 3 is often better and free for standard PDFs

## Next Steps

After getting started, explore these resources:

| Resource | Description |
|----------|-------------|
| **[CONFIGURATION.md](CONFIGURATION.md)** | All 50+ configuration options |
| **[DEPENDENCIES.md](DEPENDENCIES.md)** | System requirements (Poppler, Ghostscript, ffmpeg) |
| **[KNOWN_ISSUES.md](KNOWN_ISSUES.md)** | Troubleshooting common problems |
| **[README.md](README.md)** | Complete feature documentation |

## Need Help?

1. **Run diagnostics**: Mode 8 (System Status) shows configuration and cache info
2. **Check logs**: Review `logs/` directory for detailed error messages
3. **Troubleshooting**: See **[KNOWN_ISSUES.md](KNOWN_ISSUES.md)** for common issues and solutions
4. **Configuration**: See **[CONFIGURATION.md](CONFIGURATION.md)** for all options

---

**Version:** 2.1.1
