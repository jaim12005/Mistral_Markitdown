"""
Enhanced Document Converter - Configuration Module

This module handles all configuration settings for the document converter,
including environment variables, directory setup, and model configuration.

Documentation references:
- MarkItDown: https://github.com/microsoft/markitdown
- Mistral OCR: https://docs.mistral.ai/capabilities/document_ai/basic_ocr/
- Mistral Python SDK: https://github.com/mistralai/client-python
"""

import logging
import os
import sys
import threading
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# Load environment variables from .env file.
#
# IMPORTANT: All configuration values below are evaluated once at import time.
# Subsequent changes to the .env file or environment variables will NOT take
# effect until the process is restarted.  Tests that need to override config
# values should monkeypatch the ``config.<ATTR>`` attributes directly rather
# than patching environment variables (which are already consumed).
load_dotenv()

__all__ = [
    "ensure_directories",
    "get_ocr_model",
    "validate_configuration",
    "initialize",
]


# ============================================================================
# Safe Environment Variable Parsing Helpers
# ============================================================================


def _safe_int(env_var: str, default: int, min_val: int = 0) -> int:
    """Parse an integer environment variable with a fallback default.

    Logs a warning and returns *default* when the value cannot be converted
    or is below *min_val*.
    """
    raw = os.getenv(env_var, "")
    if not raw:
        return default
    try:
        value = int(raw)
        if value < min_val:
            logging.getLogger("document_converter").warning(
                "%s=%d is below minimum %d, using default %d", env_var, value, min_val, default
            )
            return default
        return value
    except (ValueError, TypeError):
        logging.getLogger("document_converter").warning(
            "Invalid integer for %s=%r, using default %d", env_var, raw, default
        )
        return default


def _safe_float(env_var: str, default: float, min_val: float = 0.0) -> float:
    """Parse a float environment variable with a fallback default.

    Logs a warning and returns *default* when the value cannot be converted
    or is below *min_val*.
    """
    raw = os.getenv(env_var, "")
    if not raw:
        return default
    try:
        value = float(raw)
        if value < min_val:
            logging.getLogger("document_converter").warning(
                "%s=%s is below minimum %s, using default %s", env_var, value, min_val, default
            )
            return default
        return value
    except (ValueError, TypeError):
        logging.getLogger("document_converter").warning(
            "Invalid float for %s=%r, using default %s", env_var, raw, default
        )
        return default


def _safe_bool(env_var: str, default: bool) -> bool:
    """Parse a boolean environment variable with a fallback default.

    Accepts common truthy/falsy strings (true/false, yes/no, 1/0, on/off).
    Logs a warning and returns *default* for unrecognised values.
    """
    raw = os.getenv(env_var, "")
    if raw == "":
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    logging.getLogger("document_converter").warning(
        "Invalid boolean for %s=%r, using default %s",
        env_var,
        raw,
        default,
    )
    return default


def _safe_csv(env_var: str, default: str) -> List[str]:
    """Parse a comma-separated environment variable into a list of strings.

    Returns the *default* list when the variable is empty or only whitespace.
    """
    raw = os.getenv(env_var, "")
    if not raw.strip():
        return [item.strip() for item in default.split(",") if item.strip()]
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values if values else [item.strip() for item in default.split(",") if item.strip()]


# ============================================================================
# Version (single source of truth)
# ============================================================================

try:
    VERSION = _pkg_version("mistral-markitdown")
except PackageNotFoundError:
    VERSION = "3.0.0"

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
    """Create all required directories if they don't exist.

    On POSIX systems, directories that contain sensitive data (cache,
    logs, outputs) are created with mode 0o700 to restrict access to the
    owning user.  On Windows, default NTFS ACLs apply; administrators
    should tighten permissions via file-system ACLs as appropriate.
    """
    _mode = 0o700 if sys.platform != "win32" else None
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
        if _mode is not None:
            directory.mkdir(parents=True, exist_ok=True, mode=_mode)
        else:
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
MISTRAL_DOCUMENT_QNA_MODEL = os.getenv("MISTRAL_DOCUMENT_QNA_MODEL", "mistral-small-latest").strip()

