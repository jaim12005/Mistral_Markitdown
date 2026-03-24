"""
Tests for local_converter.py module.

Tests cover:
- _fix_merged_currency_cells (dollar pairs, bare numbers, text preservation)
- _fix_split_headers (fragmented header rejoining)
- coalesce_tables (merging tables with identical headers)
- _deduplicate_tables (content-based deduplication)
- analyze_file_content (file type analysis)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402

config.ensure_directories()

import local_converter  # noqa: E402


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
