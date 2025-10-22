# Enhanced Document Converter v2.1

A powerful, production-ready document conversion system that combines Microsoft's **MarkItDown** with **Mistral AI's OCR** capabilities for optimal document processing. Features 8 specialized conversion modes, advanced table extraction, intelligent caching, and comprehensive batch processing.

## Features

### Core Capabilities

- **8 Conversion Modes**: From simple batch processing to advanced hybrid pipelines
- **Dual-Engine Processing**: MarkItDown (local, fast) + Mistral AI (cloud, accurate)
- **Advanced Table Extraction**: pdfplumber + camelot with financial document optimization
- **Intelligent Caching**: Hash-based caching with 24-hour persistence - second run = $0 API costs
- **OCR Quality Assessment**: Automated 0-100 scoring with weak page detection and re-processing
- **Batch Processing**: Concurrent file processing with metadata tracking
- **Multi-Format Support**: PDF, DOCX, PPTX, XLSX, images, audio/video
- **Consecutive Duplicate Cleaning**: Removes OCR artifacts like repeated headers automatically

### Supported Formats

| Category | Formats |
|----------|---------|
| **Documents** | PDF, DOCX, DOC, PPTX, PPT, XLSX, XLS |
| **Web** | HTML, HTM, XML |
| **Data** | CSV, JSON |
| **Images** | PNG, JPG, JPEG, GIF, BMP, TIFF |
| **Books** | EPUB |
| **Audio/Video** | MP3, WAV, M4A, FLAC (requires plugins) |

## How It Works

### Dual-Engine Architecture

This system leverages two complementary processing engines:

- **MarkItDown Engine**: Fast, local, free - extracts text/tables from standard documents
- **Mistral OCR Engine**: AI-powered, cloud-based - understands complex layouts, equations, multi-column text

### Intelligent Processing Pipeline (HYBRID Mode)

1. **Content Analysis** - Examines file structure to optimize processing strategy
2. **Table Extraction First** - pdfplumber + camelot with financial document tuning (detects merged currency cells, normalizes month headers)
3. **MarkItDown Text Extraction** - Prose, headings, document structure
4. **Mistral OCR Analysis** - Comprehensive AI understanding with ~95% accuracy across all PDF types
5. **Quality Assessment** - Automated 0-100 scoring with weak page detection
6. **Intelligent Aggregation** - Priority: Tables > Text > OCR, with quality transparency

### Files API Architecture

All Mistral OCR uses the **Files API with signed URLs** (not base64 encoding) for maximum quality:

1. **Upload** - File uploaded with `purpose="ocr"` parameter
2. **Signed URL** - System retrieves HTTPS signed URL for processing
3. **OCR Processing** - Mistral processes via signed URL (better quality than base64)
4. **Response Parsing** - Extracts text, images, and metadata
5. **Quality Scoring** - Heuristics evaluate result quality (0-100 score)
6. **Weak Page Re-processing** - Low-quality pages automatically re-OCR'd

**Why Files API?** Significantly better OCR results than base64 data URLs, especially for complex documents.

## Cost Optimization

### Intelligent Caching System

- **SHA-256 File Hashing** - Detects file changes automatically
- **24-Hour Cache Duration** (configurable) - Second run on same files = $0 API costs
- **Hit Rate Tracking** - Monitor cache effectiveness with Mode 8
- **Auto-Expiration** - Old cache entries cleared automatically

**Example Savings**: Processing 100 PDFs twice in one day - first run uses API, second run is FREE (cached).

### When to Use Each Mode

| Mode | Cost | Speed | Best For |
|------|------|-------|----------|
| **Mode 3 (MarkItDown Only)** | $0 | Fast | Text-based PDFs, Office docs, simple extraction |
| **Mode 4 (Mistral OCR Only)** | Mistral API | Moderate | When you need AI-powered document understanding |
| **Mode 1 (HYBRID)** | Mistral API | Comprehensive | Maximum accuracy, critical documents, complex layouts |

### Typical Costs

- **Mistral OCR**: Check current pricing at https://console.mistral.ai/
- **MarkItDown**: Free (local processing)
- **Cache Hits**: $0 (reuses previous results)
- **Weak Page Re-processing**: Automatic quality improvement (minimal additional cost)

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
- **Advanced table extraction** with financial document tuning:
  - Detects and fixes merged currency cells (e.g., "$ 1,234.56 $ 5,678.90" → two cells)
  - Normalizes month headers (January, February, etc.)
  - Removes page artifacts (footers, page numbers)
  - Coalesces split tables across pages
  - Deduplicates identical tables
- **Mistral OCR analysis** (works on ALL PDFs - both scanned and text-based)
- **Quality assessment** provides transparency into OCR performance (0-100 score)
- **Weak page re-processing** automatically improves low-quality results
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

**Best for**: When you want pure AI-powered document understanding

**IMPORTANT: OCR Works on ALL PDFs** - Not just scanned documents!

