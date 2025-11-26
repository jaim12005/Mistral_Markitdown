"""
Enhanced Document Converter v2.1.1 - Configuration Module

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

# Optional API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
AZURE_DOC_INTEL_ENDPOINT = os.getenv("AZURE_DOC_INTEL_ENDPOINT", "")
AZURE_DOC_INTEL_KEY = os.getenv("AZURE_DOC_INTEL_KEY", "")

# ============================================================================
# Mistral OCR Configuration
# ============================================================================

# Model selection - ALWAYS use mistral-ocr-latest for OCR
MISTRAL_OCR_MODEL = os.getenv("MISTRAL_OCR_MODEL", "mistral-ocr-latest")

# OCR options
MISTRAL_INCLUDE_IMAGES = os.getenv("MISTRAL_INCLUDE_IMAGES", "true").lower() == "true"
SAVE_MISTRAL_JSON = (
    os.getenv("SAVE_MISTRAL_JSON", "true").lower() == "true"
)  # Default true for quality assessment

# File upload management
CLEANUP_OLD_UPLOADS = os.getenv("CLEANUP_OLD_UPLOADS", "true").lower() == "true"
UPLOAD_RETENTION_DAYS = int(os.getenv("UPLOAD_RETENTION_DAYS", "7"))  # Delete files older than N days

# OCR Quality Assessment Thresholds (0-100 scale)
OCR_QUALITY_THRESHOLD_EXCELLENT = int(os.getenv("OCR_QUALITY_THRESHOLD_EXCELLENT", "80"))
OCR_QUALITY_THRESHOLD_GOOD = int(os.getenv("OCR_QUALITY_THRESHOLD_GOOD", "60"))
OCR_QUALITY_THRESHOLD_ACCEPTABLE = int(os.getenv("OCR_QUALITY_THRESHOLD_ACCEPTABLE", "40"))

# OCR Quality Detection Thresholds
OCR_MIN_TEXT_LENGTH = int(os.getenv("OCR_MIN_TEXT_LENGTH", "50"))
OCR_MIN_DIGIT_COUNT = int(os.getenv("OCR_MIN_DIGIT_COUNT", "20"))
OCR_MIN_UNIQUENESS_RATIO = float(os.getenv("OCR_MIN_UNIQUENESS_RATIO", "0.3"))
OCR_MAX_PHRASE_REPETITIONS = int(os.getenv("OCR_MAX_PHRASE_REPETITIONS", "5"))
OCR_MIN_AVG_LINE_LENGTH = int(os.getenv("OCR_MIN_AVG_LINE_LENGTH", "10"))

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

# Image optimization
MISTRAL_ENABLE_IMAGE_OPTIMIZATION = (
    os.getenv("MISTRAL_ENABLE_IMAGE_OPTIMIZATION", "true").lower() == "true"
)
MISTRAL_ENABLE_IMAGE_PREPROCESSING = (
    os.getenv("MISTRAL_ENABLE_IMAGE_PREPROCESSING", "false").lower() == "true"
)
MISTRAL_MAX_IMAGE_DIMENSION = int(os.getenv("MISTRAL_MAX_IMAGE_DIMENSION", "2048"))
MISTRAL_IMAGE_QUALITY_THRESHOLD = int(
    os.getenv("MISTRAL_IMAGE_QUALITY_THRESHOLD", "70")
)

# ============================================================================
# MarkItDown Configuration
# ============================================================================

# LLM integration
MARKITDOWN_USE_LLM = os.getenv("MARKITDOWN_USE_LLM", "false").lower() == "true"
MARKITDOWN_LLM_MODEL = os.getenv("MARKITDOWN_LLM_MODEL", "gpt-4-vision-preview")
MARKITDOWN_ENABLE_PLUGINS = (
    os.getenv("MARKITDOWN_ENABLE_PLUGINS", "false").lower() == "true"
)

# File size limit (for determining when to use Mistral Files API)
MARKITDOWN_MAX_FILE_SIZE_MB = int(os.getenv("MARKITDOWN_MAX_FILE_SIZE_MB", "100"))

# ============================================================================
# Table Extraction Configuration
# ============================================================================

# Camelot quality thresholds
CAMELOT_MIN_ACCURACY = float(os.getenv("CAMELOT_MIN_ACCURACY", "75.0"))  # Minimum accuracy % to accept table
CAMELOT_MAX_WHITESPACE = float(os.getenv("CAMELOT_MAX_WHITESPACE", "30.0"))  # Maximum whitespace % to accept

# ============================================================================
# PDF to Image Configuration
# ============================================================================

PDF_IMAGE_FORMAT = os.getenv("PDF_IMAGE_FORMAT", "png")  # png, jpeg, ppm, tiff
PDF_IMAGE_DPI = int(os.getenv("PDF_IMAGE_DPI", "200"))  # Image resolution
PDF_IMAGE_THREAD_COUNT = int(os.getenv("PDF_IMAGE_THREAD_COUNT", "4"))  # Concurrent conversion threads
PDF_IMAGE_USE_PDFTOCAIRO = os.getenv("PDF_IMAGE_USE_PDFTOCAIRO", "true").lower() == "true"  # Better quality

# ============================================================================
# System Configuration
# ============================================================================

# External tools paths (Windows)
POPPLER_PATH = os.getenv("POPPLER_PATH", "")
GHOSTSCRIPT_PATH = os.getenv("GHOSTSCRIPT_PATH", "")

# Caching
CACHE_DURATION_HOURS = int(os.getenv("CACHE_DURATION_HOURS", "24"))
AUTO_CLEAR_CACHE = os.getenv("AUTO_CLEAR_CACHE", "true").lower() == "true"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
SAVE_PROCESSING_LOGS = os.getenv("SAVE_PROCESSING_LOGS", "true").lower() == "true"
VERBOSE_PROGRESS = os.getenv("VERBOSE_PROGRESS", "true").lower() == "true"

# Performance
MAX_CONCURRENT_FILES = int(os.getenv("MAX_CONCURRENT_FILES", "5"))

# Async operations
ENABLE_ASYNC_OPERATIONS = os.getenv("ENABLE_ASYNC_OPERATIONS", "true").lower() == "true"

# Streaming (real-time progress feedback)
ENABLE_STREAMING = os.getenv("ENABLE_STREAMING", "false").lower() == "true"

# Retry Configuration (for Mistral API calls)
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_INITIAL_INTERVAL_MS = int(
    os.getenv("RETRY_INITIAL_INTERVAL_MS", "1000")
)  # 1 second
RETRY_MAX_INTERVAL_MS = int(os.getenv("RETRY_MAX_INTERVAL_MS", "10000"))  # 10 seconds
RETRY_EXPONENT = float(os.getenv("RETRY_EXPONENT", "2.0"))  # Exponential backoff
RETRY_MAX_ELAPSED_TIME_MS = int(
    os.getenv("RETRY_MAX_ELAPSED_TIME_MS", "60000")
)  # 1 minute
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

# Latest Mistral models (as of January 2025)
# NOTE: Model availability and specifications may change. Verify at https://docs.mistral.ai/
MISTRAL_MODELS = {
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
        "name": "Mistral OCR 2505",
        "description": "Dedicated OCR service",
        "best_for": ["ocr", "text_extraction"],
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
    "mp3",
    "wav",
    "m4a",
    "flac",  # Audio (requires plugins)
}

MISTRAL_OCR_SUPPORTED = {
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "bmp",
    "docx",
    "pptx",
}

PDF_EXTENSIONS = {"pdf"}
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "tiff"}
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

    # Check LLM configuration
    if MARKITDOWN_USE_LLM and not OPENAI_API_KEY:
        issues.append("WARNING: MARKITDOWN_USE_LLM is true but OPENAI_API_KEY not set.")

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

# Ensure all directories exist
ensure_directories()

# Validate configuration on import
_config_issues = validate_configuration()
if _config_issues and __name__ == "__main__":
    print("\n".join(_config_issues))
