"""
Tests for utils.py module
"""

import os
import tempfile
from pathlib import Path
import pytest

# Add parent directory to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

import utils


class TestIntelligentCache:
    """Test the IntelligentCache class."""

    def test_cache_initialization(self, tmp_path):
        """Test cache initializes correctly."""
        cache = utils.IntelligentCache(cache_dir=tmp_path)
        assert cache.cache_dir.exists()
        assert cache.hits == 0
        assert cache.misses == 0

    def test_cache_set_and_get(self, tmp_path):
        """Test basic cache set and get operations."""
        cache = utils.IntelligentCache(cache_dir=tmp_path)

        # Create a temporary file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # Cache some data
        test_data = {"result": "test value"}
        cache.set(test_file, test_data, cache_type="test")

        # Retrieve cached data
        retrieved = cache.get(test_file, cache_type="test")
        assert retrieved == test_data
        assert cache.hits == 1
        assert cache.misses == 0

    def test_cache_miss(self, tmp_path):
        """Test cache miss behavior."""
        cache = utils.IntelligentCache(cache_dir=tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # Try to get non-existent cache
        result = cache.get(test_file, cache_type="test")
        assert result is None
        assert cache.misses == 1

    def test_cache_type_mismatch(self, tmp_path):
        """Test that different cache types are isolated."""
        cache = utils.IntelligentCache(cache_dir=tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # Cache with type "A"
        cache.set(test_file, {"data": "A"}, cache_type="type_a")

        # Try to get with type "B"
        result = cache.get(test_file, cache_type="type_b")
        assert result is None
        assert cache.misses == 1

    def test_cache_statistics(self, tmp_path):
        """Test cache statistics calculation."""
        cache = utils.IntelligentCache(cache_dir=tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # Perform operations
        cache.set(test_file, {"data": "value"}, cache_type="test")
        cache.get(test_file, cache_type="test")  # Hit
        cache.get(tmp_path / "nonexistent.txt", cache_type="test")  # Miss

        stats = cache.get_statistics()
        assert stats["total_entries"] == 1
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1
        assert stats["hit_rate"] == 50.0


class TestMarkdownFormatting:
    """Test markdown formatting functions."""

    def test_format_table_to_markdown_basic(self):
        """Test basic table formatting."""
        headers = ["Name", "Age", "City"]
        data = [["Alice", "30", "NYC"], ["Bob", "25", "LA"]]

        result = utils.format_table_to_markdown(data, headers=headers)

        assert "| Name | Age | City |" in result
        assert "| --- | --- | --- |" in result
        assert "| Alice | 30 | NYC |" in result
        assert "| Bob | 25 | LA |" in result

    def test_format_table_empty_data(self):
        """Test formatting with empty data."""
        result = utils.format_table_to_markdown([])
        assert result == ""

    def test_format_table_uneven_rows(self):
        """Test formatting with uneven row lengths."""
        headers = ["A", "B", "C"]
        data = [
            ["1", "2"],  # Missing third column
            ["3", "4", "5"],
        ]

        result = utils.format_table_to_markdown(data, headers=headers)
        assert "| 1 | 2 |  |" in result  # Padded


class TestTextCleaning:
    """Test text cleaning functions."""

    def test_clean_consecutive_duplicates_basic(self):
        """Test basic duplicate line removal."""
        text = "Line 1\nLine 1\nLine 1\nLine 2\nLine 2\nLine 3"
        result = utils.clean_consecutive_duplicates(text)
        expected = "Line 1\nLine 2\nLine 3"
        assert result == expected

    def test_clean_consecutive_duplicates_no_duplicates(self):
        """Test with no consecutive duplicates."""
        text = "Line 1\nLine 2\nLine 3"
        result = utils.clean_consecutive_duplicates(text)
        assert result == text

    def test_clean_consecutive_duplicates_empty(self):
        """Test with empty string."""
        result = utils.clean_consecutive_duplicates("")
        assert result == ""

    def test_markdown_to_text_removes_formatting(self):
        """Test markdown to text conversion."""
        markdown = """---
title: Test
---
# Heading

**Bold text** and *italic text*

[Link text](https://example.com)

```python
code block
```
"""
        result = utils.markdown_to_text(markdown)

        assert "---" not in result  # No frontmatter
        assert "# " not in result  # No heading markers
        assert "**" not in result  # No bold markers
        assert "*" not in result or "italic text" in result  # No italic markers
        assert "https://example.com" not in result  # No URLs
        assert "```" not in result  # No code block markers


class TestFileValidation:
    """Test file validation functions."""

    def test_validate_file_exists(self, tmp_path):
        """Test validation of existing file."""
        test_file = tmp_path / "test.pdf"
        test_file.write_text("content")

        is_valid, error = utils.validate_file(test_file)
        assert is_valid
        assert error is None

    def test_validate_file_not_exists(self, tmp_path):
        """Test validation of non-existent file."""
        test_file = tmp_path / "nonexistent.pdf"

        is_valid, error = utils.validate_file(test_file)
        assert not is_valid
        assert "does not exist" in error

    def test_validate_file_empty(self, tmp_path):
        """Test validation of empty file."""
        test_file = tmp_path / "empty.pdf"
        test_file.write_text("")

        is_valid, error = utils.validate_file(test_file)
        assert not is_valid
        assert "empty" in error.lower()

    def test_validate_file_unsupported_type(self, tmp_path):
        """Test validation of unsupported file type."""
        test_file = tmp_path / "test.xyz"
        test_file.write_text("content")

        is_valid, error = utils.validate_file(test_file)
        assert not is_valid
        assert "Unsupported" in error


class TestYAMLFrontmatter:
    """Test YAML frontmatter functions."""

    def test_generate_yaml_frontmatter_basic(self):
        """Test basic frontmatter generation."""
        result = utils.generate_yaml_frontmatter(
            title="Test Document", file_name="test.pdf", conversion_method="Test Method"
        )

        assert "---" in result
        assert 'title: "Test Document"' in result
        assert 'source_file: "test.pdf"' in result
        assert 'conversion_method: "Test Method"' in result

    def test_generate_yaml_frontmatter_additional_fields(self):
        """Test frontmatter with additional fields."""
        result = utils.generate_yaml_frontmatter(
            title="Test",
            file_name="test.pdf",
            conversion_method="Method",
            additional_fields={"page_count": 5, "has_tables": True},
        )

        assert "page_count: 5" in result
        assert "has_tables: True" in result

    def test_strip_yaml_frontmatter(self):
        """Test frontmatter removal."""
        content = """---
title: "Test"
date: 2025-01-01
---

# Content starts here

This is the actual content.
"""
        result = utils.strip_yaml_frontmatter(content)

        assert "---" not in result
        assert "title:" not in result
        assert "# Content starts here" in result
        assert "This is the actual content." in result


class TestMetadataTracker:
    """Test MetadataTracker class."""

    def test_metadata_initialization(self):
        """Test metadata tracker initialization."""
        tracker = utils.MetadataTracker()

        assert tracker.metadata["total_files"] == 0
        assert tracker.metadata["successful"] == 0
        assert tracker.metadata["failed"] == 0
        assert len(tracker.metadata["files_processed"]) == 0

    def test_add_file_success(self):
        """Test adding successful file processing."""
        tracker = utils.MetadataTracker()
        tracker.add_file("test.pdf", "success", 1.5)

        assert tracker.metadata["total_files"] == 1
        assert tracker.metadata["successful"] == 1
        assert tracker.metadata["failed"] == 0
        assert len(tracker.metadata["files_processed"]) == 1

    def test_add_file_failed(self):
        """Test adding failed file processing."""
        tracker = utils.MetadataTracker()
        tracker.add_file("test.pdf", "failed", 0.5, error="Test error")

        assert tracker.metadata["total_files"] == 1
        assert tracker.metadata["successful"] == 0
        assert tracker.metadata["failed"] == 1
        assert tracker.metadata["files_processed"][0]["error"] == "Test error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
