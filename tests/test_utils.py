"""
Tests for utils.py module
"""

import concurrent.futures
import json
import logging
import os
import re
import tempfile
import unittest.mock
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import utils
import config


class TestSetupLogging:
    """Test logging configuration."""

    def test_returns_logger(self):
        logger = utils.setup_logging()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "document_converter"

    def test_log_file_created(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "SAVE_PROCESSING_LOGS", True)
        log_file = str(tmp_path / "test.log")
        logger = utils.setup_logging(log_file=log_file)
        logger.info("test message")
        assert Path(log_file).exists()

    def test_no_file_handler_when_disabled(self, monkeypatch):
        monkeypatch.setattr(config, "SAVE_PROCESSING_LOGS", False)
        logger = utils.setup_logging(log_file="/tmp/nope.log")
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 0

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

    def test_hash_memo_is_bounded(self, tmp_path):
        """Ensure hash memoization does not grow unbounded."""
        cache = utils.IntelligentCache(cache_dir=tmp_path)

        for i in range(1200):
            f = tmp_path / f"f-{i}.txt"
            f.write_text(f"content-{i}")
            cache._get_file_hash(f)

        assert len(cache._hash_memo) <= cache._hash_memo_max_entries

    def test_cache_set_atomic_under_concurrency(self, tmp_path):
        """Concurrent writes to same cache key should not produce corrupt JSON."""
        cache = utils.IntelligentCache(cache_dir=tmp_path)
        test_file = tmp_path / "shared.txt"
        test_file.write_text("shared-content")

        def _writer(i: int):
            cache.set(test_file, {"writer": i, "payload": "x" * 1000}, cache_type="test")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(_writer, range(50)))

        file_hash = cache._get_file_hash(test_file)
        cache_path = cache._get_cache_path(file_hash, "test")
        with open(cache_path, "r", encoding="utf-8") as f:
            parsed = json.load(f)
        assert parsed.get("type") == "test"
        assert "data" in parsed


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

    def test_generate_yaml_frontmatter_escapes_quotes(self):
        """String values should be safely escaped to valid YAML/JSON string form."""
        result = utils.generate_yaml_frontmatter(
            title='Report "2026"',
            file_name="test.pdf",
            conversion_method="Method",
        )

        assert 'title: "Report \\"2026\\""' in result

    def test_strip_yaml_frontmatter(self):
        """Test frontmatter removal."""
        content = """---
title: "Test"
date: 2025-01-01
---
This is the actual content.
"""
        result = utils.strip_yaml_frontmatter(content)

        assert result == "This is the actual content."


class TestOutputNaming:
    """Test output file naming and collision handling."""

    def test_safe_output_stem_disambiguates_same_stem(self, tmp_path):
        """When two files share the same stem, each gets a _ext suffix."""
        # Create two files with the same stem but different extensions
        (tmp_path / "report.pdf").touch()
        (tmp_path / "report.docx").touch()

        with unittest.mock.patch.object(config, "INPUT_DIR", tmp_path):
            stem_pdf = utils.safe_output_stem(tmp_path / "report.pdf")
            stem_docx = utils.safe_output_stem(tmp_path / "report.docx")

        assert stem_pdf != stem_docx
        assert "pdf" in stem_pdf
        assert "docx" in stem_docx

    def test_safe_output_stem_unique_stem(self, tmp_path):
        """When only one file has a given stem, no _ext suffix is needed."""
        (tmp_path / "unique.pdf").touch()

        with unittest.mock.patch.object(config, "INPUT_DIR", tmp_path):
            stem = utils.safe_output_stem(tmp_path / "unique.pdf")

        assert stem == "unique"


class TestPrintProgress:
    """Test the progress bar helper."""

    def test_no_output_when_verbose_off(self, monkeypatch, capsys):
        monkeypatch.setattr(config, "VERBOSE_PROGRESS", False)
        utils.print_progress(1, 10)
        assert capsys.readouterr().out == ""

    def test_output_when_verbose_on(self, monkeypatch, capsys):
        monkeypatch.setattr(config, "VERBOSE_PROGRESS", True)
        utils.print_progress(5, 10)
        captured = capsys.readouterr().out
        assert "50.0%" in captured

    def test_handles_zero_total(self, monkeypatch, capsys):
        monkeypatch.setattr(config, "VERBOSE_PROGRESS", True)
        utils.print_progress(0, 0)
        captured = capsys.readouterr().out
        assert "0.0%" in captured


