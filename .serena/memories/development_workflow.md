# Development Workflow and Best Practices

## Development Environment Setup

### Windows Development (Recommended)
1. **Quick Setup**: Run `run_converter.bat` for automated environment setup
2. **Manual Setup**: Create venv, install dependencies, configure .env
3. **IDE Setup**: Configure IDE to use `env\Scripts\python.exe` as interpreter
4. **External Tools**: Install Ghostscript, Poppler, FFmpeg for full functionality

### Environment Configuration
```bash
# Copy and configure environment
cp .env.example .env
# Edit .env to add MISTRAL_API_KEY and other settings

# Verify setup
python main.py --test
```

## Development Workflow

### Feature Development Process
1. **Branch Creation**: Create feature branch from main
2. **Environment Setup**: Ensure clean environment with `run_converter.bat`
3. **Code Changes**: Implement changes following style conventions
4. **Testing**: Run comprehensive tests on affected functionality
5. **Documentation**: Update relevant documentation and examples
6. **Commit**: Use conventional commit messages
7. **Pull Request**: Create PR with detailed description

### Testing Strategy

#### Unit Testing
```bash
# Basic functionality test
python main.py --test

# Mode-specific testing
python main.py --mode hybrid --no-interactive
python main.py --mode markitdown --no-interactive
python main.py --mode ocr --no-interactive
python main.py --mode transcription --no-interactive
```

#### Integration Testing
```bash
# Clean environment test
rmdir /s cache logs
run_converter.bat
python main.py --test

# End-to-end testing with sample files
# Place test files in input/ directory
python main.py --mode hybrid
```

#### Performance Testing
- Test with various file sizes (small, medium, large >45MB)
- Verify caching system reduces processing time on reruns
- Monitor memory usage during batch processing
- Test concurrent processing limits

### Debugging Workflow

#### Log Analysis
```bash
# Application startup logs
type logs\app_startup.log

# Installation logs
type logs\pip_install.log

# OCR response debugging (if SAVE_MISTRAL_JSON=true)
dir logs\*.json

# Session metadata
dir logs\metadata\
```

#### Common Issues and Solutions

**Import Errors**:
- Check virtual environment activation
- Verify requirements.txt installation
- Use `pip check` to validate dependencies

**OCR Processing Issues**:
- Verify MISTRAL_API_KEY in .env
- Check network connectivity
- Enable SAVE_MISTRAL_JSON=true for detailed responses
- Clear cache/ directory to force reprocessing

**Table Extraction Problems**:
- Verify Ghostscript installation: `gswin64c --version`
- Test with different camelot modes (lattice vs stream)
- Check PDF structure with pdfplumber

**PDF to Image Conversion**:
- Verify Poppler installation and POPPLER_PATH setting
- Test with `pdftoppm --help`
- Check file permissions and disk space

### Code Review Guidelines

#### Review Checklist
- [ ] **Type hints**: All new functions have proper annotations
- [ ] **Error handling**: Appropriate exception handling with user-friendly messages
- [ ] **Documentation**: Docstrings for public functions
- [ ] **Testing**: New functionality tested with --test and relevant modes
- [ ] **Performance**: Large file handling considered
- [ ] **Security**: No API keys or sensitive data in code

#### Code Quality Standards
- **Modularity**: Functions have single responsibility
- **Readability**: Clear variable names and logical structure  
- **Robustness**: Graceful handling of edge cases
- **Performance**: Efficient processing with appropriate caching
- **User Experience**: Clear console output with helpful error messages

## Release Process

### Version Management
- Version information in README.md and module docstrings
- Follow semantic versioning (MAJOR.MINOR.PATCH)
- Tag releases in Git with version numbers

### Pre-Release Checklist
```bash
# Complete environment test
run_converter.bat
python main.py --test

# Multi-mode functionality test
python main.py --mode hybrid --no-interactive
python main.py --mode enhanced --no-interactive

# Documentation updates
# - Update README.md with new features
# - Refresh CLAUDE.md with new commands
# - Update .env.example with new configuration options

# External dependency verification
gs --version || gswin64c --version
pdftoppm --help
ffmpeg -version
```

### Deployment Verification
1. **Clean Installation**: Test setup scripts on clean systems
2. **Cross-Platform**: Verify Windows and Unix compatibility
3. **Dependency Management**: Ensure all external tools documented
4. **Performance**: Benchmark processing times on representative files
5. **Documentation**: Verify all setup instructions work correctly

## Troubleshooting and Maintenance

### Regular Maintenance Tasks
- **Cache Cleanup**: Periodically clear cache/ directory for testing
- **Log Rotation**: Archive or clear old log files  
- **Dependency Updates**: Regular updates with `pip install -U`
- **Performance Monitoring**: Review session metadata for optimization opportunities

### Common Development Pitfalls
1. **API Key Management**: Never commit .env files or hardcode keys
2. **Path Handling**: Always use pathlib.Path for cross-platform compatibility
3. **Exception Handling**: Catch specific exceptions, not broad Exception
4. **Resource Cleanup**: Proper file handle and network connection management
5. **Testing Coverage**: Test with various file types and sizes

### Performance Optimization Guidelines
- **Caching**: Utilize intelligent caching for expensive OCR operations
- **Concurrency**: Use ConcurrentProcessor for batch operations
- **Memory Management**: Monitor memory usage for large file processing
- **API Efficiency**: Batch operations where possible, respect rate limits
- **Error Recovery**: Implement exponential backoff for network failures