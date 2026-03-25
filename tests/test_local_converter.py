"""
Tests for local_converter.py module.

Tests cover:
- _fix_merged_currency_cells (dollar pairs, bare numbers, text preservation)
- _fix_split_headers (fragmented header rejoining)
- coalesce_tables (merging tables with identical headers)
- _deduplicate_tables (content-based deduplication)
- analyze_file_content (file type analysis)
- get_markitdown_instance / reset (singleton lifecycle)
- convert_with_markitdown (MarkItDown integration, mocked)
- convert_stream_with_markitdown (stream-based conversion, mocked)
- extract_tables_pdfplumber / extract_tables_camelot (mocked)
- extract_all_tables (integration, mocked)
- save_tables_to_files (file output, mocked)
- convert_pdf_to_images (pdf2image integration, mocked)
"""

from unittest.mock import MagicMock, patch

import pytest

import config

config.ensure_directories()

import local_converter


# ============================================================================
# _fix_merged_currency_cells Tests
# ============================================================================


class TestFixMergedCurrencyCells:
    """Test splitting of merged currency/number cells."""

    def test_splits_dollar_sign_pairs(self):
        table = [["Item", "$ 1,234.56 $ 5,678.90"]]
        result = local_converter._fix_merged_currency_cells(table)
        assert len(result[0]) == 3
        assert "$" in result[0][1]
        assert "$" in result[0][2]

    def test_splits_bare_number_pairs(self):
        table = [["153,990.37 (235,497.83)"]]
        result = local_converter._fix_merged_currency_cells(table)
        assert len(result[0]) == 2
        assert "153,990.37" in result[0][0]
        assert "(235,497.83)" in result[0][1]

    def test_preserves_text_cells(self):
        """Cells containing letters should never be split."""
        table = [["10201 Cash - Operating 1"]]
        result = local_converter._fix_merged_currency_cells(table)
        assert len(result[0]) == 1
        assert result[0][0] == "10201 Cash - Operating 1"

    def test_preserves_single_number_cell(self):
        table = [["1,234.56"]]
        result = local_converter._fix_merged_currency_cells(table)
        assert len(result[0]) == 1
        assert result[0][0] == "1,234.56"

    def test_handles_empty_cells(self):
        table = [["", None, "value"]]
        result = local_converter._fix_merged_currency_cells(table)
        assert result[0][0] == ""
        assert result[0][1] is None
        assert result[0][2] == "value"

    def test_handles_zero_shorthands(self):
        table = [[".00 .00"]]
        result = local_converter._fix_merged_currency_cells(table)
        assert len(result[0]) == 2

    def test_splits_parenthetical_negatives(self):
        table = [["(18,954.54) (31,090.86)"]]
        result = local_converter._fix_merged_currency_cells(table)
        assert len(result[0]) == 2


# ============================================================================
# _fix_split_headers Tests
# ============================================================================


class TestFixSplitHeaders:
    """Test rejoining of split header text."""

    def test_rejoins_fragmented_word(self):
        """'Be' + 'ginning' -> '' + 'Beginning'"""
        table = [["Be", "ginning", "January"]]
        result = local_converter._fix_split_headers(table)
        assert "Beginning" in result[0][1] or "Beginning" in " ".join(result[0])

    def test_rejoins_trailing_fragment(self):
        """'Acct Account Title B' + 'alance' -> 'Acct Account Title' + 'Balance'"""
        table = [["Acct Account Title B", "alance"]]
        result = local_converter._fix_split_headers(table)
        assert "Balance" in result[0][1] or "Balance" in " ".join(result[0])

    def test_leaves_proper_headers_alone(self):
        table = [["Name", "Age", "City"]]
        result = local_converter._fix_split_headers(table)
        assert result[0] == ["Name", "Age", "City"]

    def test_does_not_merge_legitimate_lowercase_columns(self):
        """Legitimate lowercase column names (>= 3 chars) should not be merged."""
        table = [["Account ", "units", "Total"]]
        result = local_converter._fix_split_headers(table)
        # "units" should remain its own column since current cell ends with space
        assert "units" in result[0]

    def test_does_not_merge_long_trailing_fragment(self):
        """Trailing fragment > 2 chars in current cell should not trigger merge."""
        table = [["Some Header", "value", "Other"]]
        result = local_converter._fix_split_headers(table)
        assert result[0][1] == "value"

    def test_only_touches_first_rows(self):
        """Data rows below max_header_rows should not be modified."""
        table = [
            ["Header1", "Header2"],
            ["data1", "data2"],
            ["data3", "data4"],
            ["Da", "ta5"],  # row 3, beyond default max_header_rows=3
        ]
        result = local_converter._fix_split_headers(table, max_header_rows=2)
        assert result[3] == ["Da", "ta5"]

    def test_skips_uppercase_next_cell(self):
        """Next cell starting with uppercase is a real column, not a fragment."""
        table = [["Account", "Balance"]]
        result = local_converter._fix_split_headers(table)
        assert result[0] == ["Account", "Balance"]