# OCR options
MISTRAL_INCLUDE_IMAGES = _safe_bool("MISTRAL_INCLUDE_IMAGES", True)
SAVE_MISTRAL_JSON = _safe_bool("SAVE_MISTRAL_JSON", True)

# Batch OCR configuration (50% cost reduction for bulk processing)
MISTRAL_BATCH_ENABLED = _safe_bool("MISTRAL_BATCH_ENABLED", True)
MISTRAL_BATCH_MIN_FILES = _safe_int("MISTRAL_BATCH_MIN_FILES", 10, min_val=1)

# File upload management
CLEANUP_OLD_UPLOADS = _safe_bool("CLEANUP_OLD_UPLOADS", True)
UPLOAD_RETENTION_DAYS = _safe_int("UPLOAD_RETENTION_DAYS", 7, min_val=1)

# OCR Quality Assessment Thresholds (0-100 scale)
OCR_QUALITY_THRESHOLD_EXCELLENT = _safe_int("OCR_QUALITY_THRESHOLD_EXCELLENT", 80)
OCR_QUALITY_THRESHOLD_GOOD = _safe_int("OCR_QUALITY_THRESHOLD_GOOD", 60)
OCR_QUALITY_THRESHOLD_ACCEPTABLE = _safe_int("OCR_QUALITY_THRESHOLD_ACCEPTABLE", 40)

# OCR Quality Detection Thresholds
OCR_MIN_TEXT_LENGTH = _safe_int("OCR_MIN_TEXT_LENGTH", 50)
OCR_MIN_DIGIT_COUNT = _safe_int("OCR_MIN_DIGIT_COUNT", 20)
OCR_WEAK_PAGE_DIGIT_RATIO = _safe_float("OCR_WEAK_PAGE_DIGIT_RATIO", 0.0)
OCR_MIN_UNIQUENESS_RATIO = _safe_float("OCR_MIN_UNIQUENESS_RATIO", 0.3)
OCR_MAX_PHRASE_REPETITIONS = _safe_int("OCR_MAX_PHRASE_REPETITIONS", 5)
OCR_MIN_AVG_LINE_LENGTH = _safe_int("OCR_MIN_AVG_LINE_LENGTH", 10)

# Quality assessment controls
ENABLE_OCR_QUALITY_ASSESSMENT = _safe_bool("ENABLE_OCR_QUALITY_ASSESSMENT", True)
ENABLE_OCR_WEAK_PAGE_IMPROVEMENT = _safe_bool("ENABLE_OCR_WEAK_PAGE_IMPROVEMENT", True)

MISTRAL_ENABLE_STRUCTURED_OUTPUT = _safe_bool("MISTRAL_ENABLE_STRUCTURED_OUTPUT", True)

# Schema selection for structured extraction
# Options: invoice, financial_statement, contract, form, generic, auto
MISTRAL_DOCUMENT_SCHEMA_TYPE = os.getenv("MISTRAL_DOCUMENT_SCHEMA_TYPE", "auto").strip().lower()

# Enable bounding box structured extraction
MISTRAL_ENABLE_BBOX_ANNOTATION = _safe_bool("MISTRAL_ENABLE_BBOX_ANNOTATION", False)

# Enable document-level structured extraction
MISTRAL_ENABLE_DOCUMENT_ANNOTATION = _safe_bool("MISTRAL_ENABLE_DOCUMENT_ANNOTATION", False)

# OCR 3 (mistral-ocr-2512) features
# Table output format: "markdown" (default) or "html" (gives colspan/rowspan for merged cells)
MISTRAL_TABLE_FORMAT = os.getenv("MISTRAL_TABLE_FORMAT", "").strip().lower()

# Extract headers/footers separately from page content
MISTRAL_EXTRACT_HEADER = _safe_bool("MISTRAL_EXTRACT_HEADER", True)
MISTRAL_EXTRACT_FOOTER = _safe_bool("MISTRAL_EXTRACT_FOOTER", True)

# Custom guidance prompt for document annotation LLM
MISTRAL_DOCUMENT_ANNOTATION_PROMPT = os.getenv("MISTRAL_DOCUMENT_ANNOTATION_PROMPT", "")

