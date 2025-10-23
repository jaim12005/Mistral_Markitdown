"""
Pytest configuration and shared fixtures.
"""

import os
import tempfile
from pathlib import Path
import pytest


@pytest.fixture
def tmp_path():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_pdf_path(tmp_path):
    """Create a sample PDF file for testing."""
    pdf_path = tmp_path / "sample.pdf"
    # Create a minimal PDF file (just for testing file operations)
    pdf_path.write_bytes(b"%PDF-1.4\n%EOF")
    return pdf_path


@pytest.fixture
def sample_text_file(tmp_path):
    """Create a sample text file for testing."""
    text_path = tmp_path / "sample.txt"
    text_path.write_text("Sample text content\nLine 2\nLine 3")
    return text_path


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    test_env = {
        "MISTRAL_API_KEY": "test_api_key_12345",
        "CACHE_DURATION_HOURS": "24",
        "LOG_LEVEL": "INFO",
        "MAX_CONCURRENT_FILES": "5",
    }
    for key, value in test_env.items():
        monkeypatch.setenv(key, value)
    return test_env


@pytest.fixture
def sample_markdown():
    """Sample markdown content for testing."""
    return """---
title: "Test Document"
date: 2025-01-01
---

# Main Heading

This is a **bold** statement and this is *italic*.

## Table

| Name | Age | City |
|------|-----|------|
| Alice | 30 | NYC |
| Bob | 25 | LA |

## Code Block

```python
def hello():
    print("Hello, World!")
```

[Link to example](https://example.com)
"""


@pytest.fixture
def sample_ocr_result():
    """Sample OCR result for testing."""
    return {
        "file_name": "test.pdf",
        "pages": [
            {
                "page_number": 0,
                "text": "Sample page 1 text with multiple words and numbers 123 456.",
                "images": [],
            },
            {
                "page_number": 1,
                "text": "Sample page 2 text with more content and data 789 012.",
                "images": [],
            },
        ],
        "full_text": "Sample page 1 text with multiple words and numbers 123 456.\n\nSample page 2 text with more content and data 789 012.",
        "images": [],
        "metadata": {},
    }
