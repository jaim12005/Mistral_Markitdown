# Quick Start Guide

Get started with Enhanced Document Converter in 5 minutes.

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
- Images (PNG, JPG)

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
- Supported: PDF, DOCX, PPTX, XLSX, PNG, JPG

### Low OCR quality scores
- For text-based PDFs, use Mode 3 (MarkItDown) instead
- Mode 3 is often better and free for standard PDFs

## Next Steps

- Read [README.md](README.md) for advanced configuration
- Check [DEPENDENCIES.md](DEPENDENCIES.md) for system requirements
- See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup

## Need Help?

- Check Mode 8 (System Status) for diagnostics
- Review logs in `logs/` directory
- Check [README.md](README.md) troubleshooting section