class TestClearOldEntries:
    """Test cache expiry cleanup."""

    def test_removes_expired_entries(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "CACHE_DURATION_HOURS", 1)
        cache = utils.IntelligentCache(cache_dir=tmp_path)
        # Write a cache file with an old timestamp
        cache_file = tmp_path / "old_entry.json"
        old_time = (datetime.now() - timedelta(hours=5)).isoformat()
        cache_file.write_text(json.dumps({"timestamp": old_time, "type": "ocr", "data": {}}))
        removed = cache.clear_old_entries()
        assert removed == 1
        assert not cache_file.exists()

    def test_keeps_fresh_entries(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "CACHE_DURATION_HOURS", 24)
        cache = utils.IntelligentCache(cache_dir=tmp_path)
        cache_file = tmp_path / "fresh_entry.json"
        cache_file.write_text(json.dumps({"timestamp": datetime.now().isoformat(), "type": "ocr", "data": {}}))
        removed = cache.clear_old_entries()
        assert removed == 0
        assert cache_file.exists()


class TestDetectMonthHeaderRow:
    """Test month header detection in financial tables."""

    def test_detects_month_headers(self):
        table = [
            ["Account", "Description"],
            ["", "January", "February", "March", "April"],
            ["10201", "100", "200", "300", "400"],
        ]
        assert utils.detect_month_header_row(table) == 1

    def test_no_months_returns_none(self):
        table = [["Name", "Value"], ["A", "1"]]
        assert utils.detect_month_header_row(table) is None

    def test_empty_table_returns_none(self):
        assert utils.detect_month_header_row([]) is None


class TestCleanTableCell:
    """Test cell cleaning."""

    def test_removes_newlines(self):
        assert utils.clean_table_cell("Hello\nWorld") == "Hello World"

    def test_collapses_whitespace(self):
        assert utils.clean_table_cell("  too   many   spaces  ") == "too many spaces"

    def test_empty_string(self):
        assert utils.clean_table_cell("") == ""

    def test_none_returns_empty(self):
        assert utils.clean_table_cell(None) == ""


class TestIsPageArtifactRow:
    """Test page artifact row detection."""

    def test_page_number_is_artifact(self):
        assert utils.is_page_artifact_row(["Page 1"]) is True

    def test_page_number_multi_digit(self):
        assert utils.is_page_artifact_row(["Page 42"]) is True

    def test_date_is_artifact(self):
        assert utils.is_page_artifact_row(["December 31, 2010"]) is True

    def test_empty_row_is_artifact(self):
        assert utils.is_page_artifact_row(["", ""]) is True

    def test_data_row_is_not_artifact(self):
        assert utils.is_page_artifact_row(["10201", "Cash Operating", "1234.56"]) is False

    def test_none_input(self):
        assert utils.is_page_artifact_row([]) is False


class TestCleanTable:
    """Test full table cleaning."""

    def test_removes_artifacts_and_cleans(self):
        table = [
            ["Name\nValue", "Amount"],
            ["Page 1"],
            ["Item A", "100"],
        ]
        result = utils.clean_table(table)
        assert len(result) == 2
        assert result[0] == ["Name Value", "Amount"]
        assert result[1] == ["Item A", "100"]

    def test_empty_table(self):
        assert utils.clean_table([]) == []


class TestNormalizeTableHeaders:
    """Test table header normalization."""

    def test_with_month_headers(self):
        table = [
            ["Account", "Description"],
            ["", "January", "February", "March", "April"],
            ["10201", "100", "200", "300", "400"],
        ]
        headers, data = utils.normalize_table_headers(table)
        assert "January" in headers

    def test_without_month_headers(self):
        table = [["Name", "Age"], ["Alice", "30"]]
        headers, data = utils.normalize_table_headers(table)
        assert headers == ["Name", "Age"]
        assert data == [["Alice", "30"]]

    def test_empty_table(self):
        headers, data = utils.normalize_table_headers([])
        assert headers == []
        assert data == []


class TestSaveTextOutput:
    """Test text output saving."""

    def test_saves_text_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "GENERATE_TXT_OUTPUT", True)
        monkeypatch.setattr(config, "OUTPUT_TXT_DIR", tmp_path)
        md_path = tmp_path / "test.md"
        result = utils.save_text_output(md_path, "# Hello\n\n**Bold** text")
        assert result is not None
        assert result.exists()
        content = result.read_text()
        assert "Hello" in content
        assert "**" not in content

    def test_disabled_returns_none(self, monkeypatch):
        monkeypatch.setattr(config, "GENERATE_TXT_OUTPUT", False)
        result = utils.save_text_output(Path("test.md"), "content")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
