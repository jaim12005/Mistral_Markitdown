import os
from pathlib import Path

# --- Configuration and Setup ---
APP_ROOT = Path(__file__).resolve().parent
INPUT_DIR = (APP_ROOT / "input").resolve()
OUT_MD = (APP_ROOT / "output_md").resolve()
OUT_TXT = (APP_ROOT / "output_txt").resolve()
OUT_IMG = (APP_ROOT / "output_images").resolve()
LOG_DIR = (APP_ROOT / "logs").resolve()
CACHE_DIR = (APP_ROOT / "cache").resolve()


def setup_directories():
    """Create necessary directories."""
    for p in (INPUT_DIR, OUT_MD, OUT_TXT, OUT_IMG, LOG_DIR, CACHE_DIR):
        p.mkdir(parents=True, exist_ok=True)


def load_env_like_files() -> None:
    """Load key=value from ./.env and ./env if present (prefers .env)."""
    for fname in (".env", "env"):
        p = (APP_ROOT / fname)
        if not (p.exists() and p.is_file()):  # Ensure it's a file, not a directory
            continue
        try:
            for raw in p.read_text(encoding="utf-8").splitlines():
                raw = raw.strip()
                if not raw or raw.startswith("#") or "=" not in raw:
                    continue
                k, v = raw.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and (k not in os.environ):
                    os.environ[k] = v
        except Exception:
            pass


# Load environment variables immediately
load_env_like_files()

# --- Enhanced Configuration Loading Helpers ---
def get_env_bool(key: str, default: bool) -> bool:
    value = os.environ.get(key, str(default)).lower()
    return value in ("true", "1", "yes")


def get_env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except ValueError:
        return default


# --- System Path Configuration ---
# Path to Poppler binary installation, required for PDF-to-image conversion features.
POPPLER_PATH = os.environ.get("POPPLER_PATH", "")

# --- Mistral AI API Configuration ---
# Your main API key for authenticating with the Mistral platform.
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "").strip()
# The specific OCR model to use for document processing.
MISTRAL_MODEL = os.environ.get("MISTRAL_OCR_MODEL", "mistral-ocr-latest")
# Alternative models for different use cases:
# - "mistral-medium" for multimodal documents with images/text
# - "pixtral-large" for advanced image understanding
# - "codestral" for code-heavy documents
# If True, includes base64-encoded images in the OCR response.
MISTRAL_INCLUDE_IMAGES = get_env_bool("MISTRAL_INCLUDE_IMAGES", True)
# If True, requests AI-generated descriptions for images found in the document.
MISTRAL_INCLUDE_IMAGE_ANNOTATIONS = get_env_bool("MISTRAL_INCLUDE_IMAGE_ANNOTATIONS", True)
# If True, saves the full JSON response from Mistral to the 'logs' directory for debugging.
SAVE_MISTRAL_JSON = get_env_bool("SAVE_MISTRAL_JSON", False)
# If True, collapses MarkItDown sections when OCR tables are high quality. Set to False to always show full content.
GATE_MARKITDOWN_WHEN_OCR_GOOD = get_env_bool("GATE_MARKITDOWN_WHEN_OCR_GOOD", True)
# Files larger than this (in MB) are uploaded via the Files API rather than sent inline.
LARGE_FILE_THRESHOLD_MB = get_env_int("LARGE_FILE_THRESHOLD_MB", 45)
# Timeout in seconds for individual HTTP requests to the Mistral API.
MISTRAL_TIMEOUT = get_env_int("MISTRAL_HTTP_TIMEOUT", 300)

# --- Markitdown Engine Configuration ---
# If True, uses an OpenAI-compatible model to generate image descriptions.
MARKITDOWN_USE_LLM = get_env_bool("MARKITDOWN_USE_LLM", False)
# The model name to use for LLM-based image descriptions (e.g., 'gpt-4o-mini').
MARKITDOWN_LLM_MODEL = os.environ.get("MARKITDOWN_LLM_MODEL", "gpt-4o-mini")
# The API key for the LLM service (e.g., OpenAI).
MARKITDOWN_LLM_KEY = os.environ.get("OPENAI_API_KEY", "")
# Endpoint for using Azure Document Intelligence as the backend for Markitdown.
AZURE_DOC_INTEL_ENDPOINT = os.environ.get("AZURE_DOC_INTEL_ENDPOINT", "")
AZURE_DOC_INTEL_KEY = os.environ.get("AZURE_DOC_INTEL_KEY", "")

# --- Markitdown Advanced Settings ---
# Strategy for table extraction: 'ocr_only', 'text_only', or 'auto'.
MARKITDOWN_TABLE_STRATEGY = os.environ.get("MARKITDOWN_TABLE_STRATEGY", "auto")
# Strategy for image extraction: 'extract', 'ignore', or 'auto'.
MARKITDOWN_IMAGE_STRATEGY = os.environ.get("MARKITDOWN_IMAGE_STRATEGY", "auto")
# PDF processing mode if Azure is not used: 'auto', 'text', or 'ocr'.
MARKITDOWN_PDF_MODE = os.environ.get("MARKITDOWN_PDF_MODE", "auto")
# If True, enables Markitdown's third-party plugin system.
MARKITDOWN_ENABLE_PLUGINS = get_env_bool("MARKITDOWN_ENABLE_PLUGINS", False)

# --- Performance & Batch Processing ---
# Number of files to process concurrently in standard batch mode.
BATCH_SIZE = get_env_int("BATCH_SIZE", 5)
# Maximum number of retries for failed network requests (e.g., API calls).
MAX_RETRIES = get_env_int("MAX_RETRIES", 3)
# Base delay in seconds for exponential backoff between retries.
RETRY_DELAY = get_env_int("RETRY_DELAY", 5)

# --- Caching Configuration ---
# Duration in hours to retain cached OCR results.
CACHE_DURATION_HOURS = get_env_int("CACHE_DURATION_HOURS", 24)
# Enable PDF table extraction during batch/enhanced modes
BATCH_EXTRACT_TABLES = get_env_bool("BATCH_EXTRACT_TABLES", False)

# Constants
MONTHS = [
    "Beginning Balance", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December", "Current Balance"
]
M_SHORT = [
    "Beginning", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December", "Current"
]

# Initialize directories
setup_directories()
