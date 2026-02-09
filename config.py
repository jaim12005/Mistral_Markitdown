"""
Enhanced Document Converter - Configuration Module

This module handles all configuration settings for the document converter,
including environment variables, directory setup, and model configuration.

Documentation references:
- MarkItDown: https://github.com/microsoft/markitdown
- Mistral OCR: https://docs.mistral.ai/capabilities/document_ai/basic_ocr/
- Mistral Python SDK: https://github.com/mistralai/client-python
"""

import os
import sys
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# ============================================================================
# Safe Environment Variable Parsing Helpers
# ============================================================================


def _safe_int(env_var: str, default: int) -> int:
    """Parse an integer environment variable with a fallback default.

    Logs a warning and returns *default* when the value cannot be converted.
    """
    raw = os.getenv(env_var, "")
    if not raw:
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        import logging
        logging.getLogger("document_converter").warning(
            f"Invalid integer for {env_var}={raw!r}, using default {default}"
        )
        return default


def _safe_float(env_var: str, default: float) -> float:
    """Parse a float environment variable with a fallback default.

    Logs a warning and returns *default* when the value cannot be converted.
    """
    raw = os.getenv(env_var, "")
    if not raw:
        return default
    try:
        return float(raw)
    except (ValueError, TypeError):
        import logging
        logging.getLogger("document_converter").warning(
            f"Invalid float for {env_var}={raw!r}, using default {default}"
        )
        return default

# ============================================================================
# Version (single source of truth)
# ============================================================================

VERSION = "2.1.1"

# ============================================================================
# Project Paths
# ============================================================================

# Base directory
BASE_DIR = Path(__file__).parent.resolve()

# Input/Output directories
INPUT_DIR = BASE_DIR / "input"
OUTPUT_MD_DIR = BASE_DIR / "output_md"
OUTPUT_TXT_DIR = BASE_DIR / "output_txt"
OUTPUT_IMAGES_DIR = BASE_DIR / "output_images"

# System directories
CACHE_DIR = BASE_DIR / "cache"
LOGS_DIR = BASE_DIR / "logs"
METADATA_DIR = LOGS_DIR / "metadata"

# ============================================================================
# Directory Creation
# ============================================================================