# ============================================================================
# coalesce_tables Tests
# ============================================================================


class TestCoalesceTables:
    """Test merging tables with identical headers across pages."""

    def test_merges_matching_headers(self):
        t1 = [["Name", "Value"], ["A", "1"], ["B", "2"]]
        t2 = [["Name", "Value"], ["C", "3"], ["D", "4"]]
        result = local_converter.coalesce_tables([t1, t2])
        assert len(result) == 1
        assert len(result[0]) == 5  # header + 4 data rows

    def test_keeps_different_headers_separate(self):
        t1 = [["Name", "Value"], ["A", "1"]]
        t2 = [["ID", "Count"], ["X", "9"]]
        result = local_converter.coalesce_tables([t1, t2])
        assert len(result) == 2

    def test_handles_empty_list(self):
        result = local_converter.coalesce_tables([])
        assert result == []

    def test_handles_single_table(self):
        t1 = [["H1", "H2"], ["a", "b"]]
        result = local_converter.coalesce_tables([t1])
        assert len(result) == 1
        assert result[0] == t1

    def test_three_way_merge(self):
        header = ["Col1", "Col2"]
        t1 = [header, ["a", "1"]]
        t2 = [header, ["b", "2"]]
        t3 = [header, ["c", "3"]]
        result = local_converter.coalesce_tables([t1, t2, t3])
        assert len(result) == 1
        assert len(result[0]) == 4  # header + 3 data rows


# ============================================================================
# _deduplicate_tables Tests
# ============================================================================


class TestDeduplicateTables:
    """Test content-based table deduplication."""

    def test_removes_identical_tables(self):
        t1 = [["A", "B"], ["1", "2"]]
        t2 = [["A", "B"], ["1", "2"]]
        result = local_converter._deduplicate_tables([t1, t2])
        assert len(result) == 1

    def test_keeps_different_tables(self):
        t1 = [["A", "B"], ["1", "2"]]
        t2 = [["A", "B"], ["3", "4"]]
        result = local_converter._deduplicate_tables([t1, t2])
        assert len(result) == 2

    def test_skips_empty_tables(self):
        result = local_converter._deduplicate_tables([[], [["A"]], []])
        assert len(result) == 1

    def test_handles_empty_input(self):
        result = local_converter._deduplicate_tables([])
        assert result == []


# ============================================================================
# analyze_file_content Tests
# ============================================================================


