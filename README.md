# Enhanced Document Converter v2.1.1

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

### Advanced Features (NEW in v2.1)

- **Structured Data Extraction**: JSON schema-based extraction for invoices, financial statements, forms
- **Async Operations**: Non-blocking processing for better performance and responsiveness
- **Retry Configuration**: Exponential backoff with configurable retry logic for API resilience
- **Bounding Box Annotations**: Structured extraction of text regions, tables, and figures with metadata
- **Document-Level Annotations**: Automatic extraction of document structure, metadata, and summaries

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

### Automatic File Cleanup

- **Automated Cleanup** - Removes old uploaded files from Mistral Files API
- **Configurable Retention** - Default: 7 days (prevents unnecessary storage costs)
- **Runs on System Status** - Automatically cleans up when you check Mode 8
- **Cost Savings** - Prevents accumulation of unused files in cloud storage

Configure in `.env`:
```ini
CLEANUP_OLD_UPLOADS=true
UPLOAD_RETENTION_DAYS=7
```

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

## Dependencies

### Required Dependencies

The core installation (`requirements.txt`) provides all essential features:

```bash
pip install -r requirements.txt
```

**Includes:**
- ✓ MarkItDown document converter (PDF, DOCX, PPTX, XLSX, HTML, images)
- ✓ Mistral AI OCR
- ✓ Advanced table extraction (pdfplumber + camelot)
- ✓ PDF to image conversion
- ✓ All 8 conversion modes (except audio/YouTube transcription)

### Optional Dependencies

For extended features like audio transcription and YouTube support:

```bash
pip install -r requirements-optional.txt
```

**Adds:**
- ✓ Audio/video transcription (MP3, WAV, M4A, FLAC)
- ✓ YouTube transcript fetching
- ✓ Azure Document Intelligence integration
- ✓ Outlook MSG file support

**Important:** Audio transcription requires:
1. Installing optional packages: `pip install pydub SpeechRecognition`
2. Installing ffmpeg binary (see [DEPENDENCIES.md](DEPENDENCIES.md))
3. Setting `MARKITDOWN_ENABLE_PLUGINS=true` in `.env`

### Complete Reference

For detailed information about all dependencies, system requirements, and troubleshooting:

📖 **See [DEPENDENCIES.md](DEPENDENCIES.md)** for the complete dependency guide.

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

# Optional: Install extended features (audio, YouTube, Azure)
pip install -r requirements-optional.txt

# Configure environment
# Note: Create a .env file based on the configuration options in this README
# or reference the comprehensive configuration sections below
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
- Renders each PDF page to PNG/JPEG/TIFF
- Configurable DPI and format
- Multi-threaded conversion (4 threads default)
- High-quality rendering with pdftocairo
- Optimized output (progressive JPEG, optimized PNG)
- Requires Poppler

**Advanced Options** (NEW):
```ini
PDF_IMAGE_FORMAT=png           # png, jpeg, ppm, tiff
PDF_IMAGE_DPI=200              # Resolution (150-300 recommended)
PDF_IMAGE_THREAD_COUNT=4       # Concurrent threads
PDF_IMAGE_USE_PDFTOCAIRO=true  # Better quality rendering
```

**Output Files**:
- `output_images/<pdf_name>_pages/page_001.png` (or .jpg, .tiff)
- `output_images/<pdf_name>_pages/page_002.png`
- etc.

**Format Comparison**:
- **PNG**: Best quality, lossless, larger files (~2-5MB/page)
- **JPEG**: Smaller files (~200-500KB/page), slight quality loss
- **TIFF**: Professional use, very large files

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

The table extraction pipeline includes sophisticated post-processing and quality filtering:

#### Quality Filtering (NEW)

**Automatic Quality Assessment:**
- **Accuracy Threshold** - Only accepts tables above `CAMELOT_MIN_ACCURACY` (default: 75%)
- **Whitespace Filtering** - Rejects tables with excessive empty cells (> `CAMELOT_MAX_WHITESPACE`)
- **Quality Metrics Logging** - Reports accuracy and whitespace percentages for each table

