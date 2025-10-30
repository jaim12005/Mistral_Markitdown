# Known Issues and Limitations

Current known issues and design limitations in Enhanced Document Converter v2.1.1.

## Current Issues

### 1. OCR Parameter Limitations

**Issue:** The Mistral OCR endpoint does not support certain chat completion parameters.

**Details:**
- Parameters like `temperature`, `max_tokens`, and `language` are **NOT supported** by the OCR API
- These are chat completion API parameters, not OCR service parameters
- The OCR service automatically:
  - Detects document language
  - Extracts all text deterministically (consistent results)
  - Handles documents of any reasonable size

**Supported OCR Parameters:**
- `model` - OCR model to use (`mistral-ocr-latest`)
- `document` - Document to process (file or URL)
- `include_image_base64` - Whether to extract images
- `pages` - Optional list of specific pages to process
- `bbox_annotation_format` - Optional structured bounding box extraction
- `document_annotation_format` - Optional structured document-level extraction

**Impact:** Low - The OCR service works as designed without these parameters.

**References:**
- [Mistral OCR Documentation](https://docs.mistral.ai/capabilities/document_ai/basic_ocr/)
- [Mistral Python SDK - OCR Endpoint](https://github.com/mistralai/client-python/blob/main/docs/sdks/ocr/README.md)

---

### 2. Image Preprocessing Only Works on Image Files

**Issue:** Image preprocessing and optimization settings only apply to standalone image files (PNG, JPG, etc.), NOT PDFs.

**Details:**
- `MISTRAL_ENABLE_IMAGE_PREPROCESSING` - Only affects image files
- `MISTRAL_ENABLE_IMAGE_OPTIMIZATION` - Only affects image files
- `MISTRAL_MAX_IMAGE_DIMENSION` - Only affects image files
- PDF documents are processed directly without image preprocessing

**Why:** PDFs are sent to Mistral OCR as complete documents via the Files API. Only extracted images from PDFs can be optimized after OCR.

**Impact:** Low - PDFs are processed with high quality by default through the Files API.

**Workaround:** If you need to preprocess a PDF:
1. Use Mode 7 (PDF to Images) to convert pages to images
2. Apply preprocessing to the image files
3. Use Mode 4 (Mistral OCR) on the preprocessed images

---

### 3. Low OCR Quality Scores for Text-Based PDFs

**Issue:** Text-based PDFs may receive low quality scores (< 40) when processed with Mistral OCR.

**Details:**
- Mistral OCR works on ALL PDFs (both scanned and text-based)
- Text-based PDFs may score lower due to OCR quality heuristics
- This doesn't mean the OCR failed - it indicates that simpler extraction may be better

**Recommendation:**
- **For text-based PDFs:** Use Mode 3 (MarkItDown Only) - fast, free, and often more accurate
- **For scanned documents:** Use Mode 4 (Mistral OCR Only) or Mode 1 (HYBRID) for best results
- **When unsure:** Use Mode 1 (HYBRID) which provides all extraction methods

**Impact:** Low - The system provides quality transparency and multiple extraction methods.

---

### 4. Windows Path Configuration Requirements

**Issue:** Windows users must manually configure paths for Poppler and Ghostscript.

**Details:**
- **Poppler:** Required for PDF to image conversion (Mode 7)
- **Ghostscript:** Required for camelot table extraction
- macOS/Linux: Usually auto-detected via system PATH
- Windows: Must set `POPPLER_PATH` and optionally `GHOSTSCRIPT_PATH` in `.env`

**Configuration:**
```ini
# Windows only - adjust paths to match your installation
POPPLER_PATH="C:/Program Files/poppler-23.08.0/Library/bin"
GHOSTSCRIPT_PATH="C:/Program Files/gs/gs10.02.1/bin"
```

**Impact:** Medium - Affects Windows users for specific features.

**Resources:**
- Poppler: https://github.com/oschwartz10612/poppler-windows/releases
- Ghostscript: https://ghostscript.com/releases/gsdnld.html

---

## Limitations by Design

### 1. MarkItDown Plugin Requirements

**Limitation:** Audio/video transcription features require additional setup.

**Requirements:**
1. Install optional packages: `pip install -r requirements-optional.txt`
2. Install ffmpeg binary (system-level installation)
3. Enable plugins: `MARKITDOWN_ENABLE_PLUGINS=true` in `.env`

**Supported Formats:**
- Audio: MP3, WAV, M4A, FLAC
- Video: MP4, AVI (extracts audio track)
- YouTube: Requires YouTube transcript API

**Impact:** Low - Only affects users who need audio/video transcription (Mode 5).

---

### 2. Mistral OCR Requires Paid API

**Limitation:** Mistral OCR features (Modes 1, 2, 4) require a Mistral API key and paid plan.

**Free Alternative:** Mode 3 (MarkItDown Only) is completely free and works offline.

**Cost Optimization:**
- Use intelligent caching (24-hour default) - second run = $0 API costs
- Automatic cleanup of old uploads prevents storage costs
- Use Mode 3 for text-based PDFs (free, fast, accurate)

**API Key:** Get from https://console.mistral.ai/api-keys/

**Impact:** Medium - Users must budget for API usage or use free Mode 3.

---

### 3. Large File Processing Considerations

**Limitation:** Processing very large files (>100MB) may be slower and use more API credits.

**File Size Limits:**
- Maximum file size: 100MB (configurable via `MARKITDOWN_MAX_FILE_SIZE_MB`)
- Optimal file size: < 10MB for best performance
- Large files automatically use Files API with signed URLs

**Performance Expectations:**
- MarkItDown: 1-5 seconds/file
- Mistral OCR: 2-10 seconds/page
- Table Extraction: 5-15 seconds/PDF
- HYBRID Mode: 10-30 seconds/file

**Impact:** Low - System handles large files automatically, just takes longer.

---

### 4. Concurrent Processing Limits

**Limitation:** Batch processing has configurable concurrency limits.

**Configuration:**
```ini
MAX_CONCURRENT_FILES=5  # Adjust based on system resources
```

**Recommendations:**
- 3-5 workers for most systems
- 10-15 workers for powerful systems
- Lower if experiencing rate limiting from Mistral API

**Impact:** Low - Prevents system overload and API rate limiting.

---

## When to Use Each Mode

Understanding mode capabilities helps avoid common issues:

| Mode | Cost | Speed | Best For |
|------|------|-------|----------|
| **Mode 1 (HYBRID)** | Mistral API | Comprehensive | Maximum accuracy, critical documents, complex layouts |
| **Mode 2 (ENHANCED BATCH)** | Varies | Fast | Large batches, production workflows |
| **Mode 3 (MarkItDown Only)** | $0 | Very Fast | Text-based PDFs, Office docs, simple extraction |
| **Mode 4 (Mistral OCR Only)** | Mistral API | Moderate | Scanned documents, when AI understanding is needed |
| **Mode 5 (Transcription)** | Varies | Slow | Audio/video files, YouTube videos |
| **Mode 6 (Standard Batch)** | Varies | Fast | Simple batch operations, mixed file types |
| **Mode 7 (PDF to Images)** | $0 | Fast | Page rendering, image extraction, thumbnails |
| **Mode 8 (System Status)** | $0 | Instant | Monitoring, troubleshooting, cache management |

---

## Troubleshooting Guide

### "MISTRAL_API_KEY not set"

**Solution:**
1. Create a `.env` file in project root
2. Get API key from https://console.mistral.ai/api-keys/
3. Add `MISTRAL_API_KEY="your_key_here"` to `.env`
4. Restart the converter

---

### "401 Unauthorized" or "403 Forbidden"

**Cause:** Invalid API key or OCR feature requires paid plan.

**Solution:**
1. Verify API key at https://console.mistral.ai/
2. Check if your plan includes OCR features
3. Alternative: Use Mode 3 (MarkItDown Only) - free and works for text-based PDFs

---

### "Mistral OCR returned empty text"

**Cause:** 
- API key may not have OCR access
- Document may be corrupted
- Network connectivity issues

**Solution:**
1. Verify API key has OCR access
2. Check document is valid and readable
3. Try Mode 3 (MarkItDown) as alternative
4. Check logs for detailed error messages

---

### "pdf2image: Unable to get page count" (Windows)

**Cause:** Poppler not installed or path not configured.

**Solution:**
1. Download Poppler: https://github.com/oschwartz10612/poppler-windows/releases
2. Extract to `C:\Program Files\poppler-XX.XX.X\`
3. Set in `.env`: `POPPLER_PATH="C:/Program Files/poppler-23.08.0/Library/bin"`
4. Restart converter

---

### Low OCR Quality Scores

**Symptoms:** Quality score < 40, many "weak pages" detected.

**Solution:**
- **For text-based PDFs:** Use Mode 3 (MarkItDown) - often better for standard PDFs
- **For scanned documents:** Try Mode 1 (HYBRID) for multiple extraction methods
- **Check document:** Ensure scan quality is good (higher DPI, better contrast)

---

### Cache Not Working

**Solution:**
1. Check `CACHE_DURATION_HOURS` in `.env` (default: 24)
2. Verify cache directory exists and is writable: `cache/`
3. Run Mode 8 to see cache statistics
4. Clear old cache: `AUTO_CLEAR_CACHE=true` in `.env`

---

### Audio Transcription Not Working

**Cause:** Missing ffmpeg binary or plugins not enabled.

**Solution:**
1. Install ffmpeg:
   - Windows: Download from https://www.gyan.dev/ffmpeg/builds/
   - macOS: `brew install ffmpeg`
   - Linux: `apt-get install ffmpeg`
2. Install optional dependencies: `pip install -r requirements-optional.txt`
3. Set in `.env`: `MARKITDOWN_ENABLE_PLUGINS=true`
4. Restart converter

---

## Feature Requests and Bug Reports

If you encounter issues not listed here:

1. **Check logs:** Review files in `logs/` directory for detailed error messages
2. **Run diagnostics:** Use Mode 8 (System Status) for system information
3. **Check configuration:** Review `.env` settings against [CONFIGURATION.md](CONFIGURATION.md)
4. **Consult documentation:** See [README.md](README.md) and [DEPENDENCIES.md](DEPENDENCIES.md)
5. **Report issues:** Open a GitHub issue with:
   - System information (OS, Python version)
   - Configuration (sanitize API keys)
   - Steps to reproduce
   - Error messages and logs

---

## Version History

**v2.1.1** (January 2025)
- Fixed OCR API parameter handling
- Improved documentation clarity
- Enhanced error messages
- Better Windows support

---

**Last Updated:** January 30, 2025  
**Version:** 2.1.1

For additional help, see:
- [README.md](README.md) - Complete feature documentation
- [QUICKSTART.md](QUICKSTART.md) - Getting started guide
- [CONFIGURATION.md](CONFIGURATION.md) - Configuration reference
- [DEPENDENCIES.md](DEPENDENCIES.md) - Dependency troubleshooting

