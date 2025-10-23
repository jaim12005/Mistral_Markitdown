#!/usr/bin/env bash

# Enhanced Document Converter v2.1 - macOS/Linux Quick Start Script
# This script sets up the virtual environment, installs dependencies,
# and launches the document converter.

# Enforce bash
if [ -z "$BASH_VERSION" ]; then
    echo "ERROR: This script requires bash"
    echo "Please run with: bash quick_start.sh"
    exit 1
fi

set -e

echo "============================================================"
echo "  Enhanced Document Converter v2.1 - Setup and Launch"
echo "============================================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.10+ from https://www.python.org/"
    exit 1
fi

echo "[1/5] Checking Python version..."
python3 --version

# Create logs directory if it doesn't exist
mkdir -p logs

# Check/create virtual environment
if [ ! -d "env" ]; then
    echo ""
    echo "[2/5] Creating virtual environment..."
    python3 -m venv env
    echo "Virtual environment created successfully."
else
    echo ""
    echo "[2/5] Virtual environment already exists."
fi

# Activate virtual environment
source env/bin/activate

# Upgrade pip, setuptools, and wheel
echo ""
echo "[3/5] Upgrading pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel > logs/pip_install.log 2>&1

# Install/upgrade dependencies
echo ""
echo "[4/5] Installing dependencies (this may take a few minutes)..."
echo "This process is logged to logs/pip_install.log"

# Install requirements
pip install -r requirements.txt >> logs/pip_install.log 2>&1

echo ""
echo "[5/5] Verifying installation..."
pip check > logs/pip_check.log 2>&1 || echo "WARNING: Some package conflicts detected. See logs/pip_check.log"

# Save installed versions
pip list > logs/installed_versions.txt 2>&1
echo "Installed package versions saved to logs/installed_versions.txt"

echo ""
echo "============================================================"
echo "  Setup complete!"
echo "============================================================"
echo ""

# Check for .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "WARNING: .env file not found"
        echo "Please copy .env.example to .env and configure your API keys"
        echo ""
        read -p "Would you like to create .env from .env.example now? (y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cp .env.example .env
            echo ".env file created. Please edit it with your API keys."
            echo ""
            echo "Opening .env file in default editor..."
            ${EDITOR:-nano} .env
        fi
    fi
fi

# Run smoke test
echo ""
echo "Running smoke test..."
python main.py --test

echo ""
echo "============================================================"
echo "  Smoke test complete!"
echo ""
echo "  To run the converter:"
echo "    source env/bin/activate"
echo "    python main.py"
echo ""
echo "  Or simply run: ./quick_start.sh"
echo "============================================================"
echo ""

# Keep environment activated for user
exec bash --rcfile <(echo "source env/bin/activate; PS1='(converter-env) \u@\h:\w\$ '")
