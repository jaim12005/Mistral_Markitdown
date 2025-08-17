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
        if not p.exists():
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


# Load configuration from environment variables
POPPLER_PATH = os.environ.get("POPPLER_PATH", "")

# Mistral Configuration
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "").strip()
MISTRAL_MODEL = os.environ.get("MISTRAL_OCR_MODEL", "mistral-ocr-latest")
MISTRAL_INCLUDE_IMAGES = get_env_bool("MISTRAL_INCLUDE_IMAGES", True)
MISTRAL_INCLUDE_IMAGE_ANNOTATIONS = get_env_bool("MISTRAL_INCLUDE_IMAGE_ANNOTATIONS", True)
SAVE_MISTRAL_JSON = get_env_bool("SAVE_MISTRAL_JSON", False)
LARGE_FILE_THRESHOLD_MB = get_env_int("LARGE_FILE_THRESHOLD_MB", 45)
MISTRAL_TIMEOUT = get_env_int("MISTRAL_HTTP_TIMEOUT", 300)

# Enhanced Markitdown configuration
MARKITDOWN_USE_LLM = get_env_bool("MARKITDOWN_USE_LLM", False)
MARKITDOWN_LLM_MODEL = os.environ.get("MARKITDOWN_LLM_MODEL", "gpt-4o-mini")
MARKITDOWN_LLM_KEY = os.environ.get("OPENAI_API_KEY", "")
AZURE_DOC_INTEL_ENDPOINT = os.environ.get("AZURE_DOC_INTEL_ENDPOINT", "")
AZURE_DOC_INTEL_KEY = os.environ.get("AZURE_DOC_INTEL_KEY", "")

# Markitdown Advanced Settings
MARKITDOWN_TABLE_STRATEGY = os.environ.get("MARKITDOWN_TABLE_STRATEGY", "auto")
MARKITDOWN_IMAGE_STRATEGY = os.environ.get("MARKITDOWN_IMAGE_STRATEGY", "auto")
MARKITDOWN_PDF_MODE = os.environ.get("MARKITDOWN_PDF_MODE", "auto")

# Batch processing configuration
BATCH_SIZE = get_env_int("BATCH_SIZE", 5)
MAX_RETRIES = get_env_int("MAX_RETRIES", 3)
RETRY_DELAY = get_env_int("RETRY_DELAY", 5)

# Caching Configuration
CACHE_DURATION_HOURS = get_env_int("CACHE_DURATION_HOURS", 24)

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