**Benefits:**
- Eliminates false positives from table detection
- Reduces noise in output (no more poorly extracted tables)
- Configurable thresholds for different use cases

Configure in `.env`:
```ini
CAMELOT_MIN_ACCURACY=75.0    # Minimum accuracy % to accept
CAMELOT_MAX_WHITESPACE=30.0  # Maximum whitespace % to accept
```

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
- **Quality filtering** (new - removes low-quality tables)

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
| `MISTRAL_OCR_TEMPERATURE` | `0.0` | Temperature for deterministic results |
| `MISTRAL_OCR_LANGUAGE` | `auto` | Language hint (auto, en, es, fr, de, etc.) |
| `MISTRAL_INCLUDE_IMAGES` | `true` | Extract images from documents |
| `SAVE_MISTRAL_JSON` | `true` | Save OCR metadata JSON for quality assessment |
| `CLEANUP_OLD_UPLOADS` | `true` | Auto-delete old uploaded files |
| `UPLOAD_RETENTION_DAYS` | `7` | Days to keep uploaded files |
| `CAMELOT_MIN_ACCURACY` | `75.0` | Minimum table extraction accuracy (%) |
| `PDF_IMAGE_FORMAT` | `png` | Output format for PDF conversion (png, jpeg) |
| `PDF_IMAGE_DPI` | `200` | Image resolution for PDF conversion |
| `CACHE_DURATION_HOURS` | `24` | Cache validity period |
| `MAX_CONCURRENT_FILES` | `5` | Batch processing concurrency |
| `GENERATE_TXT_OUTPUT` | `true` | Create .txt files |

See `.env.example` for 50+ configuration options with detailed explanations.

## Advanced Features Guide

### Advanced OCR Parameters (NEW)

#### Temperature Control for Deterministic Results

Control OCR consistency with temperature settings:

```ini
# In .env
MISTRAL_OCR_TEMPERATURE=0.0  # Default: Fully deterministic
```

**Benefits:**
- **Temperature 0.0** (default) = Identical results every time you process the same document
- **Consistency** = Critical for version control, testing, and reproducible workflows
- **Reliability** = Same document always produces same output

**Use Cases:**
- Document comparison and diff tracking
- Automated testing and CI/CD pipelines
- Compliance and audit requirements

#### Language Optimization

Improve OCR accuracy by specifying document language:

```ini
# In .env
MISTRAL_OCR_LANGUAGE=auto  # Default: Auto-detect
```

**Supported Languages:**
- `auto` - Automatic detection (default, works well for most cases)
- `en` - English
- `es` - Spanish
- `fr` - French
- `de` - German
- `it` - Italian
- `pt` - Portuguese
- `nl` - Dutch
- `pl` - Polish
- `ru` - Russian
- `ja` - Japanese
- `ko` - Korean
- `zh` - Chinese
- `ar` - Arabic

**When to Use:**
- Multi-language documents - specify primary language
- Specialized terminology - helps with context
- Non-English documents - significant accuracy improvement

#### Token Limits

Control maximum output length:

```ini
# In .env
MISTRAL_OCR_MAX_TOKENS=16384  # Default: 16,384 tokens
```

**Benefits:**
- Prevents truncation on large documents
- Configurable based on document size
- Balance between completeness and performance

### Enhanced Document Metadata Extraction (NEW)

MarkItDown now automatically extracts and includes document properties in YAML frontmatter:

**Automatically Extracted:**
- **Title** - Document title from metadata
- **Author** - Document author/creator
- **Subject** - Document subject
- **Creator** - Application that created the document
- **Producer** - PDF producer/converter used
- **Created Date** - Document creation timestamp
- **Modified Date** - Last modification timestamp
- **Page Count** - Total number of pages
- **Word Count** - Approximate word count (when available)