# Image extraction control (0 = no limit / no minimum)
MISTRAL_IMAGE_LIMIT = _safe_int("MISTRAL_IMAGE_LIMIT", 0)
MISTRAL_IMAGE_MIN_SIZE = _safe_int("MISTRAL_IMAGE_MIN_SIZE", 0)

# File size limit for Mistral OCR uploads (MB) - reject files exceeding this
MISTRAL_OCR_MAX_FILE_SIZE_MB = _safe_int("MISTRAL_OCR_MAX_FILE_SIZE_MB", 200, min_val=1)

# Signed URL expiry (hours) - increase for large batch jobs
MISTRAL_SIGNED_URL_EXPIRY = _safe_int("MISTRAL_SIGNED_URL_EXPIRY", 1, min_val=1)

# Image optimization
MISTRAL_ENABLE_IMAGE_OPTIMIZATION = _safe_bool("MISTRAL_ENABLE_IMAGE_OPTIMIZATION", True)
MISTRAL_ENABLE_IMAGE_PREPROCESSING = _safe_bool("MISTRAL_ENABLE_IMAGE_PREPROCESSING", False)
MISTRAL_MAX_IMAGE_DIMENSION = _safe_int("MISTRAL_MAX_IMAGE_DIMENSION", 2048, min_val=1)
MISTRAL_IMAGE_QUALITY_THRESHOLD = _safe_int("MISTRAL_IMAGE_QUALITY_THRESHOLD", 70, min_val=1)

# ============================================================================
# MarkItDown Configuration
# ============================================================================

# LLM integration - uses Mistral's OpenAI-compatible endpoint (no separate API key)
# Set to true to enable LLM-powered image descriptions in MarkItDown conversions
MARKITDOWN_ENABLE_LLM_DESCRIPTIONS = _safe_bool("MARKITDOWN_ENABLE_LLM_DESCRIPTIONS", False)
# Vision-capable model for image descriptions (pixtral-large-latest recommended)
MARKITDOWN_LLM_MODEL = os.getenv("MARKITDOWN_LLM_MODEL", "pixtral-large-latest").strip()
# Custom prompt for LLM image descriptions (empty = MarkItDown default)
MARKITDOWN_LLM_PROMPT = os.getenv("MARKITDOWN_LLM_PROMPT", "")

MARKITDOWN_ENABLE_PLUGINS = _safe_bool("MARKITDOWN_ENABLE_PLUGINS", False)

# Enable/disable built-in converters (v0.1.5+). Disable to selectively re-enable.
MARKITDOWN_ENABLE_BUILTINS = _safe_bool("MARKITDOWN_ENABLE_BUILTINS", True)

# Preserve base64-encoded images from HTML/DOCX/PPTX in Markdown output (v0.1.5+)
MARKITDOWN_KEEP_DATA_URIS = _safe_bool("MARKITDOWN_KEEP_DATA_URIS", False)

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

# Camelot stream mode tuning (for tables without clear grid lines)
# split_text: splits PDFMiner-merged strings across cell boundaries (critical for tight columns)
CAMELOT_STREAM_SPLIT_TEXT = _safe_bool("CAMELOT_STREAM_SPLIT_TEXT", True)
# edge_tol: tolerance for extending textedges vertically (default: 50)
CAMELOT_STREAM_EDGE_TOL = _safe_int("CAMELOT_STREAM_EDGE_TOL", 50)
# row_tol: tolerance for combining text into rows (camelot default: 2)
CAMELOT_STREAM_ROW_TOL = _safe_int("CAMELOT_STREAM_ROW_TOL", 2)
# column_tol: tolerance for merging column boundaries (camelot default: 0, lower = more columns detected)
CAMELOT_STREAM_COLUMN_TOL = _safe_int("CAMELOT_STREAM_COLUMN_TOL", 0)

# ============================================================================
# PDF to Image Configuration
# ============================================================================

PDF_IMAGE_FORMAT = os.getenv("PDF_IMAGE_FORMAT", "png").strip().lower()
PDF_IMAGE_DPI = _safe_int("PDF_IMAGE_DPI", 200, min_val=72)
PDF_IMAGE_THREAD_COUNT = _safe_int("PDF_IMAGE_THREAD_COUNT", 4, min_val=1)
PDF_IMAGE_USE_PDFTOCAIRO = _safe_bool("PDF_IMAGE_USE_PDFTOCAIRO", True)

