#!/bin/bash

# Enhanced Document Converter - Quick Start Script (Linux/macOS)

set -e

echo "=========================================="
echo "Enhanced Document Converter - Quick Setup"
echo "=========================================="
echo

# Check Python
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ Python 3.10+ is required but not found."
  exit 1
fi
echo "✓ Python: $(python3 --version)"

# Create venv
if [ ! -d "env" ]; then
  echo "Creating virtual environment in ./env ..."
  python3 -m venv env
fi
source env/bin/activate

echo "Installing dependencies (requirements.txt)..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -U --upgrade-strategy eager -r requirements.txt

# Ensure .env exists
if [ ! -f .env ] && [ -f .env.example ]; then
  echo "Creating .env from .env.example ..."
  cp .env.example .env
  echo "(Edit .env to add API keys when ready)"
fi

# Create directories (idempotent)
mkdir -p input output_md output_txt output_images cache logs

echo
echo "Running smoke test..."
python main.py --test || true

echo
echo "=========================================="
echo "Setup complete!"
echo "- Add files to: input/"
echo "- Run the app: python main.py"
echo "- Hybrid mode:  python main.py --mode hybrid --no-interactive"
echo "=========================================="
