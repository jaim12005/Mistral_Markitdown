# Codebase Structure and Architecture

## Core Module Organization

### main.py (Entry Point)
- **Purpose**: Interactive CLI and conversion orchestration
- **Key Functions**:
  - `menu_loop()`: Interactive 8-mode menu system
  - `convert_hybrid_pipeline()`: Recommended hybrid processing mode
  - `convert_local_only()`: MarkItDown-only processing
  - `convert_mistral_only()`: OCR-only processing
  - `convert_enhanced_batch()`: Advanced concurrent processing
  - Command-line argument parsing with `--mode`, `--no-interactive`, `--test`

### config.py (Configuration Management)
- **Purpose**: Centralized environment and path management
- **Key Components**:
  - Directory constants: `INPUT_DIR`, `OUT_MD`, `OUT_TXT`, `OUT_IMG`, `CACHE_DIR`, `LOG_DIR`
  - API configuration: `MISTRAL_API_KEY`, `MISTRAL_MODEL`, timeout settings
  - Feature flags: `MISTRAL_INCLUDE_IMAGES`, `SAVE_MISTRAL_JSON`, `MARKITDOWN_USE_LLM`
  - Performance settings: `BATCH_SIZE`, `MAX_RETRIES`, `CACHE_DURATION_HOURS`
  - `setup_directories()`: Ensures all output directories exist
  - `load_env_like_files()`: Custom .env parser with fallback support

### local_converter.py (MarkItDown Integration)
- **Purpose**: Microsoft MarkItDown wrapper with enhanced table extraction
- **Key Functions**:
  - `run_markitdown_enhanced()`: Main MarkItDown processing with YAML front-matter
  - `extract_tables_to_markdown()`: PDF table extraction using pdfplumber and camelot
  - `pdfs_to_images()`: PDF-to-image conversion utility using pdf2image
  - Advanced table reshaping for financial documents with account code splitting

### mistral_converter.py (OCR Integration)  
- **Purpose**: Mistral OCR API integration via Files API
- **Key Functions**:
  - `mistral_ocr_file_enhanced()`: Main OCR processing with caching
  - `process_mistral_response_enhanced()`: Response processing and image extraction
  - Multi-page handling with weak page re-processing
  - Large file support (>45MB) via Files API with `purpose="ocr"`

### utils.py (Shared Infrastructure)
- **Purpose**: Common utilities, caching, and processing framework
- **Key Classes**:
  - `ProcessingResult`: Dataclass for processing outcomes
  - `ConcurrentProcessor`: Concurrent file processing with rate limiting
  - `ErrorRecoveryManager`: Automatic retry logic with exponential backoff
  - `IntelligentCache`: Duration-based caching system for OCR results
  - `MetadataTracker`: Performance monitoring and session analytics
- **Key Functions**:
  - `logline()`: Console logging with flush
  - `md_to_txt()`: Markdown to plain text conversion
  - `md_table()`: Markdown table formatting
  - File strategy analysis and complexity estimation

## Data Flow Architecture

### File Processing Pipeline
1. **File Analysis**: Determine optimal processing strategy based on file type
2. **Strategy Selection**: Choose between MarkItDown, OCR, or hybrid approach
3. **Processing Execution**: Run selected engines with error recovery
4. **Result Combination**: Merge outputs for hybrid mode (especially PDFs)
5. **Output Generation**: Create Markdown, plain text, and extracted images
6. **Metadata Tracking**: Log performance metrics and processing results

### Hybrid Processing (Recommended)
```
PDF Input → MarkItDown (text/structure) → Combined Output
         ↘ Table Extraction (pdfplumber/camelot) ↗
         ↘ Mistral OCR (layout/images) ↗
```

### Caching Strategy
- **OCR Results**: Cached by file hash with configurable duration (24h default)
- **Cache Location**: `cache/` directory with JSON metadata
- **Cache Management**: Automatic expiry and hit rate monitoring
- **Performance**: Significantly reduces API calls for repeated processing

## Directory Structure and File Organization

```
Enhanced Document Converter/
├── input/                    # Source files for processing
├── output_md/               # Generated Markdown files
├── output_txt/              # Plain text versions  
├── output_images/           # Extracted images and OCR results
├── cache/                   # OCR cache entries
├── logs/                    # Session logs and metadata
│   ├── app_startup.log      # Application startup logs
│   ├── pip_install.log      # Dependency installation logs
│   └── metadata/            # Session performance data
├── config.py                # Environment and configuration
├── main.py                  # CLI entry point and orchestration
├── local_converter.py       # MarkItDown integration
├── mistral_converter.py     # OCR API integration  
├── utils.py                 # Shared utilities and framework
├── .env.example             # Configuration template
├── requirements.txt         # Python dependencies
├── run_converter.bat        # Windows setup script
└── quick_start.sh          # Unix setup script
```

## Key Patterns and Conventions

### Error Handling Strategy
- **Graceful Degradation**: Optional dependencies handled with try/except
- **User-Friendly Messages**: Clear error reporting with troubleshooting hints
- **Comprehensive Logging**: Detailed logs for debugging with traceback preservation
- **Recovery Mechanisms**: Automatic retries for network failures, fallback processing

### Configuration Pattern
- **Environment-First**: All configuration via .env file with sensible defaults
- **Type Safety**: Helper functions for bool/int conversion from environment
- **Documentation**: Comprehensive .env.example with inline documentation
- **Validation**: Configuration validation on startup with clear error messages

### Processing Framework
- **Strategy Pattern**: File type determines processing approach
- **Concurrent Execution**: Batch processing with controlled parallelism  
- **Result Tracking**: Comprehensive metadata collection and performance monitoring
- **Resource Management**: Proper cleanup and timeout handling

## Integration Points

### External Dependencies
- **MarkItDown**: Microsoft's document conversion library (local processing)
- **Mistral API**: OCR service via Files API with `purpose="ocr"`
- **Ghostscript**: Required for advanced PDF table extraction (camelot lattice mode)
- **Poppler**: PDF-to-image conversion for OCR fallback processing
- **FFmpeg**: Audio/video transcription support

### API Integration
- **Mistral OCR**: RESTful API via official Python SDK v1
- **Files API**: Large file upload support for >45MB files
- **Rate Limiting**: Built-in request throttling and retry logic
- **Timeout Management**: Configurable timeouts for large file processing