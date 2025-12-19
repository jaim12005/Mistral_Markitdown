# Enhanced Document Converter v2.1.1

A powerful, production-ready document conversion system that combines Microsoft's **MarkItDown** with **Mistral AI's OCR** capabilities for optimal document processing. Features 8 specialized conversion modes, advanced table extraction, intelligent caching, and comprehensive batch processing.

## Documentation

| Guide | Description |
|-------|-------------|
| **[QUICKSTART.md](QUICKSTART.md)** | 5-minute getting started guide |
| **[CONFIGURATION.md](CONFIGURATION.md)** | Complete configuration reference (50+ options) |
| **[DEPENDENCIES.md](DEPENDENCIES.md)** | Dependency guide and system requirements |
| **[KNOWN_ISSUES.md](KNOWN_ISSUES.md)** | Known issues, limitations, and troubleshooting |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | Development setup and contribution guidelines |

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
- **Document QnA**: Query documents in natural language using chat.complete with document_url content type (NEW)
- **Batch OCR Processing**: Process multiple documents at 50% cost reduction using Mistral's Batch API (NEW)
- **Pydantic Model Support**: Use Pydantic models with response_format_from_pydantic_model for type-safe extraction (NEW)

### Supported Formats

| Category | Formats |
|----------|---------|
| **Documents** | PDF, DOCX, DOC, PPTX, PPT, XLSX, XLS |
| **Web** | HTML, HTM, XML |
| **Data** | CSV, JSON |
| **Images** | PNG, JPG, JPEG, GIF, BMP, TIFF, WEBP, AVIF |
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
3. Prompt for .env configuration
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

**Toggle behavior via `.env`:**
- `ENABLE_OCR_QUALITY_ASSESSMENT=true|false` to turn scoring on/off.
- `ENABLE_OCR_WEAK_PAGE_IMPROVEMENT=true|false` to allow/skip weak-page re-OCR (requires assessment enabled).

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

All configuration is done via a `.env` file in the project root. 

📖 **See [CONFIGURATION.md](CONFIGURATION.md)** for the complete configuration reference with all 50+ options organized by category.

### Quick Configuration

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
| `CLEANUP_OLD_UPLOADS` | `true` | Auto-delete old uploaded files |
| `UPLOAD_RETENTION_DAYS` | `7` | Days to keep uploaded files |
| `CAMELOT_MIN_ACCURACY` | `75.0` | Minimum table extraction accuracy (%) |
| `PDF_IMAGE_FORMAT` | `png` | Output format for PDF conversion (png, jpeg) |
| `PDF_IMAGE_DPI` | `200` | Image resolution for PDF conversion |
| `CACHE_DURATION_HOURS` | `24` | Cache validity period |
| `MAX_CONCURRENT_FILES` | `5` | Batch processing concurrency |
| `GENERATE_TXT_OUTPUT` | `true` | Create .txt files |

**Configuration Options:** This README documents all 50+ configuration options. Create a `.env` file with your settings based on the examples throughout this documentation.

## Advanced Features Guide

### OCR Configuration Options

The Mistral OCR API provides dedicated OCR capabilities optimized for document processing:

```ini
# In .env
MISTRAL_OCR_MODEL="mistral-ocr-latest"  # Dedicated OCR model
MISTRAL_INCLUDE_IMAGES=true              # Extract images from documents
SAVE_MISTRAL_JSON=true                   # Save detailed OCR metadata
```

**Available Options:**
- **Model Selection**: Use `mistral-ocr-latest` (dedicated OCR service)
- **Image Extraction**: Extract embedded images alongside text
- **Metadata Saving**: Save detailed OCR results and quality metrics
- **Page Selection**: Process specific pages for targeted extraction

**Note on Advanced Parameters:**
The Mistral OCR endpoint is a specialized service that differs from the chat completion API. Parameters like `temperature`, `max_tokens`, and `language` are **not supported** by the OCR endpoint. The OCR service automatically:
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

**OCR Response Structure:**
The OCR API returns a comprehensive response including:
- `pages` - List of page objects with:
  - `markdown` - Extracted text in markdown format
  - `images` - Extracted images with position data (id, top_left_x/y, bottom_right_x/y, image_base64)
  - `dimensions` - Page dimensions (dpi, height, width)
  - `tables` - Detected tables with structure
  - `hyperlinks` - Extracted hyperlinks
  - `header` / `footer` - Page header and footer content
- `usage_info` - Processing metrics (pages_processed, doc_size_bytes)
- `model` - The OCR model used
- `document_annotation` - Structured document-level data (if enabled)

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

### Document QnA (NEW)

Query documents in natural language using Mistral's Document QnA capability. This combines OCR with chat completion to enable interactive document understanding.

#### How It Works

1. **Document Processing**: OCR extracts text, structure, and formatting
2. **Language Model Understanding**: The extracted content is analyzed by an LLM
3. **Natural Language Query**: Ask questions and get answers based on document content

#### Key Capabilities

- Question answering about specific document content
- Information extraction and summarization
- Document analysis and insights
- Multi-document queries and comparisons
- Context-aware responses

#### Usage (Programmatic)

```python
from mistral_converter import query_document, query_document_file
from pathlib import Path

# Query a public URL
success, answer, error = query_document(
    "https://arxiv.org/pdf/1805.04770",
    "What is the main contribution of this paper?"
)
if success:
    print(answer)

# Query a local file
success, answer, error = query_document_file(
    Path("my_document.pdf"),
    "Summarize the key findings"
)
```