def ensure_directories() -> None:
    """Create all required directories if they don't exist."""
    directories = [
        INPUT_DIR,
        OUTPUT_MD_DIR,
        OUTPUT_TXT_DIR,
        OUTPUT_IMAGES_DIR,
        CACHE_DIR,
        LOGS_DIR,
        METADATA_DIR,
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


# ============================================================================
# API Configuration
# ============================================================================

# Mistral AI API Key (required)
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")

# NOTE: Azure Document Intelligence and OpenAI API keys have been removed.
# LLM image descriptions now use Mistral's OpenAI-compatible endpoint
# with the existing MISTRAL_API_KEY (no separate key needed).

# ============================================================================
# Mistral OCR Configuration
# ============================================================================

# Model selection - ALWAYS use mistral-ocr-latest for OCR
MISTRAL_OCR_MODEL = os.getenv("MISTRAL_OCR_MODEL", "mistral-ocr-latest")

# Document QnA model (for querying documents with natural language)
# Supports: mistral-small-latest, mistral-medium-latest, etc.
MISTRAL_DOCUMENT_QNA_MODEL = os.getenv("MISTRAL_DOCUMENT_QNA_MODEL", "mistral-small-latest")

# OCR options
MISTRAL_INCLUDE_IMAGES = os.getenv("MISTRAL_INCLUDE_IMAGES", "true").lower() == "true"
SAVE_MISTRAL_JSON = (
    os.getenv("SAVE_MISTRAL_JSON", "true").lower() == "true"
)  # Default true for quality assessment

# Batch OCR configuration (50% cost reduction for bulk processing)
MISTRAL_BATCH_ENABLED = os.getenv("MISTRAL_BATCH_ENABLED", "true").lower() == "true"
MISTRAL_BATCH_MIN_FILES = _safe_int("MISTRAL_BATCH_MIN_FILES", 10)  # Min files to trigger batch

# File upload management
CLEANUP_OLD_UPLOADS = os.getenv("CLEANUP_OLD_UPLOADS", "true").lower() == "true"
UPLOAD_RETENTION_DAYS = _safe_int("UPLOAD_RETENTION_DAYS", 7)  # Delete files older than N days

# OCR Quality Assessment Thresholds (0-100 scale)
OCR_QUALITY_THRESHOLD_EXCELLENT = _safe_int("OCR_QUALITY_THRESHOLD_EXCELLENT", 80)
OCR_QUALITY_THRESHOLD_GOOD = _safe_int("OCR_QUALITY_THRESHOLD_GOOD", 60)
OCR_QUALITY_THRESHOLD_ACCEPTABLE = _safe_int("OCR_QUALITY_THRESHOLD_ACCEPTABLE", 40)

# OCR Quality Detection Thresholds
OCR_MIN_TEXT_LENGTH = _safe_int("OCR_MIN_TEXT_LENGTH", 50)
OCR_MIN_DIGIT_COUNT = _safe_int("OCR_MIN_DIGIT_COUNT", 20)
OCR_MIN_UNIQUENESS_RATIO = _safe_float("OCR_MIN_UNIQUENESS_RATIO", 0.3)
OCR_MAX_PHRASE_REPETITIONS = _safe_int("OCR_MAX_PHRASE_REPETITIONS", 5)
OCR_MIN_AVG_LINE_LENGTH = _safe_int("OCR_MIN_AVG_LINE_LENGTH", 10)

# Quality assessment controls
ENABLE_OCR_QUALITY_ASSESSMENT = (
    os.getenv("ENABLE_OCR_QUALITY_ASSESSMENT", "true").lower() == "true"
)
ENABLE_OCR_WEAK_PAGE_IMPROVEMENT = (
    os.getenv("ENABLE_OCR_WEAK_PAGE_IMPROVEMENT", "true").lower() == "true"
)

MISTRAL_ENABLE_STRUCTURED_OUTPUT = (
    os.getenv("MISTRAL_ENABLE_STRUCTURED_OUTPUT", "true").lower()
    == "true"  # NOW ENABLED
)

# Schema selection for structured extraction
# Options: invoice, financial_statement, form, generic, auto
MISTRAL_DOCUMENT_SCHEMA_TYPE = os.getenv("MISTRAL_DOCUMENT_SCHEMA_TYPE", "auto")

# Enable bounding box structured extraction
MISTRAL_ENABLE_BBOX_ANNOTATION = (
    os.getenv("MISTRAL_ENABLE_BBOX_ANNOTATION", "false").lower() == "true"
)

# Enable document-level structured extraction
MISTRAL_ENABLE_DOCUMENT_ANNOTATION = (
    os.getenv("MISTRAL_ENABLE_DOCUMENT_ANNOTATION", "false").lower() == "true"
)

# OCR 3 (mistral-ocr-2512) features
# Table output format: "markdown" (default) or "html" (gives colspan/rowspan for merged cells)
MISTRAL_TABLE_FORMAT = os.getenv("MISTRAL_TABLE_FORMAT", "")  # Empty = API default (markdown)

# Extract headers/footers separately from page content
MISTRAL_EXTRACT_HEADER = os.getenv("MISTRAL_EXTRACT_HEADER", "true").lower() == "true"
MISTRAL_EXTRACT_FOOTER = os.getenv("MISTRAL_EXTRACT_FOOTER", "true").lower() == "true"

# Custom guidance prompt for document annotation LLM
MISTRAL_DOCUMENT_ANNOTATION_PROMPT = os.getenv("MISTRAL_DOCUMENT_ANNOTATION_PROMPT", "")

# Image extraction control
MISTRAL_IMAGE_LIMIT = os.getenv("MISTRAL_IMAGE_LIMIT", "")  # Empty = no limit
MISTRAL_IMAGE_MIN_SIZE = os.getenv("MISTRAL_IMAGE_MIN_SIZE", "")  # Empty = no minimum (px)

# Signed URL expiry (hours) - increase for large batch jobs
MISTRAL_SIGNED_URL_EXPIRY = _safe_int("MISTRAL_SIGNED_URL_EXPIRY", 1)

# Image optimization
MISTRAL_ENABLE_IMAGE_OPTIMIZATION = (
    os.getenv("MISTRAL_ENABLE_IMAGE_OPTIMIZATION", "true").lower() == "true"
)
MISTRAL_ENABLE_IMAGE_PREPROCESSING = (
    os.getenv("MISTRAL_ENABLE_IMAGE_PREPROCESSING", "false").lower() == "true"
)
MISTRAL_MAX_IMAGE_DIMENSION = _safe_int("MISTRAL_MAX_IMAGE_DIMENSION", 2048)
MISTRAL_IMAGE_QUALITY_THRESHOLD = _safe_int("MISTRAL_IMAGE_QUALITY_THRESHOLD", 70)

# ============================================================================
# MarkItDown Configuration
# ============================================================================

# LLM integration - uses Mistral's OpenAI-compatible endpoint (no separate API key)
# Set to true to enable LLM-powered image descriptions in MarkItDown conversions
MARKITDOWN_ENABLE_LLM_DESCRIPTIONS = os.getenv("MARKITDOWN_ENABLE_LLM_DESCRIPTIONS", "false").lower() == "true"
# Vision-capable model for image descriptions (pixtral-large-latest recommended)
MARKITDOWN_LLM_MODEL = os.getenv("MARKITDOWN_LLM_MODEL", "pixtral-large-latest")
# Custom prompt for LLM image descriptions (empty = MarkItDown default)
MARKITDOWN_LLM_PROMPT = os.getenv("MARKITDOWN_LLM_PROMPT", "")

MARKITDOWN_ENABLE_PLUGINS = (
    os.getenv("MARKITDOWN_ENABLE_PLUGINS", "false").lower() == "true"
)

# DOCX style mapping for mammoth (e.g., "p[style-name='Custom Heading'] => h2:fresh")
MARKITDOWN_STYLE_MAP = os.getenv("MARKITDOWN_STYLE_MAP", "")

# Path to ExifTool binary for EXIF metadata extraction from images/audio
MARKITDOWN_EXIFTOOL_PATH = os.getenv("MARKITDOWN_EXIFTOOL_PATH", "")

# File size limit - files exceeding this are rejected to prevent OOM
MARKITDOWN_MAX_FILE_SIZE_MB = _safe_int("MARKITDOWN_MAX_FILE_SIZE_MB", 100)

# ============================================================================
# Table Extraction Configuration
# ============================================================================

# Camelot quality thresholds
CAMELOT_MIN_ACCURACY = _safe_float("CAMELOT_MIN_ACCURACY", 75.0)  # Minimum accuracy % to accept table
CAMELOT_MAX_WHITESPACE = _safe_float("CAMELOT_MAX_WHITESPACE", 30.0)  # Maximum whitespace % to accept

# ============================================================================
# PDF to Image Configuration
# ============================================================================

PDF_IMAGE_FORMAT = os.getenv("PDF_IMAGE_FORMAT", "png")  # png, jpeg, ppm, tiff
PDF_IMAGE_DPI = _safe_int("PDF_IMAGE_DPI", 200)  # Image resolution
PDF_IMAGE_THREAD_COUNT = _safe_int("PDF_IMAGE_THREAD_COUNT", 4)  # Concurrent conversion threads
PDF_IMAGE_USE_PDFTOCAIRO = os.getenv("PDF_IMAGE_USE_PDFTOCAIRO", "true").lower() == "true"  # Better quality

# ============================================================================
# System Configuration
# ============================================================================

# External tools paths (Windows)
POPPLER_PATH = os.getenv("POPPLER_PATH", "")
GHOSTSCRIPT_PATH = os.getenv("GHOSTSCRIPT_PATH", "")

# Caching
CACHE_DURATION_HOURS = _safe_int("CACHE_DURATION_HOURS", 24)
AUTO_CLEAR_CACHE = os.getenv("AUTO_CLEAR_CACHE", "true").lower() == "true"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
SAVE_PROCESSING_LOGS = os.getenv("SAVE_PROCESSING_LOGS", "true").lower() == "true"
VERBOSE_PROGRESS = os.getenv("VERBOSE_PROGRESS", "true").lower() == "true"

# Performance
MAX_CONCURRENT_FILES = _safe_int("MAX_CONCURRENT_FILES", 5)

# Document QnA configuration
MISTRAL_QNA_SYSTEM_PROMPT = os.getenv("MISTRAL_QNA_SYSTEM_PROMPT", "")  # Custom system prompt for QnA
MISTRAL_QNA_DOCUMENT_IMAGE_LIMIT = os.getenv("MISTRAL_QNA_DOCUMENT_IMAGE_LIMIT", "")  # Max images (default: API default of 8)
MISTRAL_QNA_DOCUMENT_PAGE_LIMIT = os.getenv("MISTRAL_QNA_DOCUMENT_PAGE_LIMIT", "")  # Max pages (default: API default of 64)

# Batch processing advanced configuration
MISTRAL_BATCH_TIMEOUT_HOURS = _safe_int("MISTRAL_BATCH_TIMEOUT_HOURS", 24)

# Retry Configuration (for Mistral API calls)
MAX_RETRIES = _safe_int("MAX_RETRIES", 3)
RETRY_INITIAL_INTERVAL_MS = _safe_int("RETRY_INITIAL_INTERVAL_MS", 1000)  # 1 second
RETRY_MAX_INTERVAL_MS = _safe_int("RETRY_MAX_INTERVAL_MS", 10000)  # 10 seconds
RETRY_EXPONENT = _safe_float("RETRY_EXPONENT", 2.0)  # Exponential backoff
RETRY_MAX_ELAPSED_TIME_MS = _safe_int("RETRY_MAX_ELAPSED_TIME_MS", 60000)  # 1 minute
RETRY_CONNECTION_ERRORS = os.getenv("RETRY_CONNECTION_ERRORS", "true").lower() == "true"

# ============================================================================
# Output Configuration
# ============================================================================

GENERATE_TXT_OUTPUT = os.getenv("GENERATE_TXT_OUTPUT", "true").lower() == "true"
INCLUDE_METADATA = os.getenv("INCLUDE_METADATA", "true").lower() == "true"
TABLE_OUTPUT_FORMATS = os.getenv("TABLE_OUTPUT_FORMATS", "markdown,csv").split(",")
ENABLE_BATCH_METADATA = os.getenv("ENABLE_BATCH_METADATA", "true").lower() == "true"

# ============================================================================
# Mistral Model Configuration
# ============================================================================

# Latest Mistral models (as of December 2025)
# NOTE: Model availability and specifications may change. Verify at https://docs.mistral.ai/
MISTRAL_MODELS = {
    "mistral-small-latest": {
        "name": "Mistral Small Latest",
        "description": "Fast, cost-effective model for simple tasks including Document QnA",
        "best_for": ["document_qna", "simple_extraction", "chat"],
        "max_tokens": 32768,
    },
    "mistral-medium-latest": {
        "name": "Mistral Medium 2508",
        "description": "State-of-the-art multimodal model",
        "best_for": ["complex_documents", "multimodal_content"],
        "max_tokens": 32768,
    },
    "codestral-latest": {
        "name": "Codestral 2508",
        "description": "Advanced coding model",
        "best_for": ["code_documents", "technical_content"],
        "max_tokens": 32768,
    },
    "mistral-ocr-latest": {
        "name": "Mistral OCR 2512",
        "description": "Dedicated OCR service with ~95% accuracy",
        "best_for": ["ocr", "text_extraction", "document_processing"],
        "max_tokens": 16384,
    },
    "pixtral-large-latest": {
        "name": "Pixtral Large 2411",
        "description": "Frontier multimodal with image understanding",
        "best_for": ["image_heavy", "visual_content"],
        "max_tokens": 128000,
    },
    "magistral-medium-latest": {
        "name": "Magistral Medium 2507",
        "description": "Frontier-class reasoning",
        "best_for": ["complex_reasoning", "analysis"],
        "max_tokens": 32768,
    },
    "ministral-8b-latest": {
        "name": "Ministral 8B 2410",
        "description": "Edge model - fast and efficient",
        "best_for": ["simple_documents", "fast_processing"],
        "max_tokens": 8192,
    },
    "ministral-3b-latest": {
        "name": "Ministral 3B 2410",
        "description": "Ultra-fast edge model",
        "best_for": ["simple_text", "quick_extraction"],
        "max_tokens": 4096,
    },
}


def get_ocr_model() -> str:
    """
    Get the configured OCR model.

    Always returns MISTRAL_OCR_MODEL (mistral-ocr-latest).
    This is the dedicated OCR service and should never be substituted.

    Returns:
        Model identifier string (mistral-ocr-latest)
    """
    return MISTRAL_OCR_MODEL


# ============================================================================
# File Type Configuration
# ============================================================================

# Supported file extensions
MARKITDOWN_SUPPORTED = {
    "docx",
    "doc",
    "pptx",
    "ppt",
    "xlsx",
    "xls",
    "html",
    "htm",
    "csv",
    "json",
    "xml",
    "epub",
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "bmp",
    "tiff",
    "mp3",
    "wav",
    "m4a",
    "flac",  # Audio (requires plugins)
    "zip",   # ZIP archive (recursive extraction)
    "ipynb", # Jupyter notebooks
    "msg",   # Outlook MSG (requires extract-msg)
    "txt",   # Plain text
    "rss",   # RSS feeds
}

MISTRAL_OCR_SUPPORTED = {
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "bmp",
    "webp",  # Added: commonly supported modern format
    "tiff",  # Added: commonly supported format
    "avif",  # Added: explicitly mentioned in Mistral docs
    "docx",
    "pptx",
}

PDF_EXTENSIONS = {"pdf"}
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "tiff", "webp", "avif"}
OFFICE_EXTENSIONS = {"docx", "doc", "pptx", "ppt", "xlsx", "xls"}

