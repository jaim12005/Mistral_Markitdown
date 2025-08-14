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
    # Prefer .env over env; do not override existing OS envs
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

# Load configuration from environment variables
POPPLER_PATH = os.environ.get("POPPLER_PATH", "")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "").strip()
MISTRAL_MODEL = os.environ.get("MISTRAL_OCR_MODEL", "mistral-ocr-latest")
MISTRAL_INCLUDE_IMAGES = os.environ.get("MISTRAL_INCLUDE_IMAGES", "true").lower() in ("true", "1")
SAVE_MISTRAL_JSON = os.environ.get("SAVE_MISTRAL_JSON", "false").lower() in ("true", "1")
LARGE_FILE_THRESHOLD_MB = int(os.environ.get("LARGE_FILE_THRESHOLD_MB", "45"))
# Enhanced Markitdown configuration
MARKITDOWN_USE_LLM = os.environ.get("MARKITDOWN_USE_LLM", "false").lower() in ("true", "1")
MARKITDOWN_LLM_MODEL = os.environ.get("MARKITDOWN_LLM_MODEL", "gpt-4o-mini")
MARKITDOWN_LLM_KEY = os.environ.get("OPENAI_API_KEY", "")
AZURE_DOC_INTEL_ENDPOINT = os.environ.get("AZURE_DOC_INTEL_ENDPOINT", "")
AZURE_DOC_INTEL_KEY = os.environ.get("AZURE_DOC_INTEL_KEY", "")
# Batch processing configuration
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "5"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.environ.get("RETRY_DELAY", "5"))

try:
    MISTRAL_TIMEOUT = int(os.environ.get("MISTRAL_HTTP_TIMEOUT", "300"))
except ValueError:
    MISTRAL_TIMEOUT = 300

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