# ============================================================================
# System Configuration
# ============================================================================

# External tools paths (Windows)
POPPLER_PATH = os.getenv("POPPLER_PATH", "")
GHOSTSCRIPT_PATH = os.getenv("GHOSTSCRIPT_PATH", "")

# Caching
CACHE_DURATION_HOURS = _safe_int("CACHE_DURATION_HOURS", 24)
AUTO_CLEAR_CACHE = _safe_bool("AUTO_CLEAR_CACHE", True)

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()
SAVE_PROCESSING_LOGS = _safe_bool("SAVE_PROCESSING_LOGS", True)
VERBOSE_PROGRESS = _safe_bool("VERBOSE_PROGRESS", True)

# Performance
MAX_CONCURRENT_FILES = _safe_int("MAX_CONCURRENT_FILES", 5, min_val=1)

# API cost guardrails
MAX_BATCH_FILES = _safe_int("MAX_BATCH_FILES", 100)
MAX_PAGES_PER_SESSION = _safe_int("MAX_PAGES_PER_SESSION", 1000)

# Document QnA configuration
MISTRAL_QNA_SYSTEM_PROMPT = os.getenv("MISTRAL_QNA_SYSTEM_PROMPT", "")  # Custom system prompt for QnA
MISTRAL_QNA_DOCUMENT_IMAGE_LIMIT = _safe_int("MISTRAL_QNA_DOCUMENT_IMAGE_LIMIT", 0)  # 0 = API default (8)
MISTRAL_QNA_DOCUMENT_PAGE_LIMIT = _safe_int("MISTRAL_QNA_DOCUMENT_PAGE_LIMIT", 0)  # 0 = API default (64)

# Batch processing advanced configuration
MISTRAL_BATCH_TIMEOUT_HOURS = _safe_int("MISTRAL_BATCH_TIMEOUT_HOURS", 24, min_val=1)

# Retry Configuration (for Mistral API calls)
# Set to 0 to disable retries entirely. Actual retry count is bounded by
# RETRY_MAX_ELAPSED_TIME_MS (the SDK does not support a max-attempts parameter).
MAX_RETRIES = _safe_int("MAX_RETRIES", 3)
RETRY_INITIAL_INTERVAL_MS = _safe_int("RETRY_INITIAL_INTERVAL_MS", 1000)  # 1 second
RETRY_MAX_INTERVAL_MS = _safe_int("RETRY_MAX_INTERVAL_MS", 10000)  # 10 seconds
RETRY_EXPONENT = _safe_float("RETRY_EXPONENT", 2.0, min_val=1.0)  # Exponential backoff
RETRY_MAX_ELAPSED_TIME_MS = _safe_int("RETRY_MAX_ELAPSED_TIME_MS", 60000)  # 1 minute
RETRY_CONNECTION_ERRORS = _safe_bool("RETRY_CONNECTION_ERRORS", True)

# ============================================================================
# Output Configuration
# ============================================================================