**Example Output:**
```yaml
---
title: "Financial Report Q4 2024"
source_file: "report.pdf"
conversion_method: "MarkItDown"
converted_at: "2025-01-15T10:30:00"
converter_version: "2.1"
doc_title: "Financial Report Q4 2024"
doc_author: "John Smith"
doc_subject: "Quarterly Financial Analysis"
doc_pages: 25
doc_created: "2024-12-31T09:00:00"
doc_modified: "2025-01-05T14:30:00"
---
```

**Benefits:**
- **Search and Indexing** - Rich metadata for document management systems
- **Audit Trails** - Track document provenance and modifications
- **Automation** - Script document processing based on metadata
- **Organization** - Sort and filter documents by properties

### Structured Data Extraction

Extract structured data from documents using predefined JSON schemas.

#### Available Schemas

1. **Invoice Extraction** - Vendor, line items, totals, payment terms
2. **Financial Statements** - Accounts, balances, periods, company info
3. **Form Extraction** - Field names, values, signatures, dates
4. **Generic Documents** - Sections, tables, figures, metadata

#### Configuration

```ini
# Enable structured outputs
MISTRAL_ENABLE_STRUCTURED_OUTPUT=true

# Select schema type: invoice, financial_statement, form, generic, auto
MISTRAL_DOCUMENT_SCHEMA_TYPE="auto"

# Enable bounding box annotations (text regions, tables, figures)
MISTRAL_ENABLE_BBOX_ANNOTATION=false

# Enable document-level annotations (structure, metadata, summary)
MISTRAL_ENABLE_DOCUMENT_ANNOTATION=false
```

#### Output Files

When structured extraction is enabled, you'll get:
- `<filename>_document_annotation.json` - Structured document data
- `<filename>_bbox_annotations.json` - Structured bounding box data

#### Example: Invoice Extraction

```json
{
  "document_type": "invoice",
  "vendor": {
    "name": "Acme Corp",
    "address": "123 Main St"
  },
  "invoice_details": {
    "invoice_number": "INV-2024-001",
    "invoice_date": "2024-01-15"
  },
  "line_items": [
    {
      "description": "Product A",
      "quantity": 10,
      "unit_price": 50.00,
      "amount": 500.00
    }
  ],
  "totals": {
    "subtotal": 500.00,
    "tax": 50.00,
    "total": 550.00,
    "currency": "USD"
  }
}
```

---

### Async Operations

Asynchronous processing for better performance and non-blocking operations.

#### Benefits

- **Better Resource Utilization**: Efficient use of system resources
- **Non-Blocking**: UI remains responsive during processing
- **Concurrent File I/O**: Async file operations reduce wait times

#### Configuration

```ini
# Enable async operations (recommended)
ENABLE_ASYNC_OPERATIONS=true
```

#### Current Implementation

When enabled, the system uses `async`/`await` for:
- Async file I/O operations (`aiofiles`)
- Concurrent batch processing with ThreadPoolExecutor
- Non-blocking file uploads

**Note**: Full async OCR processing integration is available in the codebase (`process_with_ocr_async`, `convert_with_mistral_ocr_async`) and can be integrated into batch modes for further performance improvements. Current batch modes use ThreadPoolExecutor for concurrent file processing.

---

### Retry Configuration

Exponential backoff retry logic for API resilience.

#### Configuration

```ini
# Number of retry attempts
MAX_RETRIES=3

# Initial retry interval (milliseconds)
RETRY_INITIAL_INTERVAL_MS=1000

# Maximum retry interval (milliseconds)
RETRY_MAX_INTERVAL_MS=10000

# Exponential backoff multiplier
RETRY_EXPONENT=2.0

# Maximum total time for retries (milliseconds)
RETRY_MAX_ELAPSED_TIME_MS=60000

# Retry on connection errors
RETRY_CONNECTION_ERRORS=true
```

#### Retry Strategy

**Exponential Backoff Example:**
- Attempt 1: Fails → Wait 1 second
- Attempt 2: Fails → Wait 2 seconds (1s × 2.0)
- Attempt 3: Fails → Wait 4 seconds (2s × 2.0)
- Attempt 4: Success or give up after 60 seconds total

