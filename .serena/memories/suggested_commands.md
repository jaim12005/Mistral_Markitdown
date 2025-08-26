# Enhanced Document Converter - Essential Commands

## Quick Start Commands

### Windows (Recommended)
```bash
# Complete setup and launch (creates venv, installs deps, runs app)
run_converter.bat

# Manual setup
python -m venv env
env\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

### macOS/Linux
```bash
# Complete setup with smoke test
bash quick_start.sh

# Manual setup  
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Development Commands

### Running the Application
```bash
# Interactive menu (8 processing modes)
python main.py

# Command line modes
python main.py --mode hybrid            # Hybrid processing (recommended)
python main.py --mode markitdown        # Local-only conversion
python main.py --mode ocr               # Mistral OCR only
python main.py --mode enhanced          # Enhanced batch processing
python main.py --mode transcription     # Audio/video transcription
python main.py --mode batch             # Simple batch processing

# Non-interactive execution
python main.py --mode hybrid --no-interactive

# Test installation without processing
python main.py --test
```

### Windows System Commands
```bash
# Directory listing
dir                     # List files in current directory
dir /s                  # Recursive listing

# File operations
copy source dest        # Copy files
move source dest        # Move/rename files
del filename           # Delete files
type filename          # Display file contents

# Process management
tasklist               # List running processes
taskkill /PID <pid>    # Kill process by PID

# Search
findstr "pattern" *.py # Search for text in files
where python           # Find command location
```

### Git Commands (Windows)
```bash
git status             # Check repository status
git add .              # Stage all changes
git commit -m "message" # Commit changes
git log --oneline -10  # Show recent commits
git diff               # Show changes
git branch             # List branches
git checkout -b name   # Create new branch
```

### Testing and Debugging
```bash
# Verify installation
python main.py --test

# Check Python environment
python --version
pip list
pip check

# Clear cache and logs (safe to delete)
rmdir /s cache
rmdir /s logs

# View logs
type logs\app_startup.log
type logs\pip_install.log
type logs\installed_versions.txt
```

## External Tool Commands

### Ghostscript (for table extraction)
```bash
# Verify installation
gs --version          # Linux/macOS
gswin64c --version    # Windows 64-bit
gswin32c --version    # Windows 32-bit
```

### Poppler (for PDF-to-image)
```bash
# Verify installation
pdftoppm --help       # Should show help if installed

# Manual PDF to image conversion
pdftoppm -png input.pdf output_prefix
```

### FFmpeg (for transcription)
```bash
# Verify installation
ffmpeg -version

# Manual audio conversion
ffmpeg -i input.mp3 -ar 16000 output.wav
```