#### Configuration

```ini
# Model for Document QnA (supports document_url content type)
MISTRAL_DOCUMENT_QNA_MODEL="mistral-small-latest"
```

---

### Batch OCR Processing (NEW)

Process multiple documents at **50% cost reduction** using Mistral's Batch API. Ideal for large-scale document processing workflows.

#### How It Works

1. **Create Batch File**: Generate a JSONL file with all documents
2. **Submit Job**: Upload batch file and start processing
3. **Monitor Progress**: Check job status and completion
4. **Download Results**: Retrieve OCR results when complete

#### Benefits

- **50% Cost Reduction**: Batch processing is significantly cheaper
- **Scalability**: Process hundreds or thousands of documents
- **Asynchronous**: Submit and retrieve results later
- **Error Handling**: Individual document failures don't affect the batch

#### Usage (Programmatic)

```python
from mistral_converter import (
    create_batch_ocr_file,
    submit_batch_ocr_job,
    get_batch_job_status,
    download_batch_results
)
from pathlib import Path

# Step 1: Create batch file
files = [Path("doc1.pdf"), Path("doc2.pdf"), Path("doc3.pdf")]
success, batch_file, error = create_batch_ocr_file(
    files,
    Path("batch_input.jsonl")
)

# Step 2: Submit batch job
success, job_id, error = submit_batch_ocr_job(
    batch_file,
    metadata={"job_type": "document_processing"}
)
print(f"Job submitted: {job_id}")

# Step 3: Monitor progress
success, status, error = get_batch_job_status(job_id)
print(f"Status: {status['status']} - {status['progress_percent']}% complete")

# Step 4: Download results when complete
if status['status'] == 'SUCCESS':
    success, results_path, error = download_batch_results(job_id)
    print(f"Results saved to: {results_path}")
```

#### Configuration

```ini
# Enable batch OCR processing
MISTRAL_BATCH_ENABLED=true

# Minimum files to recommend batch processing
MISTRAL_BATCH_MIN_FILES=10
```

#### When to Use Batch Processing

| Scenario | Recommended Method |
|----------|-------------------|
| 1-10 documents | Standard OCR (Mode 4) |
| 10-100 documents | Batch OCR (50% savings) |
| 100+ documents | Batch OCR (significant savings) |
| Real-time processing | Standard OCR |
| Overnight processing | Batch OCR |

---

## Troubleshooting

For troubleshooting common issues, see **[KNOWN_ISSUES.md](KNOWN_ISSUES.md)**.

**Quick fixes for common issues:**

- **"MISTRAL_API_KEY not set"** → Create `.env` file with your key from https://console.mistral.ai/api-keys/
- **"401 Unauthorized"** → Verify/regenerate your API key
- **Low OCR quality scores** → Use Mode 3 (MarkItDown) for text-based PDFs
- **Windows PDF issues** → Set `POPPLER_PATH` in `.env` (see [KNOWN_ISSUES.md](KNOWN_ISSUES.md))

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

## Documentation

### Quick Links

- **[QUICKSTART.md](QUICKSTART.md)** - Get started in 5 minutes
- **[CONFIGURATION.md](CONFIGURATION.md)** - All 50+ configuration options
- **[DEPENDENCIES.md](DEPENDENCIES.md)** - Installation and system requirements
- **[KNOWN_ISSUES.md](KNOWN_ISSUES.md)** - Troubleshooting and limitations
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Development and contribution guide

### External Resources

- **MarkItDown**: https://github.com/microsoft/markitdown
- **Mistral Document AI**: https://docs.mistral.ai/capabilities/document_ai/
- **Mistral Python SDK**: https://github.com/mistralai/client-python
- **Get API Key**: https://console.mistral.ai/api-keys/

## Latest Updates

### Version 2.1.1 (Current)

**Key Features:**
- ✅ **8 Specialized Conversion Modes** - From simple MarkItDown to advanced HYBRID pipelines
- ✅ **Dual-Engine Processing** - Local (MarkItDown) + Cloud (Mistral OCR) for optimal results
- ✅ **Intelligent Caching** - 24-hour persistence, second run = $0 API costs
- ✅ **Advanced Table Extraction** - pdfplumber + camelot with quality filtering (75%+ accuracy)
- ✅ **OCR Quality Assessment** - Automated 0-100 scoring with weak page detection
- ✅ **Image Preprocessing** - Optimization and enhancement for standalone image files
- ✅ **Automatic File Cleanup** - Removes old uploads from Mistral API (cost savings)
- ✅ **Enhanced Metadata** - Automatic extraction of document properties (author, dates, etc.)
- ✅ **Multi-Threaded PDF to Image** - 4x faster with multiple format support
- ✅ **Comprehensive Configuration** - 50+ documented options in dedicated guide
- ✅ **CI/CD Integration** - GitHub Actions for automated testing and linting
- ✅ **Cross-Platform** - Windows, macOS, Linux support

---

## Summary

**Enhanced Document Converter v2.1.1** combines the best of local (MarkItDown) and cloud (Mistral AI OCR) processing for optimal document conversion. Features include 8 specialized modes, intelligent caching, quality assessment, and comprehensive configuration options - all designed for production use with cost optimization in mind.
