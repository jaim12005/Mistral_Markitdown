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
    """Load environment variables from .env using python-dotenv if available.

    Falls back to a minimal key=value parser for .env or env file when
    python-dotenv isn't installed.
    """
    try:
        from dotenv import load_dotenv, find_dotenv  # type: ignore

        dotenv_path = find_dotenv(filename=".env", usecwd=True)
        if dotenv_path:
            load_dotenv(dotenv_path, override=False)
        else:
            # Fallback to sibling 'env' file if present
            alt = APP_ROOT / "env"
            if alt.exists() and alt.is_file():
                load_dotenv(str(alt), override=False)
    except Exception:
        # Fallback: light parser
        for fname in (".env", "env"):
            p = APP_ROOT / fname
            if not (p.exists() and p.is_file()):
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


def get_env_list(key: str, default: list) -> list:
    """Get environment variable as a list (comma-separated)."""
    value = os.environ.get(key, ",".join(default))
    return [item.strip() for item in value.split(",") if item.strip()]


def get_env_str(key: str, default: str) -> str:
    return os.environ.get(key, default)


# --- System Path Configuration ---
# Path to Poppler binary installation, required for PDF-to-image conversion features.
POPPLER_PATH = os.environ.get("POPPLER_PATH", "")
LOG_LEVEL = get_env_str("LOG_LEVEL", "INFO").upper()

# --- Mistral AI API Configuration ---
# Your main API key for authenticating with the Mistral platform.
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "").strip()
# The specific OCR model to use for document processing.
# Updated to support latest models as of August 2025
MISTRAL_MODEL = os.environ.get("MISTRAL_OCR_MODEL", "mistral-ocr-latest")
# Alternative models for different use cases:
# - "mistral-ocr-latest" (default): Latest OCR model (currently mistral-ocr-2505)
# - "mistral-medium-latest": Multimodal model for documents with images/text (mistral-medium-2508)
# - "pixtral-large-latest": Advanced multimodal model for complex image understanding (pixtral-large-2411)
# - "codestral-latest": Advanced coding model for processing code-heavy documents (codestral-2508)
# - "magistral-medium-latest": Frontier-class reasoning model (magistral-medium-2507)
# - "ministral-8b-latest": Efficient edge model (ministral-8b-2410)
# - "ministral-3b-latest": World's best edge model (ministral-3b-2410)
# If True, includes base64-encoded images in the OCR response.
MISTRAL_INCLUDE_IMAGES = get_env_bool("MISTRAL_INCLUDE_IMAGES", True)
# If True, requests AI-generated descriptions for images found in the document.
MISTRAL_INCLUDE_IMAGE_ANNOTATIONS = get_env_bool(
    "MISTRAL_INCLUDE_IMAGE_ANNOTATIONS", True
)
# If True, saves the full JSON response from Mistral to the 'logs' directory for debugging.
SAVE_MISTRAL_JSON = get_env_bool("SAVE_MISTRAL_JSON", False)
# If True, collapses MarkItDown sections when OCR tables are high quality. Set to False to always show full content.
GATE_MARKITDOWN_WHEN_OCR_GOOD = get_env_bool("GATE_MARKITDOWN_WHEN_OCR_GOOD", True)
# Files larger than this (in MB) are uploaded via the Files API rather than sent inline.
LARGE_FILE_THRESHOLD_MB = get_env_int("LARGE_FILE_THRESHOLD_MB", 45)
# Timeout in seconds for individual HTTP requests to the Mistral API.
MISTRAL_TIMEOUT = get_env_int("MISTRAL_HTTP_TIMEOUT", 300)
# Enable automatic model selection based on document characteristics
MISTRAL_AUTO_MODEL_SELECTION = get_env_bool("MISTRAL_AUTO_MODEL_SELECTION", True)
# Preferred models for different document types (comma-separated)
MISTRAL_PREFERRED_MODELS = get_env_list(
    "MISTRAL_PREFERRED_MODELS",
    [
        "mistral-ocr-latest",  # PRIORITY: Best for PDFs with tables (SWE review fix)
        "pixtral-large-latest",  # Best for complex images
        "mistral-medium-latest",  # Best for multimodal documents
        "codestral-latest",  # Best for code documents
    ],
)

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
# Strategy for table extraction: 'ocr_only', 'text_only', 'auto'.
MARKITDOWN_TABLE_STRATEGY = os.environ.get("MARKITDOWN_TABLE_STRATEGY", "auto")
# Strategy for image extraction: 'extract', 'ignore', 'auto'.
MARKITDOWN_IMAGE_STRATEGY = os.environ.get("MARKITDOWN_IMAGE_STRATEGY", "auto")
# PDF processing mode if Azure is not used: 'auto', 'text', or 'ocr'.
MARKITDOWN_PDF_MODE = os.environ.get("MARKITDOWN_PDF_MODE", "auto")
# If True, enables Markitdown's third-party plugin system.
MARKITDOWN_ENABLE_PLUGINS = get_env_bool("MARKITDOWN_ENABLE_PLUGINS", False)