#### Benefits

- **Resilience**: Automatic recovery from transient failures
- **Rate Limiting**: Prevents API throttling
- **Cost Optimization**: Reduces failed requests

---

### Bounding Box Annotations

Structured extraction of individual content regions with metadata.

#### What It Extracts

For each bounding box (text region, table, figure):
- **Type**: text, table, figure, heading, list
- **Content**: Extracted text
- **Confidence**: OCR confidence score (0-1)
- **Language**: Detected language
- **Formatting**: Bold, italic, font size, font family
- **Table Structure**: Rows, columns, headers
- **Metadata**: Page number, position (header/body/footer)

#### Configuration

```ini
MISTRAL_ENABLE_BBOX_ANNOTATION=true
```

#### Output Format

```json
[
  {
    "bbox_type": "table",
    "text_content": "Q1 Revenue...",
    "confidence": 0.95,
    "table_structure": {
      "rows": 5,
      "columns": 3,
      "has_header": true
    },
    "metadata": {
      "page_number": 1,
      "position": "body"
    }
  }
]
```

---

### Document-Level Annotations

Automatic extraction of document structure and metadata.

#### What It Extracts

- **Document Type**: Report, contract, invoice, etc.
- **Title**: Document title
- **Authors**: Document creators
- **Sections**: Headings and structure
- **Tables**: Table summaries
- **Figures**: Chart/diagram descriptions
- **Metadata**: Language, page count, keywords, summary

#### Configuration

```ini
MISTRAL_ENABLE_DOCUMENT_ANNOTATION=true

# Schema types: invoice, financial_statement, form, generic
MISTRAL_DOCUMENT_SCHEMA_TYPE="generic"
```

#### Use Cases

- **Document Classification**: Auto-categorize documents
- **Metadata Extraction**: Build search indexes
- **Compliance**: Extract required fields from forms
- **Analytics**: Aggregate data from financial statements

---

### Custom JSON Schemas

Advanced users can create custom schemas in `schemas.py`.

#### Example: Custom Schema

```python
CUSTOM_SCHEMA = {
    "type": "object",
    "properties": {
        "field_name": {
            "type": "string",
            "description": "Field description"
        }
    },
    "required": ["field_name"]
}
```

See `schemas.py` for complete schema definitions and examples.

---

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

### Version 2.1.1 (Current - Enhanced)

**New Features:**
- ✅ **Advanced OCR Parameters** - Temperature control, language hints, token limits
- ✅ **Automatic File Cleanup** - Removes old uploads from Mistral API (prevents storage costs)
- ✅ **Table Quality Filtering** - Accuracy and whitespace thresholds for better extraction
- ✅ **Enhanced Metadata Extraction** - Automatic extraction of document properties (author, dates, etc.)
- ✅ **Advanced PDF to Image** - Multi-threaded, multiple formats (PNG/JPEG/TIFF), optimized output
- ✅ **50+ Configuration Options** - Comprehensive `.env.example` with detailed explanations
- ✅ **Deterministic OCR** - Temperature 0.0 for reproducible results

### Version 2.1 (Previous)
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

## Summary of Improvements (v2.1.1)

| Feature | Before | After | Benefit |
|---------|--------|-------|---------|
| **OCR Consistency** | Variable results | Deterministic (temp=0.0) | Reproducible workflows |
| **File Cleanup** | Manual | Automatic | Cost savings, no orphaned files |
| **Table Quality** | All tables accepted | Quality filtered (75%+ accuracy) | Cleaner output, fewer errors |
| **Document Metadata** | Basic filename only | Full properties (author, dates, etc.) | Better organization & search |
| **PDF to Image** | PNG only, single-threaded | Multi-format, 4 threads | Faster, flexible output |
| **Configuration** | ~40 options | 50+ detailed options | More control & customization |

---

**Enhanced Document Converter v2.1.1** - Combining the best of local and cloud processing for optimal document conversion with maximum efficiency and quality.