GENERATE_TXT_OUTPUT = _safe_bool("GENERATE_TXT_OUTPUT", True)
INCLUDE_METADATA = _safe_bool("INCLUDE_METADATA", True)
TABLE_OUTPUT_FORMATS = _safe_csv("TABLE_OUTPUT_FORMATS", "markdown,csv")
ENABLE_BATCH_METADATA = _safe_bool("ENABLE_BATCH_METADATA", True)

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
    "zip",  # ZIP archive (recursive extraction)
    "ipynb",  # Jupyter notebooks
    "msg",  # Outlook MSG (requires extract-msg)
    "txt",  # Plain text
    "rtf",  # Rich Text Format (via plugins)
    "rss",  # RSS feeds
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
        issues.append("WARNING: MISTRAL_API_KEY not set. Mistral OCR features will not work.")

    # Check LLM configuration (uses Mistral's OpenAI-compatible endpoint)
    if MARKITDOWN_ENABLE_LLM_DESCRIPTIONS and not MISTRAL_API_KEY:
        issues.append("WARNING: MARKITDOWN_ENABLE_LLM_DESCRIPTIONS is true but MISTRAL_API_KEY not set.")

    # Check Poppler on Windows
    if sys.platform == "win32" and not POPPLER_PATH:
        issues.append("INFO: POPPLER_PATH not set. PDF to image conversion may not work on Windows.")

    # Check for structured output flag conflicts
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

    # Check OCR quality threshold ordering
    if not (OCR_QUALITY_THRESHOLD_EXCELLENT >= OCR_QUALITY_THRESHOLD_GOOD >= OCR_QUALITY_THRESHOLD_ACCEPTABLE):
        issues.append(
            f"WARNING: OCR quality thresholds are not in descending order "
            f"(excellent={OCR_QUALITY_THRESHOLD_EXCELLENT}, good={OCR_QUALITY_THRESHOLD_GOOD}, "
            f"acceptable={OCR_QUALITY_THRESHOLD_ACCEPTABLE}). Quality ratings may be nonsensical."
        )

    # Validate LOG_LEVEL
    valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if LOG_LEVEL not in valid_log_levels:
        issues.append(f"WARNING: LOG_LEVEL={LOG_LEVEL!r} is invalid. Use one of {sorted(valid_log_levels)}.")

    # Validate MISTRAL_DOCUMENT_SCHEMA_TYPE
    valid_schema_types = {"auto", "invoice", "financial_statement", "contract", "form", "generic"}
    if MISTRAL_DOCUMENT_SCHEMA_TYPE not in valid_schema_types:
        issues.append(
            f"WARNING: MISTRAL_DOCUMENT_SCHEMA_TYPE={MISTRAL_DOCUMENT_SCHEMA_TYPE!r} is invalid. "
            f"Use one of {sorted(valid_schema_types)}."
        )

    # Validate MISTRAL_TABLE_FORMAT
    valid_mistral_table_formats = {"", "markdown", "html"}
    if MISTRAL_TABLE_FORMAT not in valid_mistral_table_formats:
        issues.append(
            f"WARNING: MISTRAL_TABLE_FORMAT={MISTRAL_TABLE_FORMAT!r} is invalid. " "Use '', 'markdown', or 'html'."
        )

    # Validate TABLE_OUTPUT_FORMATS
    invalid_table_output_formats = set(TABLE_OUTPUT_FORMATS) - {"markdown", "csv"}
    if invalid_table_output_formats:
        issues.append(
            f"WARNING: Unsupported TABLE_OUTPUT_FORMATS={sorted(invalid_table_output_formats)}. "
            "Supported values: ['csv', 'markdown']."
        )

    # Security-relevant configuration warnings
    if MARKITDOWN_ENABLE_PLUGINS:
        issues.append(
            "SECURITY: MARKITDOWN_ENABLE_PLUGINS is true. "
            "Third-party plugins increase the parser attack surface. "
            "Only enable if you trust all installed plugins."
        )

    if MARKITDOWN_KEEP_DATA_URIS:
        issues.append(
            "SECURITY: MARKITDOWN_KEEP_DATA_URIS is true. "
            "Output Markdown will contain embedded data URIs which pose "
            "an XSS risk if served to browsers without sanitization."
        )

    if MISTRAL_SIGNED_URL_EXPIRY > 24:
        issues.append(
            f"SECURITY: MISTRAL_SIGNED_URL_EXPIRY={MISTRAL_SIGNED_URL_EXPIRY}h is unusually long. "
            "Signed URLs grant access to uploaded documents; consider <=24h."
        )

    return issues


# ============================================================================
# Initialization
# ============================================================================

_initialized = False
_init_lock = threading.Lock()


def initialize() -> List[str]:
    """
    Initialize the application: create directories and validate config.

    Safe to call multiple times; only runs once.  Thread-safe via
    double-checked locking.

    Returns:
        List of configuration warning/error messages (empty if all OK)
    """
    global _initialized
    if _initialized:
        return []
    with _init_lock:
        if _initialized:
            return []
        ensure_directories()
        issues = validate_configuration()
        _initialized = True
        return issues


# Run as a standalone config diagnostic: ``python config.py``
if __name__ == "__main__":  # pragma: no cover
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
