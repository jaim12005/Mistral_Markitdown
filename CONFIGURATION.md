# Configuration Reference

Complete reference for all configuration options in Enhanced Document Converter v2.1.1.

## Table of Contents

- [Configuration File](#configuration-file)
- [API Keys](#api-keys)
- [Mistral OCR Settings](#mistral-ocr-settings)
- [Document QnA](#document-qna)
- [Batch OCR Processing](#batch-ocr-processing)
- [File Upload Management](#file-upload-management)
- [Structured Data Extraction](#structured-data-extraction)
- [Image Processing](#image-processing)
- [Table Extraction](#table-extraction)
- [PDF to Image Conversion](#pdf-to-image-conversion)
- [System Paths](#system-paths-windows-only)
- [Caching](#caching)
- [Logging](#logging)
- [Performance](#performance)
- [API Retry Configuration](#api-retry-configuration)
- [Output Settings](#output-settings)
- [MarkItDown Settings](#markitdown-settings)
- [Complete Example Configuration](#complete-example-configuration)
- [Configuration by Use Case](#configuration-by-use-case)
- [Environment Variable Reference](#environment-variable-reference)

## Configuration File

All settings are configured through a `.env` file in the project root directory.

### Creating Your Configuration

1. Create a file named `.env` in the project root
2. Add your settings (see options below)
3. Restart the converter for changes to take effect

**Example `.env` file:**
```ini
# Minimal configuration
MISTRAL_API_KEY="your_key_from_console.mistral.ai"

# Optional optimizations
CACHE_DURATION_HOURS=24
MAX_CONCURRENT_FILES=5
LOG_LEVEL=INFO
```

---

## API Keys

### MISTRAL_API_KEY (Required for OCR)
- **Type:** String
- **Default:** None (must be set)
- **Required for:** Modes 1, 2, 4 (all OCR features)
- **Get it from:** https://console.mistral.ai/api-keys/

```ini
MISTRAL_API_KEY="your_api_key_here"
```

### OPENAI_API_KEY (Optional)
- **Type:** String
- **Default:** None
- **Required for:** MarkItDown LLM integration (if MARKITDOWN_USE_LLM=true)
- **Get it from:** https://platform.openai.com/api-keys

```ini
OPENAI_API_KEY="sk-..."
```

### Azure Document Intelligence (Optional)
- **Required for:** Azure AI integration
- **Setup at:** https://portal.azure.com/

```ini
AZURE_DOC_INTEL_ENDPOINT="https://your-resource.cognitiveservices.azure.com/"
AZURE_DOC_INTEL_KEY="your_azure_key"
```

---

## Mistral OCR Settings

### MISTRAL_OCR_MODEL
- **Type:** String
- **Default:** `"mistral-ocr-latest"`
- **Options:** `mistral-ocr-latest` (recommended)
- **Description:** OCR model to use

```ini
MISTRAL_OCR_MODEL="mistral-ocr-latest"
```

### MISTRAL_INCLUDE_IMAGES
- **Type:** Boolean
- **Default:** `true`
- **Description:** Extract embedded images from documents
- **Output:** Images saved to `output_images/`

```ini
MISTRAL_INCLUDE_IMAGES=true
```

### SAVE_MISTRAL_JSON
- **Type:** Boolean
- **Default:** `true`
- **Description:** Save detailed OCR metadata for quality assessment
- **Output:** Creates `*_ocr_metadata.json` files

```ini
SAVE_MISTRAL_JSON=true
```

### MISTRAL_DOCUMENT_QNA_MODEL
- **Type:** String
- **Default:** `"mistral-small-latest"`
- **Options:** `mistral-small-latest`, `mistral-medium-latest`, or any chat model supporting document_url
- **Description:** Model to use for Document QnA (natural language queries on documents)

```ini
MISTRAL_DOCUMENT_QNA_MODEL="mistral-small-latest"
```

### MISTRAL_BATCH_ENABLED
- **Type:** Boolean
- **Default:** `true`
- **Description:** Enable batch OCR processing for 50% cost reduction
- **Use for:** Processing large numbers of documents

```ini
MISTRAL_BATCH_ENABLED=true
```

### MISTRAL_BATCH_MIN_FILES
- **Type:** Integer
- **Default:** `10`
- **Description:** Minimum number of files to recommend batch processing
- **Note:** Batch processing is more cost-effective for larger batches

```ini
MISTRAL_BATCH_MIN_FILES=10
```

### OCR Quality Assessment Thresholds

Control when OCR results are considered usable based on quality scoring (0-100 scale).

#### OCR_QUALITY_THRESHOLD_EXCELLENT
- **Type:** Integer
- **Default:** `80`
- **Description:** Score above this is considered excellent quality

```ini
OCR_QUALITY_THRESHOLD_EXCELLENT=80
```

#### OCR_QUALITY_THRESHOLD_GOOD
- **Type:** Integer
- **Default:** `60`
- **Description:** Score above this is considered good quality

```ini
OCR_QUALITY_THRESHOLD_GOOD=60
```

#### OCR_QUALITY_THRESHOLD_ACCEPTABLE
- **Type:** Integer
- **Default:** `40`
- **Description:** Minimum score for acceptable quality

```ini
OCR_QUALITY_THRESHOLD_ACCEPTABLE=40
```

#### ENABLE_OCR_QUALITY_ASSESSMENT
- **Type:** Boolean
- **Default:** `true`
- **Description:** Enable/disable OCR quality scoring. Set to `false` to skip scoring entirely.

```ini
ENABLE_OCR_QUALITY_ASSESSMENT=true
```

#### ENABLE_OCR_WEAK_PAGE_IMPROVEMENT
- **Type:** Boolean
- **Default:** `true`
- **Description:** Enable/disable weak-page re-OCR. Requires `ENABLE_OCR_QUALITY_ASSESSMENT=true`.

```ini
ENABLE_OCR_WEAK_PAGE_IMPROVEMENT=true
```

### OCR Quality Detection Thresholds

Fine-tune the heuristics used to detect weak OCR pages.

#### OCR_MIN_TEXT_LENGTH
- **Type:** Integer
- **Default:** `50`
- **Description:** Minimum characters for valid page

```ini
OCR_MIN_TEXT_LENGTH=50
```

#### OCR_MIN_DIGIT_COUNT
- **Type:** Integer
- **Default:** `20`
- **Description:** Minimum digits for financial documents

```ini
OCR_MIN_DIGIT_COUNT=20
```

#### OCR_MIN_UNIQUENESS_RATIO
- **Type:** Float
- **Default:** `0.3`
- **Description:** Minimum unique token ratio (0-1)

```ini
OCR_MIN_UNIQUENESS_RATIO=0.3
```

#### OCR_MAX_PHRASE_REPETITIONS
- **Type:** Integer
- **Default:** `5`
- **Description:** Maximum repetitions before flagging as artifact

```ini
OCR_MAX_PHRASE_REPETITIONS=5
```

#### OCR_MIN_AVG_LINE_LENGTH
- **Type:** Integer
- **Default:** `10`
- **Description:** Minimum average line length

```ini
OCR_MIN_AVG_LINE_LENGTH=10
```

---

## File Upload Management

### CLEANUP_OLD_UPLOADS
- **Type:** Boolean
- **Default:** `true`
- **Description:** Automatically delete old uploads from Mistral API
- **Benefit:** Prevents unnecessary storage costs

```ini
CLEANUP_OLD_UPLOADS=true
```

### UPLOAD_RETENTION_DAYS
- **Type:** Integer
- **Default:** `7`
- **Description:** Days to keep uploaded files before deletion
- **Recommendation:** 7-14 days for most users

```ini
UPLOAD_RETENTION_DAYS=7
```

---

## Structured Data Extraction

**Important:** The OCR API uses raw JSON schema dictionaries for structured extraction, not ResponseFormat objects. The converter handles this automatically - these settings simply enable/disable the features.

### MISTRAL_ENABLE_STRUCTURED_OUTPUT
- **Type:** Boolean
- **Default:** `true`
- **Description:** Enable JSON schema-based extraction
- **Use for:** Invoices, financial statements, forms

```ini
MISTRAL_ENABLE_STRUCTURED_OUTPUT=true
```

### MISTRAL_DOCUMENT_SCHEMA_TYPE
- **Type:** String
- **Default:** `"auto"`
- **Options:** `invoice`, `financial_statement`, `form`, `generic`, `auto`

```ini
MISTRAL_DOCUMENT_SCHEMA_TYPE="auto"
```

### MISTRAL_ENABLE_BBOX_ANNOTATION
- **Type:** Boolean
- **Default:** `false`
- **Description:** Extract bounding boxes for text regions, tables, figures
- **Note:** Adds processing time

```ini
MISTRAL_ENABLE_BBOX_ANNOTATION=false
```

### MISTRAL_ENABLE_DOCUMENT_ANNOTATION
- **Type:** Boolean
- **Default:** `false`
- **Description:** Extract document structure and metadata
- **Note:** Adds processing time

```ini
MISTRAL_ENABLE_DOCUMENT_ANNOTATION=false
```

---

## Document QnA

Query documents in natural language using Mistral's chat completion with document_url content type.

### MISTRAL_DOCUMENT_QNA_MODEL
- **Type:** String
- **Default:** `"mistral-small-latest"`
- **Options:** Any Mistral chat model supporting document_url content type
- **Description:** Model for natural language document queries

```ini
MISTRAL_DOCUMENT_QNA_MODEL="mistral-small-latest"
```

**Usage:** Programmatically query documents:
```python
from mistral_converter import query_document
success, answer, error = query_document(
    "https://example.com/document.pdf",
    "What is the main topic of this document?"
)
```

---

## Batch OCR Processing

Process multiple documents at 50% cost reduction using Mistral's Batch API.

### MISTRAL_BATCH_ENABLED
- **Type:** Boolean
- **Default:** `true`
- **Description:** Enable batch OCR processing

```ini
MISTRAL_BATCH_ENABLED=true
```

### MISTRAL_BATCH_MIN_FILES
- **Type:** Integer
- **Default:** `10`
- **Description:** Minimum files to recommend batch processing
- **Recommendation:** Batch is most cost-effective for 10+ files

```ini
MISTRAL_BATCH_MIN_FILES=10
```

**Usage:** Programmatically batch process documents:
```python
from mistral_converter import create_batch_ocr_file, submit_batch_ocr_job
files = [Path("doc1.pdf"), Path("doc2.pdf"), ...]
success, batch_file, _ = create_batch_ocr_file(files, Path("batch.jsonl"))
success, job_id, _ = submit_batch_ocr_job(batch_file)
```

---

## Image Processing

### MISTRAL_ENABLE_IMAGE_OPTIMIZATION
- **Type:** Boolean
- **Default:** `true`
- **Description:** Resize and compress images before OCR
- **Note:** Only applies to image files, NOT PDFs

```ini
MISTRAL_ENABLE_IMAGE_OPTIMIZATION=true
```

### MISTRAL_ENABLE_IMAGE_PREPROCESSING
- **Type:** Boolean
- **Default:** `false`
- **Description:** Enhance image contrast and sharpness
- **Use for:** Low-quality scans
- **Note:** Only applies to image files, NOT PDFs

```ini
MISTRAL_ENABLE_IMAGE_PREPROCESSING=false
```

### MISTRAL_MAX_IMAGE_DIMENSION
- **Type:** Integer
- **Default:** `2048`
- **Description:** Maximum width/height in pixels for image resize

```ini
MISTRAL_MAX_IMAGE_DIMENSION=2048
```

### MISTRAL_IMAGE_QUALITY_THRESHOLD
- **Type:** Integer (1-100)
- **Default:** `70`
- **Description:** JPEG quality for compression

```ini
MISTRAL_IMAGE_QUALITY_THRESHOLD=70
```

---

## Table Extraction

### CAMELOT_MIN_ACCURACY
- **Type:** Float (0-100)
- **Default:** `75.0`
- **Description:** Minimum accuracy % to accept extracted tables
- **Higher is stricter:** Increase to 85+ for financial documents

```ini
CAMELOT_MIN_ACCURACY=75.0
```

### CAMELOT_MAX_WHITESPACE
- **Type:** Float (0-100)
- **Default:** `30.0`
- **Description:** Maximum whitespace % allowed in tables
- **Lower is stricter:** Decrease to 20 to filter sparse tables

```ini
CAMELOT_MAX_WHITESPACE=30.0
```

---

## PDF to Image Conversion

### PDF_IMAGE_FORMAT
- **Type:** String
- **Default:** `"png"`
- **Options:** `png`, `jpeg`, `tiff`, `ppm`
- **PNG:** Best quality, larger files
- **JPEG:** Smaller files, slight quality loss

```ini
PDF_IMAGE_FORMAT="png"
```

### PDF_IMAGE_DPI
- **Type:** Integer
- **Default:** `200`
- **Range:** 72-600
- **Recommendations:**
  - 150 - Screen viewing
  - 200 - General purpose
  - 300 - Print quality

```ini
PDF_IMAGE_DPI=200
```

### PDF_IMAGE_THREAD_COUNT
- **Type:** Integer
- **Default:** `4`
- **Range:** 1-16
- **Description:** Concurrent threads for PDF conversion

```ini
PDF_IMAGE_THREAD_COUNT=4
```

### PDF_IMAGE_USE_PDFTOCAIRO
- **Type:** Boolean
- **Default:** `true`
- **Description:** Use pdftocairo for better rendering quality

```ini
PDF_IMAGE_USE_PDFTOCAIRO=true
```

---

## System Paths (Windows Only)

### POPPLER_PATH
- **Type:** String
- **Default:** `""` (empty)
- **Required for:** PDF to image conversion on Windows
- **Download:** https://github.com/oschwartz10612/poppler-windows/releases

```ini
POPPLER_PATH="C:/Program Files/poppler-23.08.0/Library/bin"
```

### GHOSTSCRIPT_PATH
- **Type:** String
- **Default:** `""` (auto-detect)
- **Required for:** Camelot table extraction
- **Download:** https://ghostscript.com/releases/gsdnld.html
- **Note:** Usually auto-detected if installed

```ini
GHOSTSCRIPT_PATH="C:/Program Files/gs/gs10.02.1/bin"
```

---

## Caching

### CACHE_DURATION_HOURS
- **Type:** Integer
- **Default:** `24`
- **Description:** Hours to keep cached results
- **Benefit:** Second run = $0 API costs

```ini
CACHE_DURATION_HOURS=24
```

### AUTO_CLEAR_CACHE
- **Type:** Boolean
- **Default:** `true`
- **Description:** Automatically remove expired cache entries

```ini
AUTO_CLEAR_CACHE=true
```

---

## Logging

### LOG_LEVEL
- **Type:** String
- **Default:** `"INFO"`
- **Options:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Recommendation:** Use `DEBUG` for troubleshooting

```ini
LOG_LEVEL="INFO"
```

### SAVE_PROCESSING_LOGS
- **Type:** Boolean
- **Default:** `true`
- **Description:** Save detailed logs to `logs/` directory

```ini
SAVE_PROCESSING_LOGS=true
```

### VERBOSE_PROGRESS
- **Type:** Boolean
- **Default:** `true`
- **Description:** Show progress bars during processing

```ini
VERBOSE_PROGRESS=true
```

---

## Performance

### MAX_CONCURRENT_FILES
- **Type:** Integer
- **Default:** `5`
- **Range:** 1-20
- **Description:** Number of files to process concurrently in batch modes
- **Recommendation:** 3-5 for most systems, 10-15 for powerful systems

```ini
MAX_CONCURRENT_FILES=5
```

### ENABLE_ASYNC_OPERATIONS
- **Type:** Boolean
- **Default:** `true`
- **Description:** Use async file I/O for better performance

```ini
ENABLE_ASYNC_OPERATIONS=true
```

---

## API Retry Configuration

### MAX_RETRIES
- **Type:** Integer
- **Default:** `3`
- **Description:** Number of retry attempts for failed API calls

```ini
MAX_RETRIES=3
```

### RETRY_INITIAL_INTERVAL_MS
- **Type:** Integer
- **Default:** `1000`
- **Description:** Initial wait time (milliseconds) before first retry

```ini
RETRY_INITIAL_INTERVAL_MS=1000
```

### RETRY_MAX_INTERVAL_MS
- **Type:** Integer
- **Default:** `10000`
- **Description:** Maximum wait time between retries

```ini
RETRY_MAX_INTERVAL_MS=10000
```

### RETRY_EXPONENT
- **Type:** Float
- **Default:** `2.0`
- **Description:** Exponential backoff multiplier

```ini
RETRY_EXPONENT=2.0
```

### RETRY_MAX_ELAPSED_TIME_MS
- **Type:** Integer
- **Default:** `60000`
- **Description:** Maximum total time for all retries

```ini
RETRY_MAX_ELAPSED_TIME_MS=60000
```

### RETRY_CONNECTION_ERRORS
- **Type:** Boolean
- **Default:** `true`
- **Description:** Retry on network/connection errors

```ini
RETRY_CONNECTION_ERRORS=true
```

---

## Output Settings

### GENERATE_TXT_OUTPUT
- **Type:** Boolean
- **Default:** `true`
- **Description:** Create `.txt` files alongside `.md` files

```ini
GENERATE_TXT_OUTPUT=true
```

### INCLUDE_METADATA
- **Type:** Boolean
- **Default:** `true`
- **Description:** Include YAML frontmatter in markdown output

```ini
INCLUDE_METADATA=true
```

### TABLE_OUTPUT_FORMATS
- **Type:** Comma-separated string
- **Default:** `"markdown,csv"`
- **Options:** `markdown`, `csv`

```ini
TABLE_OUTPUT_FORMATS="markdown,csv"
```

### ENABLE_BATCH_METADATA
- **Type:** Boolean
- **Default:** `true`
- **Description:** Track batch processing statistics
- **Output:** `logs/metadata/batch_metadata.json`

```ini
ENABLE_BATCH_METADATA=true
```

---

## MarkItDown Settings

### MARKITDOWN_USE_LLM
- **Type:** Boolean
- **Default:** `false`
- **Description:** Use OpenAI LLM for enhanced conversions
- **Requires:** OPENAI_API_KEY

```ini
MARKITDOWN_USE_LLM=false
```

### MARKITDOWN_LLM_MODEL
- **Type:** String
- **Default:** `"gpt-4-vision-preview"`
- **Description:** OpenAI model to use (if LLM enabled)

```ini
MARKITDOWN_LLM_MODEL="gpt-4-vision-preview"
```

### MARKITDOWN_ENABLE_PLUGINS
- **Type:** Boolean
- **Default:** `false`
- **Description:** Enable audio/video transcription plugins
- **Required for:** Mode 5 (Transcription)
- **Requires:** Install `requirements-optional.txt`

```ini
MARKITDOWN_ENABLE_PLUGINS=false
```

### MARKITDOWN_MAX_FILE_SIZE_MB
- **Type:** Integer
- **Default:** `100`
- **Description:** Maximum file size for MarkItDown processing

```ini
MARKITDOWN_MAX_FILE_SIZE_MB=100
```

---

## Complete Example Configuration

```ini
# ============================================================================
# Minimal Production Configuration
# ============================================================================

# Required
MISTRAL_API_KEY="your_mistral_api_key_here"

# Recommended
CACHE_DURATION_HOURS=24
CLEANUP_OLD_UPLOADS=true
UPLOAD_RETENTION_DAYS=7
LOG_LEVEL=INFO

# ============================================================================
# Advanced Configuration (Optional)
# ============================================================================

# Table Extraction Quality
CAMELOT_MIN_ACCURACY=75.0
CAMELOT_MAX_WHITESPACE=30.0

# PDF to Image
PDF_IMAGE_FORMAT=png
PDF_IMAGE_DPI=200
PDF_IMAGE_THREAD_COUNT=4

# Performance
MAX_CONCURRENT_FILES=5
ENABLE_ASYNC_OPERATIONS=true

# Output
GENERATE_TXT_OUTPUT=true
INCLUDE_METADATA=true
TABLE_OUTPUT_FORMATS=markdown,csv

# Image Processing (for image files only)
MISTRAL_ENABLE_IMAGE_OPTIMIZATION=true
MISTRAL_ENABLE_IMAGE_PREPROCESSING=false
MISTRAL_IMAGE_QUALITY_THRESHOLD=70

# Structured Extraction
MISTRAL_ENABLE_STRUCTURED_OUTPUT=true
MISTRAL_DOCUMENT_SCHEMA_TYPE=auto
MISTRAL_ENABLE_BBOX_ANNOTATION=false
MISTRAL_ENABLE_DOCUMENT_ANNOTATION=false

# Document QnA (natural language queries)
MISTRAL_DOCUMENT_QNA_MODEL=mistral-small-latest

# Batch OCR (50% cost reduction)
MISTRAL_BATCH_ENABLED=true
MISTRAL_BATCH_MIN_FILES=10

# ============================================================================
# Windows-Specific Paths
# ============================================================================

# Only needed on Windows
POPPLER_PATH="C:/Program Files/poppler-23.08.0/Library/bin"
GHOSTSCRIPT_PATH=""  # Usually auto-detected
```

---

## Configuration by Use Case

### For Text-Based PDFs (Fast & Free)
```ini
MISTRAL_API_KEY=""  # Leave empty to use Mode 3 only
LOG_LEVEL=INFO
```
Use Mode 3 (MarkItDown Only) - no API required!

### For Scanned Documents (OCR Required)
```ini
MISTRAL_API_KEY="your_key"
MISTRAL_INCLUDE_IMAGES=true
SAVE_MISTRAL_JSON=true
CACHE_DURATION_HOURS=72  # Longer cache for expensive OCR
```

### For Financial Documents (Maximum Table Quality)
```ini
MISTRAL_API_KEY="your_key"
CAMELOT_MIN_ACCURACY=85.0  # Stricter quality
CAMELOT_MAX_WHITESPACE=20.0  # Less whitespace tolerance
TABLE_OUTPUT_FORMATS=markdown,csv
```

### For Batch Processing (Performance Optimized)
```ini
MISTRAL_API_KEY="your_key"
MAX_CONCURRENT_FILES=10  # More parallel processing
ENABLE_ASYNC_OPERATIONS=true
CACHE_DURATION_HOURS=24
GENERATE_TXT_OUTPUT=false  # Skip txt to save time
```

### For Development/Debugging
```ini
MISTRAL_API_KEY="your_key"
LOG_LEVEL=DEBUG  # Detailed logging
SAVE_PROCESSING_LOGS=true
VERBOSE_PROGRESS=true
```

---

## Environment Variable Reference

| Variable | Type | Default | Required | Section |
|----------|------|---------|----------|---------|
| MISTRAL_API_KEY | string | - | Yes (for OCR) | API Keys |
| OPENAI_API_KEY | string | - | No | API Keys |
| MISTRAL_OCR_MODEL | string | mistral-ocr-latest | No | OCR |
| MISTRAL_DOCUMENT_QNA_MODEL | string | mistral-small-latest | No | Document QnA |
| MISTRAL_INCLUDE_IMAGES | bool | true | No | OCR |
| SAVE_MISTRAL_JSON | bool | true | No | OCR |
| MISTRAL_BATCH_ENABLED | bool | true | No | Batch OCR |
| MISTRAL_BATCH_MIN_FILES | int | 10 | No | Batch OCR |
| CLEANUP_OLD_UPLOADS | bool | true | No | File Management |
| UPLOAD_RETENTION_DAYS | int | 7 | No | File Management |
| CAMELOT_MIN_ACCURACY | float | 75.0 | No | Tables |
| CAMELOT_MAX_WHITESPACE | float | 30.0 | No | Tables |
| PDF_IMAGE_FORMAT | string | png | No | PDF to Image |
| PDF_IMAGE_DPI | int | 200 | No | PDF to Image |
| PDF_IMAGE_THREAD_COUNT | int | 4 | No | PDF to Image |
| CACHE_DURATION_HOURS | int | 24 | No | Caching |
| AUTO_CLEAR_CACHE | bool | true | No | Caching |
| LOG_LEVEL | string | INFO | No | Logging |
| MAX_CONCURRENT_FILES | int | 5 | No | Performance |
| ENABLE_ASYNC_OPERATIONS | bool | true | No | Performance |
| GENERATE_TXT_OUTPUT | bool | true | No | Output |
| INCLUDE_METADATA | bool | true | No | Output |

See README.md for complete feature documentation.

---

**Last Updated:** 2025-12-18  

**Version:** 2.1.1

**Related Documentation:**
- **[README.md](README.md)** - Complete feature documentation
- **[QUICKSTART.md](QUICKSTART.md)** - Getting started guide
- **[DEPENDENCIES.md](DEPENDENCIES.md)** - System requirements
- **[KNOWN_ISSUES.md](KNOWN_ISSUES.md)** - Troubleshooting guide