class TestAnalyzeFileContent:
    """Test file content analysis."""

    def test_image_file_analysis(self, tmp_path):
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        result = local_converter.analyze_file_content(img_file)
        assert result["file_type"] == "png"
        assert result["has_images"] is True

    def test_non_pdf_no_pages(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("hello world")
        result = local_converter.analyze_file_content(txt_file)
        assert result["page_count"] == 0
        assert result["file_type"] == "txt"

    def test_large_file_is_complex(self, tmp_path):
        large_file = tmp_path / "big.docx"
        large_file.write_bytes(b"\x00" * (11 * 1024 * 1024))
        result = local_converter.analyze_file_content(large_file)
        assert result["is_complex"] is True

    def test_file_size_calculated(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text("a,b,c\n1,2,3\n")
        result = local_converter.analyze_file_content(f)
        assert result["file_size_mb"] > 0


# ============================================================================
# MarkItDown Singleton Lifecycle Tests
# ============================================================================


class TestMarkItDownSingleton:
    """Test get/reset of MarkItDown instance."""

    def test_reset_allows_reinit(self):
        local_converter.reset_markitdown_instance()
        # After reset, the sentinel is restored
        assert local_converter._markitdown_instance is local_converter._MARKITDOWN_UNSET

    def test_get_instance_returns_value(self):
        local_converter.reset_markitdown_instance()
        instance = local_converter.get_markitdown_instance()
        # It should return either a MarkItDown instance or None (if not installed)
        # but not the sentinel
        assert instance is not local_converter._MARKITDOWN_UNSET

    def test_cached_on_second_call(self):
        local_converter.reset_markitdown_instance()
        first = local_converter.get_markitdown_instance()
        second = local_converter.get_markitdown_instance()
        assert first is second


# ============================================================================
# convert_with_markitdown Tests (mocked)
# ============================================================================


class TestConvertWithMarkItDown:
    """Test convert_with_markitdown with mocked MarkItDown."""

    def test_file_too_large(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MARKITDOWN_MAX_FILE_SIZE_MB", 1)
        big_file = tmp_path / "big.pdf"
        big_file.write_bytes(b"\x00" * (2 * 1024 * 1024))
        success, content, error = local_converter.convert_with_markitdown(big_file)
        assert success is False
        assert "too large" in error

    def test_markitdown_not_available(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MARKITDOWN_MAX_FILE_SIZE_MB", 100)
        small_file = tmp_path / "test.txt"
        small_file.write_text("content")
        # Force get_markitdown_instance to return None
        with patch.object(local_converter, "get_markitdown_instance", return_value=None):
            success, content, error = local_converter.convert_with_markitdown(small_file)
        assert success is False
        assert "not available" in error

    def test_successful_conversion(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MARKITDOWN_MAX_FILE_SIZE_MB", 100)
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)
        monkeypatch.setattr(config, "INCLUDE_METADATA", False)
        monkeypatch.setattr(config, "GENERATE_TXT_OUTPUT", False)
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)

        test_file = tmp_path / "doc.txt"
        test_file.write_text("hello world")

        mock_result = MagicMock()
        mock_result.markdown = "# Converted\n\nhello world"
        mock_result.title = "doc"

        mock_md = MagicMock()
        mock_md.convert.return_value = mock_result

        with patch.object(local_converter, "get_markitdown_instance", return_value=mock_md):
            success, content, error = local_converter.convert_with_markitdown(test_file)

        assert success is True
        assert "hello world" in content
        assert error is None

    def test_conversion_exception(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MARKITDOWN_MAX_FILE_SIZE_MB", 100)
        test_file = tmp_path / "doc.txt"
        test_file.write_text("hello")

        mock_md = MagicMock()
        mock_md.convert.side_effect = Exception("conversion error")

        with patch.object(local_converter, "get_markitdown_instance", return_value=mock_md):
            success, content, error = local_converter.convert_with_markitdown(test_file)

        assert success is False
        assert "conversion error" in error


# ============================================================================
# convert_stream_with_markitdown Tests
# ============================================================================


class TestConvertStreamWithMarkItDown:
    """Test stream-based conversion."""

    def test_markitdown_not_available(self):
        import io

        stream = io.BytesIO(b"data")
        with patch.object(local_converter, "get_markitdown_instance", return_value=None):
            success, content, error = local_converter.convert_stream_with_markitdown(stream)
        assert success is False
        assert "not available" in error

    def test_convert_stream_not_supported(self):
        import io

        stream = io.BytesIO(b"data")
        mock_md = MagicMock(spec=[])  # no convert_stream attribute
        with patch.object(local_converter, "get_markitdown_instance", return_value=mock_md):
            success, content, error = local_converter.convert_stream_with_markitdown(stream)
        assert success is False
        assert "not available" in error

    def test_successful_stream_conversion(self):
        import io

        stream = io.BytesIO(b"data")
        mock_result = MagicMock()
        mock_result.markdown = "# Stream Content"

        mock_md = MagicMock()
        mock_md.convert_stream.return_value = mock_result

        with patch.object(local_converter, "get_markitdown_instance", return_value=mock_md):
            success, content, error = local_converter.convert_stream_with_markitdown(stream, "test.txt")

        assert success is True
        assert "Stream Content" in content


# ============================================================================
# extract_tables_pdfplumber Tests (mocked)
# ============================================================================


class TestExtractTablesPdfplumber:
    """Test pdfplumber table extraction with mocks."""

    def test_returns_empty_when_not_installed(self, tmp_path):
        with patch.object(local_converter, "pdfplumber", None):
            result = local_converter.extract_tables_pdfplumber(tmp_path / "test.pdf")
        assert result == []

    def test_extracts_tables(self, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [[["H1", "H2"], ["A", "B"]]]

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch.object(local_converter, "pdfplumber") as mock_plumber:
            mock_plumber.open.return_value = mock_pdf
            result = local_converter.extract_tables_pdfplumber(pdf_file)

        assert len(result) == 1
        assert result[0] == [["H1", "H2"], ["A", "B"]]

    def test_handles_exception(self, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        with patch.object(local_converter, "pdfplumber") as mock_plumber:
            mock_plumber.open.side_effect = Exception("corrupt PDF")
            result = local_converter.extract_tables_pdfplumber(pdf_file)

        assert result == []


# ============================================================================
# extract_tables_camelot Tests (mocked)
# ============================================================================


class TestExtractTablesCamelot:
    """Test camelot table extraction with mocks."""

    def test_returns_empty_when_not_installed(self, tmp_path):
        with patch.object(local_converter, "camelot", None):
            result = local_converter.extract_tables_camelot(tmp_path / "test.pdf")
        assert result == []

    def test_handles_exception(self, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        with patch.object(local_converter, "camelot") as mock_cam:
            mock_cam.read_pdf.side_effect = Exception("ghostscript not found")
            result = local_converter.extract_tables_camelot(pdf_file)

        assert result == []


# ============================================================================
# save_tables_to_files Tests
# ============================================================================


class TestSaveTablesToFiles:
    """Test table file saving."""

    def test_saves_markdown_and_csv(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)
        monkeypatch.setattr(config, "INCLUDE_METADATA", False)
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)

        pdf_file = tmp_path / "report.pdf"
        pdf_file.touch()

        tables = [[["Name", "Value"], ["A", "1"], ["B", "2"]]]
        result = local_converter.save_tables_to_files(pdf_file, tables)

        assert len(result) > 0
        # Check markdown file exists
        md_files = list(tmp_path.glob("*.md"))
        assert len(md_files) > 0

    def test_empty_tables_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)

        pdf_file = tmp_path / "report.pdf"
        pdf_file.touch()

        result = local_converter.save_tables_to_files(pdf_file, [])
        assert result == []


# ============================================================================
# convert_pdf_to_images Tests (mocked)
# ============================================================================


class TestConvertPdfToImages:
    """Test PDF to images conversion with mocks."""

    def test_not_installed(self, tmp_path):
        with patch.object(local_converter, "convert_from_path", None):
            success, paths, error = local_converter.convert_pdf_to_images(tmp_path / "test.pdf")
        assert success is False
        assert "not installed" in error.lower() or "not available" in error.lower()

    def test_successful_conversion(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "OUTPUT_IMAGES_DIR", tmp_path)
        monkeypatch.setattr(config, "PDF_IMAGE_DPI", 200)
        monkeypatch.setattr(config, "PDF_IMAGE_FORMAT", "png")
        monkeypatch.setattr(config, "POPPLER_PATH", "")
        monkeypatch.setattr(config, "PDF_IMAGE_THREAD_COUNT", 1)
        monkeypatch.setattr(config, "PDF_IMAGE_USE_PDFTOCAIRO", False)

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        # Create mock PIL Image objects
        mock_img1 = MagicMock()
        mock_img2 = MagicMock()

        with patch.object(local_converter, "convert_from_path", return_value=[mock_img1, mock_img2]):
            success, paths, error = local_converter.convert_pdf_to_images(pdf_file)

        assert success is True
        assert len(paths) == 2

    def test_handles_conversion_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "OUTPUT_IMAGES_DIR", tmp_path)
        monkeypatch.setattr(config, "PDF_IMAGE_DPI", 200)
        monkeypatch.setattr(config, "PDF_IMAGE_FORMAT", "png")
        monkeypatch.setattr(config, "POPPLER_PATH", "")
        monkeypatch.setattr(config, "PDF_IMAGE_THREAD_COUNT", 1)
        monkeypatch.setattr(config, "PDF_IMAGE_USE_PDFTOCAIRO", False)

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        with patch.object(local_converter, "convert_from_path", side_effect=Exception("poppler not found")):
            success, paths, error = local_converter.convert_pdf_to_images(pdf_file)

        assert success is False
        assert "poppler" in error.lower()


# ============================================================================
# extract_all_tables Tests (mocked)
# ============================================================================


class TestExtractAllTables:
    """Test combined table extraction."""

    def test_combines_pdfplumber_and_camelot(self, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        table1 = [["A", "B"], ["1", "2"]]
        table2 = [["C", "D"], ["3", "4"]]

        with patch.object(local_converter, "extract_tables_pdfplumber", return_value=[table1]):
            with patch.object(local_converter, "extract_tables_camelot", return_value=[table2]):
                result = local_converter.extract_all_tables(pdf_file)

        assert result["table_count"] >= 1
        assert "pdfplumber" in result["methods_used"]

    def test_all_methods_fail_returns_empty(self, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        with patch.object(local_converter, "extract_tables_pdfplumber", return_value=[]):
            with patch.object(local_converter, "extract_tables_camelot", return_value=[]):
                result = local_converter.extract_all_tables(pdf_file)

        assert result["table_count"] == 0
        assert result["tables"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
