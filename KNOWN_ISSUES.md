# Known Issues and Limitations

## Recently Fixed Issues

### ✅ Temporary File Cleanup (Fixed in v2.1.1)

**Issue:** When image preprocessing was enabled, temporary files (`*_preprocessed.png`, `*_optimized.png`) were created but never deleted.

**Impact:** Files accumulated in input directory over time.

**Fix:** Added automatic cleanup after upload completes (success or failure).

**Status:** ✅ Fixed - Temporary files now automatically deleted after processing.

---

## Current Known Issues

### 1. Mistral OCR API Parameter Limitations

**Issue:** The Mistral OCR endpoint does not support certain parameters available in the chat completion API.

**Parameters NOT Supported:**
- `temperature` - OCR is deterministic by design
- `max_tokens` - OCR processes full documents
- `language` - OCR auto-detects languages

**Status:** ✅ Fixed in code (parameters removed from API calls)

**Documentation:** Configuration variables exist in `config.py` but are not used. They're marked with comments explaining they're not supported.

**Impact:** None - OCR works correctly without these parameters

---

### 2. Image Preprocessing Only Works for Image Files

**Issue:** Image preprocessing (contrast, sharpness enhancement) only applies to standalone image files (.png, .jpg, etc.), NOT to PDFs.

**Explanation:**
- PDFs are uploaded as complete documents to Mistral
- Image enhancement can't be applied to PDF pages individually
- This is by design - PDFs contain vector graphics and text layers

**Workaround for PDFs:**
1. Use Mode 7 to convert PDF pages to images
2. Then process the images with Mode 4 with preprocessing enabled
3. Or use Mode 1/3 for text-based PDFs (often better quality)

**Status:** Working as designed

---

### 3. Low OCR Quality Scores for Some Text-Based PDFs

**Issue:** Text-based PDFs sometimes receive low quality scores (20-40/100) even when OCR works.

**Explanation:**
- Quality assessment heuristics are optimized for scanned documents
- Text-based PDFs may have different characteristics
- The quality checker looks for digit counts, token uniqueness, etc.

**Recommendation:**
- For text-based PDFs, use **Mode 3 (MarkItDown Only)**
- Mode 3 is faster, free, and often more accurate for text-layer PDFs
- Use OCR (Mode 4) only for scanned documents or complex layouts

**Status:** Will improve quality heuristics in future version

---

### 4. Windows Poppler/Ghostscript Path Configuration

**Issue:** PDF to image conversion (Mode 7) and some table extraction requires manual path configuration on Windows.

**Required System Binaries:**
- **Poppler** - For PDF to image conversion
- **Ghostscript** - For Camelot table extraction

**Solution:**
```ini
# In .env (Windows only)
POPPLER_PATH="C:/Program Files/poppler-23.08.0/Library/bin"
GHOSTSCRIPT_PATH=""  # Usually auto-detected
```

**Download:**
- Poppler: https://github.com/oschwartz10612/poppler-windows/releases
- Ghostscript: https://ghostscript.com/releases/gsdnld.html

**Status:** Platform-specific limitation (macOS/Linux auto-detect these)

---

## Limitations by Design

### 1. MarkItDown Plugin Features Require Additional Setup

**Affected Features:**
- Audio/video transcription (Mode 5)
- YouTube transcript fetching

**Requirements:**
1. Install optional dependencies: `pip install -r requirements-optional.txt`
2. Install ffmpeg system binary
3. Set `MARKITDOWN_ENABLE_PLUGINS=true` in `.env`

**Why:** These features require heavy dependencies (audio codecs, video processing) that most users don't need.

---

### 2. Mistral OCR Requires Paid API Access

**Limitation:** Mistral OCR features (Modes 1, 2, 4) require an API key with OCR access.

**Free Alternative:** Mode 3 (MarkItDown Only) works perfectly for:
- Text-based PDFs
- Office documents (DOCX, PPTX, XLSX)
- HTML, images, and other formats

**When OCR is Worth It:**
- Scanned documents
- Complex layouts (multi-column, equations)
- Documents where text extraction fails
- Images containing text

---

### 3. Large Batch Processing Performance

**Observation:** Processing very large batches (100+ files) may be slow with Mistral OCR.

**Optimization Tips:**
1. Use caching - second run is free
2. Increase `MAX_CONCURRENT_FILES` for powerful systems
3. Use Mode 3 for text-based PDFs (much faster)
4. Process in smaller batches

**Future Enhancement:** Full async OCR integration (functions exist, not yet wired into batch modes)

---

## Reporting Issues

### Before Reporting

1. Check this document for known issues
2. Review [CONFIGURATION.md](CONFIGURATION.md) for correct settings
3. Check Mode 8 (System Status) for diagnostics
4. Review logs in `logs/` directory

### When Reporting

Include:
1. Error message (full text)
2. Mode being used
3. File type being processed
4. Relevant log files
5. Your environment (OS, Python version)
6. Whether Mistral API key has OCR access

### Where to Report

- GitHub Issues (preferred)
- Include `[v2.1.1]` tag in title
- Attach sample files if possible (remove sensitive data)

---

**Last Updated:** 2025-01-27  
**Version:** 2.1.1

