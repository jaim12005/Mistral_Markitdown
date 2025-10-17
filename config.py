"""
Enhanced Document Converter v2.1 - Configuration Module

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
SAVE_MISTRAL_JSON = os.getenv("SAVE_MISTRAL_JSON", "false").lower() == "true"

# Advanced features
MISTRAL_ENABLE_FUNCTIONS = os.getenv("MISTRAL_ENABLE_FUNCTIONS", "false").lower() == "true"
MISTRAL_ENABLE_STRUCTURED_OUTPUT = os.getenv("MISTRAL_ENABLE_STRUCTURED_OUTPUT", "false").lower() == "true"
MISTRAL_STRUCTURED_SCHEMA_TYPE = os.getenv("MISTRAL_STRUCTURED_SCHEMA_TYPE", "auto")

# Image optimization
MISTRAL_ENABLE_IMAGE_OPTIMIZATION = os.getenv("MISTRAL_ENABLE_IMAGE_OPTIMIZATION", "true").lower() == "true"
MISTRAL_ENABLE_IMAGE_PREPROCESSING = os.getenv("MISTRAL_ENABLE_IMAGE_PREPROCESSING", "false").lower() == "true"
MISTRAL_MAX_IMAGE_DIMENSION = int(os.getenv("MISTRAL_MAX_IMAGE_DIMENSION", "2048"))
MISTRAL_IMAGE_QUALITY_THRESHOLD = int(os.getenv("MISTRAL_IMAGE_QUALITY_THRESHOLD", "70"))

# ============================================================================
# MarkItDown Configuration
# ============================================================================

# LLM integration
MARKITDOWN_USE_LLM = os.getenv("MARKITDOWN_USE_LLM", "false").lower() == "true"
MARKITDOWN_LLM_MODEL = os.getenv("MARKITDOWN_LLM_MODEL", "gpt-4-vision-preview")
MARKITDOWN_ENABLE_PLUGINS = os.getenv("MARKITDOWN_ENABLE_PLUGINS", "false").lower() == "true"

# File size limit (for determining when to use Mistral Files API)
MARKITDOWN_MAX_FILE_SIZE_MB = int(os.getenv("MARKITDOWN_MAX_FILE_SIZE_MB", "100"))

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
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "1"))

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

# Latest Mistral models (as of August 2025)
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

def select_best_model(
    file_type: str,
    content_analysis: Optional[dict] = None
) -> str:
    """
    Select Mistral model for OCR processing.

    ALWAYS returns mistral-ocr-latest for OCR tasks.
    This is the dedicated OCR model and should never be substituted.

    Args:
        file_type: The type of file being processed (pdf, image, docx, etc.)
        content_analysis: Optional dict with keys like 'has_images', 'has_code', etc.

    Returns:
        Model identifier string (always mistral-ocr-latest for OCR)
    """
    # ALWAYS use mistral-ocr-latest for OCR tasks
    # Never substitute with pixtral, codestral, or other models
    return MISTRAL_OCR_MODEL

# ============================================================================
# File Type Configuration
# ============================================================================

# Supported file extensions
MARKITDOWN_SUPPORTED = {
    "docx", "doc", "pptx", "ppt", "xlsx", "xls",
    "html", "htm", "csv", "json", "xml", "epub",
    "pdf", "png", "jpg", "jpeg", "gif", "bmp",
    "mp3", "wav", "m4a", "flac",  # Audio (requires plugins)
}

MISTRAL_OCR_SUPPORTED = {
    "pdf", "png", "jpg", "jpeg", "gif", "bmp",
    "docx", "pptx",
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
        issues.append("WARNING: MISTRAL_API_KEY not set. Mistral OCR features will not work.")

    # Check LLM configuration
    if MARKITDOWN_USE_LLM and not OPENAI_API_KEY:
        issues.append("WARNING: MARKITDOWN_USE_LLM is true but OPENAI_API_KEY not set.")

    # Check Poppler on Windows
    if sys.platform == "win32" and not POPPLER_PATH:
        issues.append("INFO: POPPLER_PATH not set. PDF to image conversion may not work on Windows.")

    # Check model preferences
    if MISTRAL_AUTO_MODEL_SELECTION and not MISTRAL_PREFERRED_MODELS:
        issues.append("WARNING: MISTRAL_AUTO_MODEL_SELECTION is true but no preferred models configured.")

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