# ============================================================================
# Validation
# ============================================================================


def validate_configuration() -> List[str]:
    """
    Validate the configuration and return a list of warnings/errors.

    Returns:
        List of warning/error messages
    """
    issues = []

    # Check required API key
    if not MISTRAL_API_KEY:
        issues.append(
            "WARNING: MISTRAL_API_KEY not set. Mistral OCR features will not work."
        )

    # Check LLM configuration (uses Mistral's OpenAI-compatible endpoint)
    if MARKITDOWN_ENABLE_LLM_DESCRIPTIONS and not MISTRAL_API_KEY:
        issues.append("WARNING: MARKITDOWN_ENABLE_LLM_DESCRIPTIONS is true but MISTRAL_API_KEY not set.")

    # Check Poppler on Windows
    if sys.platform == "win32" and not POPPLER_PATH:
        issues.append(
            "INFO: POPPLER_PATH not set. PDF to image conversion may not work on Windows."
        )

    # Check for structured output flag conflicts
    # bbox/document annotations require structured output to be enabled
    if not MISTRAL_ENABLE_STRUCTURED_OUTPUT:
        if MISTRAL_ENABLE_BBOX_ANNOTATION:
            issues.append(
                "WARNING: MISTRAL_ENABLE_BBOX_ANNOTATION is true but "
                "MISTRAL_ENABLE_STRUCTURED_OUTPUT is false. Bbox annotations will be silently disabled."
            )
        if MISTRAL_ENABLE_DOCUMENT_ANNOTATION:
            issues.append(
                "WARNING: MISTRAL_ENABLE_DOCUMENT_ANNOTATION is true but "
                "MISTRAL_ENABLE_STRUCTURED_OUTPUT is false. Document annotations will be silently disabled."
            )

    return issues


# ============================================================================
# Initialization
# ============================================================================

_initialized = False


def initialize() -> List[str]:
    """
    Initialize the application: create directories and validate config.

    Safe to call multiple times; only runs once.

    Returns:
        List of configuration warning/error messages (empty if all OK)
    """
    global _initialized
    if _initialized:
        return []
    _initialized = True

    ensure_directories()
    return validate_configuration()


# Run as a standalone config diagnostic: ``python config.py``
if __name__ == "__main__":
    _issues = initialize()
    print(f"Enhanced Document Converter v{VERSION}")
    print(f"Base directory: {BASE_DIR}")
    print(f"OCR model: {MISTRAL_OCR_MODEL}")
    print(f"API key set: {'Yes' if MISTRAL_API_KEY else 'No'}")
    if _issues:
        print("\nConfiguration issues:")
        for issue in _issues:
            print(f"  - {issue}")
    else:
        print("\nConfiguration OK - no issues detected.")