Mistral OCR is designed to process **both scanned documents AND text-based PDFs** with ~95% accuracy across diverse document types.

#### Why Use OCR on Text-Based PDFs?

- **AI Understands Complex Layouts** - Multi-column text, tables within paragraphs, equations
- **Preserves Spatial Relationships** - Document structure maintained
- **Extracts Embedded Images** - Images alongside text extraction
- **Superior Table Detection** - Recognizes tables that text extraction might miss
- **Cross-Page Analysis** - Understands content flow across pages

#### Features

- State-of-the-art OCR using Mistral AI's dedicated OCR model (`mistral-ocr-latest`)
- **Works on ALL PDFs** (scanned and text-based), images, DOCX, PPTX
- ~95% accuracy across diverse document types
- Understands tables, equations, multi-column layouts, complex formatting
- **Quality assessment** with 0-100 scoring
- **Weak page detection** - Identifies pages with low OCR quality
- **Automatic re-processing** - Improves weak pages without manual intervention
- Image extraction with base64 encoding
- **Files API with signed URLs** for all documents (superior to base64)

#### Technical Architecture

1. **Upload** - File uploaded to Mistral Files API with `purpose="ocr"`
2. **Signed URL** - System retrieves HTTPS signed URL
3. **OCR Processing** - Mistral processes document via signed URL
4. **Quality Assessment** - Automated scoring using multiple heuristics:
   - Text length and density
   - Digit count (critical for financial documents)
   - Token uniqueness (detects repetitive artifacts)
   - Repeated phrase detection
   - Average line length
5. **Weak Page Re-processing** - Pages below quality threshold automatically re-OCR'd
6. **Consecutive Duplicate Cleaning** - Removes OCR artifacts (e.g., repeated headers)

**Output Files**:
- `<name>_mistral_ocr.md`: Page-by-page OCR results with quality score
- `<name>_mistral_ocr.txt`: Plain text export
- `<name>_ocr_metadata.json`: Structured JSON with quality metrics (if enabled)
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

## OCR Quality Assessment System

### Automated Quality Scoring (0-100)

The system automatically evaluates OCR results using multiple heuristics to ensure transparency and reliability.

#### Quality Metrics

**Text Analysis:**
- ✅ **Text Length and Density** - Sufficient content extracted
- ✅ **Digit Count** - Critical for financial documents (low digit count = warning)
- ✅ **Token Uniqueness** - Detects repetitive artifacts (< 30% uniqueness = issue)
- ✅ **Repeated Phrase Detection** - Identifies headers repeated 5+ times
- ✅ **Average Line Length** - Very short lines suggest parsing issues

**Quality Thresholds:**
- **80-100**: Excellent quality - Use with confidence
- **60-79**: Good quality - Minor issues may exist
- **40-59**: Acceptable quality - Flagged with warnings
- **0-39**: Low quality - Prominently flagged, may prefer MarkItDown for text-based PDFs

#### Weak Page Detection

Pages are flagged as "weak" if they exhibit:
- Very short text (< 50 characters)
- Low digit count (< 20 digits for data/financial documents)
- Token uniqueness < 30% (heavy repetition)
- Repeated phrases (same header 5+ times)
- Short average line length (< 10 characters)

**Automatic Improvement**: Weak pages are automatically re-processed for better results.

#### Example Quality Output

```
OCR Quality Score: 87/100
✓ OCR quality is good. Extracted content from 12 page(s).

Weak pages: 1/12
Issues detected:
- Page 7 has low numerical content (15 digits)
```

## Advanced Features

### Enterprise-Grade Table Extraction

The table extraction pipeline includes sophisticated post-processing:

#### Financial Document Optimization

**Merged Currency Cell Detection:**
```
Before: "$ 1,234.56 $ 5,678.90"  (single cell)
After:  "$ 1,234.56" | "$ 5,678.90"  (two cells)
```

**Month Header Normalization:**
- Detects month column headers (January, February, etc.)
- Normalizes split headers across pages
- Identifies "Beginning" and "Current" balance columns

**Multi-Strategy Extraction:**
1. **pdfplumber** (fast baseline)
2. **camelot lattice mode** (tuned: `line_scale=40`, `shift_text=['l','t']`)
3. **camelot stream mode** (tuned: `edge_tol=50`, `row_tol=5`)

**Post-Processing Pipeline:**
- Fix merged currency cells (regex pattern matching)
- Deduplicate identical tables
- Coalesce split tables across pages
- Normalize headers (detect month columns)
- Clean page artifacts (footers, page numbers)
- Remove consecutive duplicate lines

### Consecutive Duplicate Cleaning

**Problem**: OCR sometimes recognizes headers/footers multiple times:
```
5151 E Broadway
5151 E Broadway
5151 E Broadway
Account Summary
```

**Solution**: Automatic cleaning with `itertools.groupby`:
```
5151 E Broadway
Account Summary
```

