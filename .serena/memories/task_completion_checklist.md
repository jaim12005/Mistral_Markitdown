# Task Completion Checklist

## Before Committing Code Changes

### 1. Code Quality Checks
- **Run smoke test**: `python main.py --test` to verify basic functionality
- **Test affected modes**: Run the specific conversion modes that were modified
- **Check imports**: Verify all optional imports are handled gracefully
- **Review error handling**: Ensure new code has appropriate exception handling

### 2. Testing Commands
```bash
# Basic functionality test
python main.py --test

# Test specific modes (choose relevant ones)
python main.py --mode hybrid --no-interactive
python main.py --mode markitdown --no-interactive  
python main.py --mode ocr --no-interactive

# Verify environment
python --version
pip check
```

### 3. File and Directory Verification
```bash
# Check required directories exist
dir input output_md output_txt output_images cache logs

# Verify .env configuration
type .env

# Check logs for any issues
type logs\app_startup.log
```

### 4. Code Style Verification
- **Type hints**: Ensure all new functions have proper type annotations
- **Modern Python**: Use `list[Type]` syntax, not `List[Type]`
- **Path handling**: Use `pathlib.Path` consistently
- **Error messages**: Include helpful user-facing error messages with emojis
- **Docstrings**: Add docstrings for new public functions

### 5. Configuration Updates
- **Environment variables**: Update `.env.example` if new config options added
- **Dependencies**: Update `requirements.txt` if new packages added
- **Documentation**: Update README.md or CLAUDE.md if significant changes made

### 6. Git Workflow
```bash
# Check status
git status

# Review changes
git diff

# Stage files
git add .

# Commit with conventional commit format
git commit -m "feat: add new feature"
git commit -m "fix: resolve issue with table extraction"
git commit -m "docs: update configuration guide"
```

## Commit Message Conventions

Based on the git history, use conventional commit format:

- **feat**: New features
- **fix**: Bug fixes
- **docs**: Documentation changes
- **refactor**: Code refactoring
- **test**: Test additions/modifications
- **chore**: Build process or auxiliary tool changes

Examples from history:
- `feat: Enhance document converter with transcription and expanded OCR`
- `fix: Handle non-string data in financial table reshaping`
- `fix(local_converter): Prevent errors from duplicate columns in tables`

## Post-Commit Verification

### 1. Verify Changes Work
```bash
# Clean test environment
rmdir /s cache
rmdir /s logs

# Fresh installation test
run_converter.bat

# Test key functionality
python main.py --test
```

### 2. Documentation Updates
- Update version numbers if applicable
- Refresh CLAUDE.md with any new commands or procedures
- Update README.md if user-facing changes

## Windows-Specific Considerations

### Path Handling
- Use `pathlib.Path` for cross-platform compatibility
- Test with spaces in file names and paths
- Verify Poppler path configuration on Windows

### Environment Setup
- Test with `run_converter.bat` script
- Verify virtual environment creation and activation
- Check pip installation logs in `logs/pip_install.log`

### External Dependencies
- Verify Ghostscript installation: `gswin64c --version`
- Check Poppler: `pdftoppm --help`
- Test FFmpeg: `ffmpeg -version`

## Performance Considerations

### Memory and Processing
- Test with large files (>45MB threshold)
- Verify caching system works correctly
- Check concurrent processing doesn't overwhelm system

### API Rate Limits
- Test Mistral API integration with various file sizes
- Verify retry logic works for network failures
- Check timeout handling for large uploads

## Security Checks

### API Keys and Secrets
- Ensure `.env` file is in `.gitignore`
- Verify no API keys in code or logs
- Check that sensitive data isn't cached inappropriately

### File Handling
- Test with various file types and sizes
- Verify no directory traversal vulnerabilities
- Check proper cleanup of temporary files