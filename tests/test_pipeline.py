"""
Tests for main.py pipeline modes.

Tests cover:
- mode_convert_smart (smart routing by content analysis)
- mode_markitdown_only / mode_mistral_ocr_only (concurrency)
- Dispatch table integrity
"""

from unittest.mock import patch, MagicMock

import pytest

import config

config.ensure_directories()

import main


# ============================================================================
# mode_convert_smart Tests
# ============================================================================


class TestModeConvertSmart:
    """Test the smart auto-routing conversion mode."""

    @patch("main.mistral_converter")
    @patch("main.local_converter")
    def test_scanned_pdf_routes_to_ocr(self, mock_local, mock_mistral, tmp_path, monkeypatch):
        """Scanned PDFs (no text layer) should route to Mistral OCR."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MAX_BATCH_FILES", 0)
        monkeypatch.setattr(config, "MAX_CONCURRENT_FILES", 1)

        pdf_file = tmp_path / "scanned.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%EOF")

        mock_local.analyze_file_content.return_value = {
            "is_text_based": False, "file_type": "pdf", "page_count": 1,
        }
        mock_local.extract_all_tables.return_value = {
            "tables": [], "table_count": 0, "methods_used": [],
        }
        mock_mistral.convert_with_mistral_ocr.return_value = (True, tmp_path / "out.md", None)

        success, message = main.mode_convert_smart([pdf_file])

        assert success is True
        mock_mistral.convert_with_mistral_ocr.assert_called_once_with(pdf_file)

    @patch("main.local_converter")
    def test_text_pdf_routes_to_markitdown(self, mock_local, tmp_path, monkeypatch):
        """Text-based PDFs should route to MarkItDown (free, faster)."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MAX_BATCH_FILES", 0)
        monkeypatch.setattr(config, "MAX_CONCURRENT_FILES", 1)
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)

        pdf_file = tmp_path / "textbased.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%EOF")

        mock_local.analyze_file_content.return_value = {
            "is_text_based": True, "file_type": "pdf", "page_count": 5,
        }
        mock_local.extract_all_tables.return_value = {
            "tables": [], "table_count": 0, "methods_used": [],
        }
        mock_local.convert_with_markitdown.return_value = (True, "Content", None)

        success, _ = main.mode_convert_smart([pdf_file])

        assert success is True
        mock_local.convert_with_markitdown.assert_called_once_with(pdf_file)

    @patch("main.local_converter")
    def test_docx_always_routes_to_markitdown(self, mock_local, tmp_path, monkeypatch):
        """DOCX should always use MarkItDown, even with API key set."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MAX_BATCH_FILES", 0)
        monkeypatch.setattr(config, "MAX_CONCURRENT_FILES", 1)
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)

        docx_file = tmp_path / "doc.docx"
        docx_file.write_bytes(b"PK\x03\x04")

        mock_local.convert_with_markitdown.return_value = (True, "Content", None)

        success, message = main.mode_convert_smart([docx_file])

        assert success is True
        mock_local.convert_with_markitdown.assert_called_once_with(docx_file)

    @patch("main.mistral_converter")
    def test_image_routes_to_ocr(self, mock_mistral, tmp_path, monkeypatch):
        """Image files should always route to Mistral OCR."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MAX_BATCH_FILES", 0)
        monkeypatch.setattr(config, "MAX_CONCURRENT_FILES", 1)

        png_file = tmp_path / "scan.png"
        png_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        mock_mistral.convert_with_mistral_ocr.return_value = (True, tmp_path / "out.md", None)

        success, _ = main.mode_convert_smart([png_file])

        assert success is True
        mock_mistral.convert_with_mistral_ocr.assert_called_once_with(png_file)

    @patch("main.local_converter")
    def test_no_api_key_all_to_markitdown(self, mock_local, tmp_path, monkeypatch):
        """Without API key, all files (even images) route to MarkItDown."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "")
        monkeypatch.setattr(config, "MAX_BATCH_FILES", 0)
        monkeypatch.setattr(config, "MAX_CONCURRENT_FILES", 1)
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)

        png_file = tmp_path / "scan.png"
        png_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        mock_local.convert_with_markitdown.return_value = (True, "Content", None)

        success, _ = main.mode_convert_smart([png_file])

        assert success is True
        mock_local.convert_with_markitdown.assert_called_once()

    @patch("main.local_converter")
    def test_txt_routes_to_markitdown(self, mock_local, tmp_path, monkeypatch):
        """txt files should always route to MarkItDown."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MAX_BATCH_FILES", 0)
        monkeypatch.setattr(config, "MAX_CONCURRENT_FILES", 1)
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)

        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("hello world")

        mock_local.convert_with_markitdown.return_value = (True, "hello world", None)

        success, _ = main.mode_convert_smart([txt_file])

        assert success is True
        mock_local.convert_with_markitdown.assert_called_once_with(txt_file)

    @patch("main.mistral_converter")
    @patch("main.local_converter")
    def test_pdf_table_extraction_runs(self, mock_local, mock_mistral, tmp_path, monkeypatch):
        """PDF table extraction should run regardless of OCR routing."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MAX_BATCH_FILES", 0)
        monkeypatch.setattr(config, "MAX_CONCURRENT_FILES", 1)

        pdf_file = tmp_path / "tables.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n%EOF")

        fake_tables = [[["H1", "H2"], ["A", "B"]]]
        mock_local.analyze_file_content.return_value = {"is_text_based": False}
        mock_local.extract_all_tables.return_value = {
            "tables": fake_tables, "table_count": 1, "methods_used": ["pdfplumber"],
        }
        mock_local.save_tables_to_files.return_value = [tmp_path / "tables_all.md"]
        mock_mistral.convert_with_mistral_ocr.return_value = (True, tmp_path / "out.md", None)

        success, _ = main.mode_convert_smart([pdf_file])

        assert success is True
        mock_local.save_tables_to_files.assert_called_once_with(pdf_file, fake_tables)

    def test_batch_size_guardrail(self, tmp_path, monkeypatch):
        """Should reject batches exceeding MAX_BATCH_FILES."""
        monkeypatch.setattr(config, "MAX_BATCH_FILES", 2)

        files = [tmp_path / f"doc{i}.pdf" for i in range(5)]
        for f in files:
            f.write_bytes(b"%PDF-1.4")

        success, message = main.mode_convert_smart(files)

        assert success is False
        assert "MAX_BATCH_FILES" in message


# ============================================================================
# Concurrency Tests
# ============================================================================


class TestModeConcurrency:
    """Test that MarkItDown and Mistral OCR modes handle multiple files."""

    @patch("main.local_converter")
    def test_markitdown_processes_all(self, mock_local, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MAX_CONCURRENT_FILES", 2)

        files = []
        for i in range(3):
            f = tmp_path / f"doc{i}.txt"
            f.write_text(f"content {i}")
            files.append(f)

        mock_local.convert_with_markitdown.return_value = (True, "ok", None)

        success, message = main.mode_markitdown_only(files)

        assert success is True
        assert "3/3" in message
        assert mock_local.convert_with_markitdown.call_count == 3

    @patch("main.mistral_converter")
    def test_mistral_ocr_processes_all(self, mock_mistral, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MAX_CONCURRENT_FILES", 2)

        files = []
        for i in range(2):
            f = tmp_path / f"doc{i}.pdf"
            f.write_bytes(b"%PDF-1.4")
            files.append(f)

        mock_mistral.convert_with_mistral_ocr.return_value = (True, tmp_path / "out.md", None)

        success, message = main.mode_mistral_ocr_only(files)

        assert success is True
        assert "2/2" in message


# ============================================================================
# Dispatch Table Tests
# ============================================================================


class TestDispatchTable:
    """Test the mode dispatch infrastructure."""

    def test_all_cli_modes_in_dispatch(self):
        expected_modes = {
            "smart", "markitdown", "mistral_ocr", "pdf_to_images", "qna", "batch_ocr",
        }
        actual_modes = set(main._CLI_MODE_DISPATCH.keys())
        assert expected_modes == actual_modes

    def test_menu_choices_have_handlers(self):
        expected_choices = {"1", "2", "3", "4", "5", "6"}
        actual_choices = set(main.MODE_DISPATCH.keys())
        assert expected_choices == actual_choices

    def test_dispatch_handlers_are_callable(self):
        for choice, (cli_name, handler) in main.MODE_DISPATCH.items():
            assert callable(handler), f"Handler for {cli_name} (choice {choice}) is not callable"


# ============================================================================
# Job ID Validation Tests
# ============================================================================


class TestValidateJobId:
    """Test batch job ID input validation."""

    @pytest.mark.parametrize("job_id", [
        "abc-def-123",
        "550e8400-e29b-41d4-a716-446655440000",
        "a" * 128,
        "job_123_test",
    ])
    def test_valid_job_ids(self, job_id):
        assert main._validate_job_id(job_id) is True

    @pytest.mark.parametrize("job_id", [
        "",
        "id with spaces",
        "id;DROP TABLE",
        "../../../etc/passwd",
        "a" * 129,
        "id\nnewline",
    ])
    def test_invalid_job_ids(self, job_id):
        assert main._validate_job_id(job_id) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