# --- Enhanced Markitdown Configuration ---
# Enable experimental features in Markitdown
MARKITDOWN_EXPERIMENTAL = get_env_bool("MARKITDOWN_EXPERIMENTAL", False)
# Custom processing options for different file types
MARKITDOWN_CUSTOM_OPTIONS = get_env_bool("MARKITDOWN_CUSTOM_OPTIONS", True)
# Enable Markitdown's built-in caching for repeated files
MARKITDOWN_USE_CACHE = get_env_bool("MARKITDOWN_USE_CACHE", True)
# Maximum file size for Markitdown processing (in MB)
MARKITDOWN_MAX_FILE_SIZE_MB = get_env_int("MARKITDOWN_MAX_FILE_SIZE_MB", 100)
# Enable advanced table detection algorithms
MARKITDOWN_ADVANCED_TABLES = get_env_bool("MARKITDOWN_ADVANCED_TABLES", True)
# Enable enhanced image processing and OCR
MARKITDOWN_ENHANCED_IMAGES = get_env_bool("MARKITDOWN_ENHANCED_IMAGES", True)
# Custom image quality settings (1-100, higher = better quality but larger files)
MARKITDOWN_IMAGE_QUALITY = get_env_int("MARKITDOWN_IMAGE_QUALITY", 90)
# Enable parallel processing for large documents
MARKITDOWN_PARALLEL_PROCESSING = get_env_bool("MARKITDOWN_PARALLEL_PROCESSING", True)
# Number of parallel workers for document processing
# Default: min(cpu_count or 4, 8) - uses CPU count with fallback to 4, capped at 8 workers max
MARKITDOWN_WORKERS = get_env_int("MARKITDOWN_WORKERS", min(os.cpu_count() or 4, 8))

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

# --- Advanced Mistral AI Features ---
# Enable function calling for structured data extraction
MISTRAL_ENABLE_FUNCTIONS = get_env_bool("MISTRAL_ENABLE_FUNCTIONS", False)
# Enable structured outputs with JSON schema
MISTRAL_ENABLE_STRUCTURED_OUTPUT = get_env_bool(
    "MISTRAL_ENABLE_STRUCTURED_OUTPUT", False
)
# Schema type for structured output ('auto', 'financial_statement', 'document_analysis', 'image_description')
MISTRAL_STRUCTURED_SCHEMA_TYPE = os.environ.get(
    "MISTRAL_STRUCTURED_SCHEMA_TYPE", "auto"
)
# Enable multi-turn conversations for complex analysis
MISTRAL_ENABLE_MULTI_TURN = get_env_bool("MISTRAL_ENABLE_MULTI_TURN", False)
# Maximum number of conversation turns
MISTRAL_MAX_TURNS = get_env_int("MISTRAL_MAX_TURNS", 3)

# --- Enhanced Image Processing ---
# Enable advanced image quality analysis and optimization
MISTRAL_ENABLE_IMAGE_OPTIMIZATION = get_env_bool(
    "MISTRAL_ENABLE_IMAGE_OPTIMIZATION", True
)
# Enable image preprocessing to improve OCR accuracy
MISTRAL_ENABLE_IMAGE_PREPROCESSING = get_env_bool(
    "MISTRAL_ENABLE_IMAGE_PREPROCESSING", False
)
# Maximum image dimension for processing (longest side in pixels)
MISTRAL_MAX_IMAGE_DIMENSION = get_env_int("MISTRAL_MAX_IMAGE_DIMENSION", 2048)
# Image quality threshold for using advanced models (0-100 in config, converted to 0.0-1.0 internally)
MISTRAL_IMAGE_QUALITY_THRESHOLD = (
    get_env_int("MISTRAL_IMAGE_QUALITY_THRESHOLD", 70) / 100.0
)

# Constants
MONTHS = [
    "Beginning Balance",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
    "Current Balance",
]
M_SHORT = [
    "Beginning",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
    "Current",
]

# Initialize directories
setup_directories()


# --- Runtime overrides ---
def override_paths(
    input_dir: str | None = None,
    out_md: str | None = None,
    out_txt: str | None = None,
    out_img: str | None = None,
) -> None:
    """Optionally override key IO paths at runtime then (re)create dirs."""
    global INPUT_DIR, OUT_MD, OUT_TXT, OUT_IMG
    if input_dir:
        INPUT_DIR = Path(input_dir).resolve()
    if out_md:
        OUT_MD = Path(out_md).resolve()
    if out_txt:
        OUT_TXT = Path(out_txt).resolve()
    if out_img:
        OUT_IMG = Path(out_img).resolve()
    setup_directories()


def set_workers(workers: int) -> None:
    """Override worker count for parallel processing runtimes."""
    global MARKITDOWN_WORKERS
    try:
        workers = int(workers)
        MARKITDOWN_WORKERS = max(1, min(workers, 64))
    except Exception:
        pass
