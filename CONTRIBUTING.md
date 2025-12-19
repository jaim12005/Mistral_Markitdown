# Contributing to Enhanced Document Converter

Thank you for your interest in contributing to Enhanced Document Converter v2.1.1! This document provides guidelines and setup instructions for developers.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- Virtual environment tool (venv, virtualenv, or conda)

### Quick Start

```bash
# Clone the repository (replace with your fork URL)
git clone https://github.com/your-username/Mistral_Markitdown.git
cd Mistral_Markitdown

# Create and activate virtual environment
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install dependencies
make install-dev
# Or manually:
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Optional: Install extended features (if testing audio/YouTube features)
pip install -r requirements-optional.txt

# Verify setup
make check
```

**Note on Optional Dependencies:**
- `requirements-optional.txt` contains MarkItDown plugin features (audio, YouTube, Azure)
- Only install if you're working on features that require these capabilities
- See [DEPENDENCIES.md](DEPENDENCIES.md) for details

## Development Workflow

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_utils.py -v

# Run tests with coverage
pytest tests/ --cov=. --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Code Quality

```bash
# Run all linters
make lint

# Format code
make format

# Type checking
make type-check

# Run all checks before committing
make check
```

### Making Changes

1. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clean, documented code
   - Follow existing code style
   - Add tests for new features

3. **Test your changes**
   ```bash
   make check
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

5. **Push and create pull request**
   ```bash
   git push origin feature/your-feature-name
   ```

## Code Style Guidelines

### Python Style

- **Line Length**: 120 characters maximum
- **Formatting**: Use `black` and `isort`
- **Docstrings**: Google-style docstrings for all public functions
- **Type Hints**: Use type hints for function signatures
- **Imports**: Group imports (stdlib, third-party, local)

### Example

```python
from pathlib import Path
from typing import Optional, Tuple

import config
import utils


def process_document(file_path: Path, use_cache: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Process a document file.

    Args:
        file_path: Path to the document file
        use_cache: Whether to use cached results

    Returns:
        Tuple of (success, error_message)
    """
    logger.info(f"Processing {file_path.name}")
    # Implementation...
```

## Testing Guidelines

### Writing Tests

- Place tests in `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use fixtures for common setup
- Mock external API calls

**Testing Optional Features:**
- Audio/YouTube features require `requirements-optional.txt` to be installed
- Use `pytest.importorskip()` to skip tests when optional packages are missing
- Example: `pytest.importorskip("pydub", reason="Audio features not installed")`

### Test Structure

```python
def test_feature_name():
    """Test description."""
    # Arrange
    input_data = create_test_data()
    
    # Act
    result = function_under_test(input_data)
    
    # Assert
    assert result == expected_output
```

### Fixtures

Common fixtures are available in `tests/conftest.py`:
- `tmp_path`: Temporary directory
- `sample_pdf_path`: Sample PDF file
- `sample_markdown`: Sample markdown content
- `mock_env_vars`: Mocked environment variables

## Project Structure

```
Mistral_Markitdown/
├── main.py                  # Main application entry point (8 modes)
├── config.py                # Configuration management (50+ options)
├── local_converter.py       # MarkItDown integration & table extraction
├── mistral_converter.py     # Mistral AI OCR integration
├── utils.py                 # Utility functions (caching, logging, formatting)
├── schemas.py               # JSON schemas for structured extraction
│
├── requirements.txt         # Core dependencies (required)
├── requirements-optional.txt # Optional features (audio, YouTube, Azure)
├── requirements-dev.txt     # Development dependencies (testing, linting)
│
├── README.md                # Complete user guide
├── QUICKSTART.md            # 5-minute getting started guide
├── CONFIGURATION.md         # Complete configuration reference
├── DEPENDENCIES.md          # Dependency reference and troubleshooting
├── KNOWN_ISSUES.md          # Known issues and troubleshooting guide
├── CONTRIBUTING.md          # Development guidelines (this file)
├── LICENSE                  # MIT License
│
├── run_converter.bat        # Windows quick start script
├── quick_start.sh           # Linux/macOS quick start script
├── Makefile                 # Development commands
├── pyproject.toml           # Tool configuration (black, isort, pytest)
├── mypy.ini                 # Type checking configuration
│
├── tests/                   # Test suite
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures
│   ├── test_config.py       # Configuration tests
│   └── test_utils.py        # Utility function tests
│
├── .github/workflows/       # CI/CD automation
│   ├── test.yml             # Multi-platform testing
│   └── lint.yml             # Code quality checks
│
├── input/                   # Place files to convert here
├── output_md/               # Markdown output
├── output_txt/              # Plain text output
├── output_images/           # Extracted images and PDF renders
├── cache/                   # OCR result cache
└── logs/                    # Processing logs
    └── metadata/            # Batch processing metadata
```

## Common Tasks

### Adding a New Feature

1. **Create tests first** (TDD approach)
   ```bash
   # Create test file
   touch tests/test_new_feature.py
   
   # Write failing tests
   # Then implement feature to make tests pass
   ```

2. **Implement the feature**
   - Add to appropriate module
   - Follow existing patterns
   - Use type hints
   - Add docstrings

3. **Update documentation**
   - Update README.md if user-facing
   - Update docstrings
   - Add comments for complex logic

### Debugging

```bash
# Run with debug logging
LOG_LEVEL=DEBUG python main.py

# Use ipdb for interactive debugging
import ipdb; ipdb.set_trace()

# Run specific test with output
pytest tests/test_utils.py::TestClassName::test_method_name -v -s
```

### Updating Dependencies

```bash
# Update requirements
pip install --upgrade package-name
pip freeze > requirements.txt

# Test with new versions
make check
```

## Continuous Integration

### GitHub Actions

Two workflows run automatically:

1. **Lint** (`lint.yml`)
   - Runs on every push and PR
   - Checks code formatting
   - Fast feedback (~2 minutes)

2. **Test** (`test.yml`)
   - Runs on every push and PR
   - Tests on multiple OS and Python versions
   - Comprehensive checks (~10 minutes)

### Pre-commit Hooks

Install pre-commit hooks for automatic checks:

```bash
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

## Release Process

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG.md**
3. **Run full test suite**
   ```bash
   make check
   ```
4. **Create git tag**
   ```bash
   git tag -a v2.1.0 -m "Release v2.1.0"
   git push origin v2.1.0
   ```

## Getting Help

- **Issues**: Open an issue on GitHub
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check README.md and docstrings

## Code Review Guidelines

### For Contributors

- Keep PRs focused and reasonably sized
- Write clear commit messages
- Respond to review comments promptly
- Ensure CI passes before requesting review

### For Reviewers

- Be respectful and constructive
- Focus on code quality and maintainability
- Check for test coverage
- Verify documentation is updated

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to Enhanced Document Converter! 🎉

**Version:** 2.1.1

**Related Documentation:**
- **[README.md](README.md)** - Complete feature documentation
- **[CONFIGURATION.md](CONFIGURATION.md)** - Configuration reference
- **[DEPENDENCIES.md](DEPENDENCIES.md)** - Dependency guide
- **[KNOWN_ISSUES.md](KNOWN_ISSUES.md)** - Known issues
