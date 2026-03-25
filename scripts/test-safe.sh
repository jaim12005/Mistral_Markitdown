#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$ROOT_DIR/env"
REQ_MAIN="$ROOT_DIR/requirements.txt"
REQ_DEV="$ROOT_DIR/requirements-dev.txt"

usage() {
  cat <<'EOF'
Usage: scripts/test-safe.sh [pytest-args...]

Run pytest with a known-good Python (>=3.10) and required test deps installed,
so local Python/version/plugin mismatches don't produce noisy failures.

Examples:
  scripts/test-safe.sh
  scripts/test-safe.sh tests/test_utils.py::TestYAMLFrontmatter
  scripts/test-safe.sh -q -o addopts='' tests/test_mistral_converter.py::TestValidateDocumentUrl
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

python_at_least_310() {
  local bin="$1"
  "$bin" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
}

pick_base_python() {
  local -a candidates=()
  if [[ -n "${MISTRAL_MARKITDOWN_PYTHON:-}" ]]; then
    candidates+=("$MISTRAL_MARKITDOWN_PYTHON")
  fi

  local name
  for name in python3.12 python3.11 python3.10 python3; do
    if command -v "$name" >/dev/null 2>&1; then
      candidates+=("$(command -v "$name")")
    fi
  done

  for name in /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11 /usr/local/bin/python3.12 /usr/local/bin/python3.11 /usr/bin/python3; do
    if [[ -x "$name" ]]; then
      candidates+=("$name")
    fi
  done

  local bin
  for bin in "${candidates[@]}"; do
    if [[ -x "$bin" ]] && python_at_least_310 "$bin"; then
      printf '%s\n' "$bin"
      return 0
    fi
  done

  return 1
}

ensure_venv() {
  local base_py="$1"
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "INFO: creating virtualenv at $VENV_DIR" >&2
    "$base_py" -m venv "$VENV_DIR"
  fi
}

venv_missing_test_deps() {
  "$VENV_DIR/bin/python" - <<'PY' >/dev/null 2>&1
import importlib.util
mods = ["pytest", "pytest_cov", "dotenv"]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
raise SystemExit(0 if missing else 1)
PY
}

install_test_deps() {
  echo "INFO: installing test dependencies into $VENV_DIR (may take a minute)..." >&2
  "$VENV_DIR/bin/python" -m pip install -q --upgrade pip
  "$VENV_DIR/bin/pip" install -q -r "$REQ_MAIN" -r "$REQ_DEV"
}

if ! BASE_PY="$(pick_base_python)"; then
  echo "ERROR: no compatible Python found (need >=3.10)" >&2
  exit 2
fi

ensure_venv "$BASE_PY"

if venv_missing_test_deps; then
  install_test_deps
fi

cd "$ROOT_DIR"

if [[ $# -eq 0 ]]; then
  exec "$VENV_DIR/bin/python" -m pytest tests/
else
  exec "$VENV_DIR/bin/python" -m pytest "$@"
fi