This feature runs automatically on all OCR results - no configuration needed.

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

**Solution:**
1. Copy `.env.example` to `.env`
2. Get API key from https://console.mistral.ai/api-keys/
3. Set `MISTRAL_API_KEY` in `.env`

### "Mistral OCR returned empty text"

**Cause**: Your API key may not have OCR access

**Solution:**
1. Verify your API key at https://console.mistral.ai/
2. Check if your plan includes OCR features (may require paid plan)
3. Try Mode 3 (MarkItDown Only) - works perfectly for text-based PDFs (free, local)

### "401 Unauthorized"

**Cause**: Invalid or expired API key

**Solution:**
1. Generate new API key at https://console.mistral.ai/api-keys/
2. Update `MISTRAL_API_KEY` in `.env`
3. Restart the converter

### "403 Forbidden - Access denied to Mistral OCR"

**Cause**: OCR feature requires paid plan

**Solution:**
1. Upgrade your Mistral plan at https://console.mistral.ai/
2. Verify plan includes OCR access
3. Alternative: Use Mode 3 (MarkItDown Only) for text-based PDFs (free)

### "MarkItDown not installed"

**Solution:**
```bash
pip install markitdown
```

### "pdf2image: Unable to get page count"

**Cause**: Poppler not installed or path not configured (Windows only)

**Solution:**
1. Download Poppler: https://github.com/oschwartz10612/poppler-windows/releases
2. Extract to `C:\Program Files\poppler-XX.XX.X\`
3. Set `POPPLER_PATH` in `.env`: `POPPLER_PATH="C:/Program Files/poppler-23.08.0/Library/bin"`

### Low OCR Quality Scores

**Symptoms**: Quality score < 40, many "weak pages" detected

**Solution:**
- **For text-based PDFs**: Use Mode 3 (MarkItDown) instead - often better for standard PDFs
- **For scanned documents**: Try improving scan quality (higher DPI, better contrast)
- **For complex layouts**: Mode 1 (HYBRID) provides best results with multiple extraction methods
- **Check document type**: Some unusual fonts or layouts may challenge OCR

### Cache Not Working

**Solution:**
1. Check `CACHE_DURATION_HOURS` in `.env` (default: 24)
2. Verify cache directory exists: `cache/`
3. Run Mode 8 to see cache statistics
4. Clear old cache: Set `AUTO_CLEAR_CACHE=true`

## Performance Expectations

### Processing Speed

| Document Type | Typical Speed | Notes |
|---------------|---------------|-------|
| **MarkItDown** | 1-5 seconds/file | Local processing, very fast |
| **Mistral OCR** | 2-10 seconds/page | Depends on document complexity |
| **Table Extraction** | 5-15 seconds/PDF | Multiple extraction strategies |
| **HYBRID Mode** | 10-30 seconds/file | Comprehensive analysis |

### File Size Limits

- **Maximum file size**: 100MB (configurable via `MARKITDOWN_MAX_FILE_SIZE_MB`)
- **Optimal file size**: < 10MB for best performance
- **Large files**: Automatically use Files API with signed URLs

### Concurrent Processing

- **Default workers**: 5 files concurrently (Mode 2)
- **Configurable**: Set `MAX_CONCURRENT_FILES` in `.env`
- **Recommended**: 3-10 workers depending on system resources

## Documentation Links

### Core Dependencies
- **MarkItDown**: https://github.com/microsoft/markitdown
- **Mistral Document AI**: https://docs.mistral.ai/capabilities/document_ai/basic_ocr/
- **Mistral Python SDK**: https://github.com/mistralai/client-python

### Advanced Documentation
- **Mistral OCR Endpoint**: https://github.com/mistralai/client-python/blob/main/docs/sdks/ocr/README.md
- **Mistral Files API**: https://github.com/mistralai/client-python/blob/main/docs/sdks/files/README.md
- **Camelot (Table Extraction)**: https://camelot-py.readthedocs.io/
- **pdf2image**: https://github.com/Belval/pdf2image

### API Management
- **Get Mistral API Key**: https://console.mistral.ai/api-keys/
- **Verify Access Levels**: https://console.mistral.ai/

## Latest Updates

### Version 2.1 (Current)
- ✅ 8 specialized conversion modes
- ✅ Hybrid processing pipeline with OCR quality assessment
- ✅ Intelligent caching system (24-hour persistence)
- ✅ Advanced table extraction with financial document tuning
- ✅ Automated OCR quality scoring (0-100) and weak page re-processing
- ✅ Consecutive duplicate cleaning for OCR artifacts
- ✅ Files API with signed URLs for all Mistral OCR
- ✅ Comprehensive batch processing with metadata tracking
- ✅ Cross-platform support (Windows, macOS, Linux)

---

**Enhanced Document Converter v2.1** - Combining the best of local and cloud processing for optimal document conversion.
