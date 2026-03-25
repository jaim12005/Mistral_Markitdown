"""
Tests for main.py pipeline modes.

Tests cover:
- mode_convert_smart (smart routing by content analysis)
- mode_markitdown_only / mode_mistral_ocr_only (concurrency)
- Dispatch table integrity
- _list_input_files, _filter_valid_files
- _process_files_concurrently
- _should_use_ocr, _route_label
- mode_pdf_to_images, mode_document_qna, mode_batch_ocr
- mode_system_status
- select_files, main (CLI)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import config

config.ensure_directories()

import local_converter
import main
import mistral_converter
import utils

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
            "is_text_based": False,
            "file_type": "pdf",
            "page_count": 1,
        }
        mock_local.extract_all_tables.return_value = {
            "tables": [],
            "table_count": 0,
            "methods_used": [],
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
            "is_text_based": True,
            "file_type": "pdf",
            "page_count": 5,
        }
        mock_local.extract_all_tables.return_value = {
            "tables": [],
            "table_count": 0,
            "methods_used": [],
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
            "tables": fake_tables,
            "table_count": 1,
            "methods_used": ["pdfplumber"],
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
            "smart",
            "markitdown",
            "mistral_ocr",
            "pdf_to_images",
            "qna",
            "batch_ocr",
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

    @pytest.mark.parametrize(
        "job_id",
        [
            "abc-def-123",
            "550e8400-e29b-41d4-a716-446655440000",
            "a" * 128,
            "job_123_test",
        ],
    )
    def test_valid_job_ids(self, job_id):
        assert main._validate_job_id(job_id) is True

    @pytest.mark.parametrize(
        "job_id",
        [
            "",
            "id with spaces",
            "id;DROP TABLE",
            "../../../etc/passwd",
            "a" * 129,
            "id\nnewline",
        ],
    )
    def test_invalid_job_ids(self, job_id):
        assert main._validate_job_id(job_id) is False


# ============================================================================
# _list_input_files Tests
# ============================================================================


class TestListInputFiles:
    """Test input file listing."""

    def test_lists_files_sorted(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        (tmp_path / "beta.pdf").touch()
        (tmp_path / "alpha.txt").touch()
        (tmp_path / "gamma.docx").touch()
        result = main._list_input_files()
        names = [f.name for f in result]
        assert names == ["alpha.txt", "beta.pdf", "gamma.docx"]

    def test_empty_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        result = main._list_input_files()
        assert result == []

    def test_ignores_directories(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        (tmp_path / "subdir").mkdir()
        (tmp_path / "file.pdf").touch()
        result = main._list_input_files()
        assert len(result) == 1
        assert result[0].name == "file.pdf"


# ============================================================================
# _filter_valid_files Tests
# ============================================================================


class TestFilterValidFiles:
    """Test file validation filtering."""

    def test_filters_invalid_files(self, tmp_path):
        valid = tmp_path / "good.pdf"
        valid.write_text("content")
        invalid = tmp_path / "bad.xyz"
        invalid.write_text("content")
        result = main._filter_valid_files([valid, invalid])
        assert len(result) == 1
        assert result[0].name == "good.pdf"

    def test_filters_empty_files(self, tmp_path):
        empty = tmp_path / "empty.pdf"
        empty.touch()
        result = main._filter_valid_files([empty])
        assert result == []


# ============================================================================
# _process_files_concurrently Tests
# ============================================================================


class TestProcessFilesConcurrently:
    """Test concurrent file processing."""

    def test_single_file_success(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("data")
        success, failed = main._process_files_concurrently([f], lambda p: (True, "content", None))
        assert success == 1
        assert failed == 0

    def test_single_file_failure(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("data")
        success, failed = main._process_files_concurrently([f], lambda p: (False, None, "error"))
        assert success == 0
        assert failed == 1

    def test_single_file_exception(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("data")

        def raise_fn(p):
            raise RuntimeError("boom")

        success, failed = main._process_files_concurrently([f], raise_fn)
        assert success == 0
        assert failed == 1

    def test_multiple_files_concurrent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MAX_CONCURRENT_FILES", 2)
        files = []
        for i in range(3):
            f = tmp_path / f"doc{i}.txt"
            f.write_text(f"content {i}")
            files.append(f)

        success, failed = main._process_files_concurrently(files, lambda p: (True, "ok", None))
        assert success == 3
        assert failed == 0

    def test_concurrent_failure(self, tmp_path, monkeypatch):
        """Lines 121-123: concurrent path with failed result."""
        monkeypatch.setattr(config, "MAX_CONCURRENT_FILES", 2)
        files = []
        for i in range(2):
            f = tmp_path / f"doc{i}.txt"
            f.write_text(f"content {i}")
            files.append(f)

        success, failed = main._process_files_concurrently(files, lambda p: (False, None, "failed"))
        assert success == 0
        assert failed == 2

    def test_concurrent_exception(self, tmp_path, monkeypatch):
        """Lines 124-126: concurrent path with exception."""
        monkeypatch.setattr(config, "MAX_CONCURRENT_FILES", 2)
        files = []
        for i in range(2):
            f = tmp_path / f"doc{i}.txt"
            f.write_text(f"content {i}")
            files.append(f)

        def raise_fn(p):
            raise RuntimeError("boom")

        success, failed = main._process_files_concurrently(files, raise_fn)
        assert success == 0
        assert failed == 2


# ============================================================================
# _should_use_ocr / _route_label Tests
# ============================================================================


class TestShouldUseOcr:
    """Test OCR routing decisions."""

    def test_no_api_key_returns_false(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "")
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        assert main._should_use_ocr(pdf) is False

    def test_image_always_ocr(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG")
        assert main._should_use_ocr(img) is True

    def test_office_doc_uses_markitdown(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        doc = tmp_path / "test.docx"
        doc.write_bytes(b"PK\x03\x04")
        assert main._should_use_ocr(doc) is False


class TestRouteLabel:
    """Test route label generation."""

    def test_image_label(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG")
        label = main._route_label_cached(img, use_ocr=True)
        assert "Mistral OCR" in label

    def test_office_doc_label(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        doc = tmp_path / "test.docx"
        doc.write_bytes(b"PK\x03\x04")
        label = main._route_label_cached(doc, use_ocr=False)
        assert "MarkItDown" in label


# ============================================================================
# mode_pdf_to_images Tests
# ============================================================================


class TestModePdfToImages:
    """Test PDF to images mode."""

    @patch("main.local_converter")
    def test_converts_pdfs(self, mock_local, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "VERBOSE_PROGRESS", False)
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        mock_local.convert_pdf_to_images.return_value = (True, [tmp_path / "page1.png", tmp_path / "page2.png"], None)

        success, msg = main.mode_pdf_to_images([pdf])
        assert success is True
        assert "2 total pages" in msg

    @patch("main.local_converter")
    def test_skips_non_pdfs(self, mock_local, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "VERBOSE_PROGRESS", False)
        txt = tmp_path / "test.txt"
        txt.write_text("hello")

        success, msg = main.mode_pdf_to_images([txt])
        assert success is True
        mock_local.convert_pdf_to_images.assert_not_called()

    @patch("main.local_converter")
    def test_handles_failure(self, mock_local, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "VERBOSE_PROGRESS", False)
        pdf = tmp_path / "bad.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        mock_local.convert_pdf_to_images.return_value = (False, [], "corrupt file")
        success, msg = main.mode_pdf_to_images([pdf])
        assert success is False


# ============================================================================
# mode_document_qna Tests
# ============================================================================


class TestModeDocumentQna:
    """Test document QnA mode."""

    def test_requires_api_key(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "")
        success, msg = main.mode_document_qna([tmp_path / "doc.pdf"])
        assert success is False
        assert "MISTRAL_API_KEY" in msg

    def test_requires_single_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        files = [tmp_path / "a.pdf", tmp_path / "b.pdf"]
        success, msg = main.mode_document_qna(files)
        assert success is False
        assert "one file" in msg.lower()

    def test_rejects_large_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        huge = tmp_path / "huge.pdf"
        huge.write_bytes(b"\x00" * (51 * 1024 * 1024))  # 51 MB

        with patch.object(main, "mistral_converter") as mock_mc:
            mock_mc.get_mistral_client.return_value = MagicMock()
            success, msg = main.mode_document_qna([huge])

        assert success is False
        assert "too large" in msg.lower()


# ============================================================================
# mode_batch_ocr Tests
# ============================================================================


class TestModeBatchOcr:
    """Test batch OCR mode."""

    def test_requires_api_key(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "")
        success, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])
        assert success is False
        assert "MISTRAL_API_KEY" in msg

    def test_requires_batch_enabled(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", False)
        success, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])
        assert success is False
        assert "disabled" in msg.lower()

    def test_cancel_option(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 1)
        with patch("builtins.input", return_value="0"):
            success, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])
        assert success is False

    def test_submit_job_flow(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 1)
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)

        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF")

        with patch("builtins.input", return_value="1"):
            with patch.object(main, "mistral_converter") as mock_mc:
                mock_mc.create_batch_ocr_file.return_value = (True, tmp_path / "batch.jsonl", None)
                mock_mc.submit_batch_ocr_job.return_value = (True, "job-123", None)
                success, msg = main.mode_batch_ocr([pdf])

        assert success is True
        assert "job-123" in msg

    def test_check_status_flow(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 1)

        inputs = iter(["2", "job-abc-123"])
        with patch("builtins.input", side_effect=inputs):
            with patch.object(main, "mistral_converter") as mock_mc:
                mock_mc.get_batch_job_status.return_value = (
                    True,
                    {"status": "completed", "progress_percent": 100, "succeeded_requests": 5, "failed_requests": 0},
                    None,
                )
                success, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])

        assert success is True
        assert "completed" in msg

    def test_list_jobs_flow(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 1)

        with patch("builtins.input", return_value="3"):
            with patch.object(main, "mistral_converter") as mock_mc:
                mock_mc.list_batch_jobs.return_value = (
                    True,
                    [{"id": "job-1", "status": "completed", "total_requests": 3, "created_at": "2025-01-01"}],
                    None,
                )
                success, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])

        assert success is True
        assert "1 batch" in msg

    def test_download_results_flow(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 1)

        inputs = iter(["4", "job-xyz"])
        with patch("builtins.input", side_effect=inputs):
            with patch.object(main, "mistral_converter") as mock_mc:
                mock_mc.download_batch_results.return_value = (True, "/output/results.md", None)
                success, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])

        assert success is True
        assert "downloaded" in msg.lower()


# ============================================================================
# mode_system_status Tests
# ============================================================================


class TestModeSystemStatus:
    """Test system status mode."""

    def test_displays_status(self, monkeypatch):
        monkeypatch.setattr(config, "CLEANUP_OLD_UPLOADS", False)
        monkeypatch.setattr(config, "AUTO_CLEAR_CACHE", False)
        success, msg = main.mode_system_status()
        assert success is True
        assert "status" in msg.lower()


# ============================================================================
# select_files Tests
# ============================================================================


class TestSelectFiles:
    """Test file selection."""

    def test_empty_dir_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        result = main.select_files()
        assert result == []

    def test_cancel_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        (tmp_path / "test.pdf").write_text("content")
        with patch("builtins.input", return_value="0"):
            result = main.select_files()
        assert result == []

    def test_select_all(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        (tmp_path / "a.pdf").write_text("content")
        (tmp_path / "b.txt").write_text("content")
        # "3" is len(files)+1 for "Process ALL"
        with patch("builtins.input", return_value="3"):
            result = main.select_files()
        assert len(result) == 2

    def test_select_single(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        (tmp_path / "a.pdf").write_text("content")
        (tmp_path / "b.txt").write_text("content")
        with patch("builtins.input", return_value="1"):
            result = main.select_files()
        assert len(result) == 1


# ============================================================================
# main() CLI Tests
# ============================================================================


class TestMainCli:
    """Test main() entry point."""

    def test_test_mode(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["main.py", "--test"])
        monkeypatch.setattr(config, "CLEANUP_OLD_UPLOADS", False)
        monkeypatch.setattr(config, "AUTO_CLEAR_CACHE", False)
        # Should not raise
        main.main()

    def test_status_mode(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["main.py", "--mode", "status"])
        monkeypatch.setattr(config, "CLEANUP_OLD_UPLOADS", False)
        monkeypatch.setattr(config, "AUTO_CLEAR_CACHE", False)
        main.main()

    def test_no_files_non_interactive(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", ["main.py", "--mode", "markitdown", "--no-interactive"])
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        # Empty dir → should print message and return
        main.main()

    def test_direct_mode_markitdown(self, tmp_path, monkeypatch):
        """Test direct mode execution with --mode and files."""
        monkeypatch.setattr("sys.argv", ["main.py", "--mode", "markitdown", "--no-interactive"])
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path / "out")
        monkeypatch.setattr(config, "OUTPUT_TXT_DIR", tmp_path / "out_txt")
        monkeypatch.setattr(config, "CLEANUP_OLD_UPLOADS", False)
        monkeypatch.setattr(config, "AUTO_CLEAR_CACHE", False)

        (tmp_path / "out").mkdir()
        (tmp_path / "out_txt").mkdir()

        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello world")

        with pytest.raises(SystemExit) as exc_info:
            main.main()
        # Could be 0 (success) or 1 (failure), depending on markitdown availability
        assert exc_info.value.code in (0, 1)

    def test_direct_mode_with_select_files(self, tmp_path, monkeypatch):
        """Test direct mode that calls select_files (no --no-interactive)."""
        monkeypatch.setattr("sys.argv", ["main.py", "--mode", "markitdown"])
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path / "out")
        monkeypatch.setattr(config, "OUTPUT_TXT_DIR", tmp_path / "out_txt")
        monkeypatch.setattr(config, "CLEANUP_OLD_UPLOADS", False)
        monkeypatch.setattr(config, "AUTO_CLEAR_CACHE", False)

        (tmp_path / "out").mkdir()
        (tmp_path / "out_txt").mkdir()

        # select_files returns empty → main returns without processing
        with patch.object(main, "select_files", return_value=[]):
            main.main()

    def test_no_mode_runs_interactive(self, monkeypatch):
        """Test that no --mode arg runs interactive menu."""
        monkeypatch.setattr("sys.argv", ["main.py"])
        monkeypatch.setattr(config, "CLEANUP_OLD_UPLOADS", False)
        monkeypatch.setattr(config, "AUTO_CLEAR_CACHE", False)

        with patch.object(main, "interactive_menu") as mock_menu:
            main.main()
        mock_menu.assert_called_once()


# ============================================================================
# interactive_menu Tests
# ============================================================================


class TestInteractiveMenu:
    """Test the interactive menu loop."""

    def test_exit_immediately(self, monkeypatch):
        """Test user choosing 0 to exit."""
        monkeypatch.setattr("builtins.input", lambda _: "0")
        main.interactive_menu()

    def test_invalid_then_exit(self, monkeypatch):
        """Test invalid choice followed by exit."""
        inputs = iter(["9", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        main.interactive_menu()

    def test_status_then_exit(self, monkeypatch):
        """Test showing system status then exit."""
        inputs = iter(["7", "", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        main.interactive_menu()

    def test_keyboard_interrupt(self, monkeypatch):
        """Test KeyboardInterrupt exits gracefully."""
        monkeypatch.setattr("builtins.input", MagicMock(side_effect=KeyboardInterrupt))
        main.interactive_menu()


# ============================================================================
# select_files Tests (expanded)
# ============================================================================


class TestSelectFilesExpanded:
    """Test file selection menu."""

    def test_select_specific_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        f1 = tmp_path / "doc1.txt"
        f1.write_text("hello")

        monkeypatch.setattr("builtins.input", lambda _: "1")
        result = main.select_files()
        assert len(result) == 1

    def test_select_all_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        f1 = tmp_path / "doc1.txt"
        f1.write_text("hello")
        f2 = tmp_path / "doc2.txt"
        f2.write_text("world")

        # 3 = "Process ALL files" when there are 2 files
        monkeypatch.setattr("builtins.input", lambda _: "3")
        result = main.select_files()
        assert len(result) == 2

    def test_cancel_selection(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        f1 = tmp_path / "doc1.txt"
        f1.write_text("hello")

        monkeypatch.setattr("builtins.input", lambda _: "0")
        result = main.select_files()
        assert result == []

    def test_eof_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        f1 = tmp_path / "doc1.txt"
        f1.write_text("hello")

        monkeypatch.setattr("builtins.input", MagicMock(side_effect=EOFError))
        result = main.select_files()
        assert result == []


# ============================================================================
# show_menu Tests
# ============================================================================


class TestShowMenu:
    """Test menu display."""

    def test_show_menu_runs(self, capsys):
        main.show_menu()
        captured = capsys.readouterr()
        assert "ENHANCED DOCUMENT CONVERTER" in captured.out
        assert "Exit" in captured.out


# ============================================================================
# mode_document_qna expanded
# ============================================================================


class TestModeConvertSmartExpanded:
    """Test mode_convert_smart uncovered branches."""

    def test_table_extraction_exception(self, tmp_path, monkeypatch):
        """Lines 192-193: table extraction throws exception."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "")
        monkeypatch.setattr(config, "MAX_CONCURRENT_FILES", 1)
        monkeypatch.setattr(config, "MAX_BATCH_FILES", 0)
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path / "out")
        (tmp_path / "out").mkdir()

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")

        with patch.object(local_converter, "extract_all_tables", side_effect=Exception("extraction failed")):
            with patch.object(local_converter, "convert_with_markitdown", return_value=(True, "content", None)):
                ok, msg = main.mode_convert_smart([pdf])
        assert ok is True

    def test_batch_size_exceeded(self, tmp_path, monkeypatch):
        """Lines 324, 333-388: batch guardrail check."""
        monkeypatch.setattr(config, "MAX_BATCH_FILES", 1)
        files = [tmp_path / "a.pdf", tmp_path / "b.pdf"]
        ok, msg = main.mode_convert_smart(files)
        assert ok is False
        assert "MAX_BATCH_FILES" in msg

    def test_full_smart_mode(self, tmp_path, monkeypatch):
        """Lines 333-388: full mode_convert_smart execution."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MAX_CONCURRENT_FILES", 1)
        monkeypatch.setattr(config, "MAX_BATCH_FILES", 0)
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path / "out")
        (tmp_path / "out").mkdir()

        doc = tmp_path / "test.docx"
        doc.write_bytes(b"PK\x03\x04")

        with patch.object(local_converter, "convert_with_markitdown", return_value=(True, "content", None)):
            ok, msg = main.mode_convert_smart([doc])
        assert ok is True


class TestModeBatchOcrExpanded:
    """Test batch OCR edge cases (uncovered lines)."""

    def test_min_files_warning(self, tmp_path, monkeypatch):
        """Lines 416-417: batch min files note."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 5)

        with patch("builtins.input", return_value="0"):
            ok, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])
        assert ok is False

    def test_keyboard_interrupt_on_input(self, tmp_path, monkeypatch):
        """Lines 428-429: KeyboardInterrupt."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 1)

        with patch("builtins.input", side_effect=KeyboardInterrupt):
            ok, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])
        assert ok is False
        assert "Cancelled" in msg

    def test_create_batch_file_failure(self, tmp_path, monkeypatch):
        """Line 437: create_batch_ocr_file fails."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 1)
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)

        with patch("builtins.input", return_value="1"):
            with patch.object(main, "mistral_converter") as mock_mc:
                mock_mc.create_batch_ocr_file.return_value = (False, None, "creation error")
                ok, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])
        assert ok is False
        assert "Failed to create" in msg

    def test_submit_batch_job_failure(self, tmp_path, monkeypatch):
        """Line 446: submit_batch_ocr_job fails."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 1)
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)

        with patch("builtins.input", return_value="1"):
            with patch.object(main, "mistral_converter") as mock_mc:
                mock_mc.create_batch_ocr_file.return_value = (True, tmp_path / "batch.jsonl", None)
                mock_mc.submit_batch_ocr_job.return_value = (False, None, "submit error")
                ok, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])
        assert ok is False
        assert "Failed to submit" in msg

    def test_check_status_empty_job_id(self, tmp_path, monkeypatch):
        """Line 451: empty job ID."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 1)

        inputs = iter(["2", ""])
        with patch("builtins.input", side_effect=inputs):
            ok, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])
        assert ok is False
        assert "No job ID" in msg

    def test_check_status_invalid_job_id(self, tmp_path, monkeypatch):
        """Line 453: invalid job ID format."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 1)

        inputs = iter(["2", "invalid job!@#"])
        with patch("builtins.input", side_effect=inputs):
            ok, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])
        assert ok is False
        assert "Invalid job ID" in msg

    def test_check_status_error(self, tmp_path, monkeypatch):
        """Line 463: status check returns error."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 1)

        inputs = iter(["2", "job-abc"])
        with patch("builtins.input", side_effect=inputs):
            with patch.object(main, "mistral_converter") as mock_mc:
                mock_mc.get_batch_job_status.return_value = (False, None, "not found")
                ok, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])
        assert ok is False
        assert "Error" in msg

    def test_list_jobs_empty(self, tmp_path, monkeypatch):
        """Lines 472-474: list returns empty."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 1)

        with patch("builtins.input", return_value="3"):
            with patch.object(main, "mistral_converter") as mock_mc:
                mock_mc.list_batch_jobs.return_value = (True, [], None)
                ok, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])
        assert ok is True
        assert "No batch jobs" in msg

    def test_list_jobs_error(self, tmp_path, monkeypatch):
        """Lines 475-476: list returns error."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 1)

        with patch("builtins.input", return_value="3"):
            with patch.object(main, "mistral_converter") as mock_mc:
                mock_mc.list_batch_jobs.return_value = (False, None, "API error")
                ok, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])
        assert ok is False

    def test_download_empty_job_id(self, tmp_path, monkeypatch):
        """Line 481: download with empty job ID."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 1)

        inputs = iter(["4", ""])
        with patch("builtins.input", side_effect=inputs):
            ok, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])
        assert ok is False
        assert "No job ID" in msg

    def test_download_invalid_job_id(self, tmp_path, monkeypatch):
        """Line 483: download with invalid job ID."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 1)

        inputs = iter(["4", "bad id!!!"])
        with patch("builtins.input", side_effect=inputs):
            ok, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])
        assert ok is False
        assert "Invalid job ID" in msg

    def test_download_error(self, tmp_path, monkeypatch):
        """Line 489: download fails."""
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_BATCH_ENABLED", True)
        monkeypatch.setattr(config, "MISTRAL_BATCH_MIN_FILES", 1)

        inputs = iter(["4", "job-xyz"])
        with patch("builtins.input", side_effect=inputs):
            with patch.object(main, "mistral_converter") as mock_mc:
                mock_mc.download_batch_results.return_value = (False, None, "not ready")
                ok, msg = main.mode_batch_ocr([tmp_path / "doc.pdf"])
        assert ok is False
        assert "Error" in msg


class TestModeSystemStatusExpanded:
    """Test system status uncovered branches."""

    def test_cache_over_100_entries(self, monkeypatch):
        """Line 558: > 100 cache entries recommendation."""
        monkeypatch.setattr(config, "CLEANUP_OLD_UPLOADS", False)
        monkeypatch.setattr(config, "AUTO_CLEAR_CACHE", False)

        mock_stats = {
            "total_entries": 150,
            "total_size_mb": 5.0,
            "cache_hits": 100,
            "cache_misses": 50,
            "hit_rate": 66.7,
        }
        with patch.object(utils.cache, "get_statistics", return_value=mock_stats):
            ok, msg = main.mode_system_status()
        assert ok is True

    def test_auto_clear_cache(self, monkeypatch):
        """Line 563: auto clear cache returns > 0."""
        monkeypatch.setattr(config, "CLEANUP_OLD_UPLOADS", False)
        monkeypatch.setattr(config, "AUTO_CLEAR_CACHE", True)

        with patch.object(utils.cache, "clear_old_entries", return_value=5):
            ok, msg = main.mode_system_status()
        assert ok is True

    def test_cleanup_uploads(self, monkeypatch):
        """Lines 566-571: cleanup uploaded files."""
        monkeypatch.setattr(config, "CLEANUP_OLD_UPLOADS", True)
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "AUTO_CLEAR_CACHE", False)

        mock_client = MagicMock()
        with patch.object(mistral_converter, "get_mistral_client", return_value=mock_client):
            with patch.object(mistral_converter, "cleanup_uploaded_files", return_value=3):
                ok, msg = main.mode_system_status()
        assert ok is True

    def test_cleanup_uploads_exception(self, monkeypatch):
        """Lines 572-573: cleanup raises exception."""
        monkeypatch.setattr(config, "CLEANUP_OLD_UPLOADS", True)
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "AUTO_CLEAR_CACHE", False)

        with patch.object(mistral_converter, "get_mistral_client", side_effect=Exception("API fail")):
            ok, msg = main.mode_system_status()
        assert ok is True

    def test_all_systems_operational(self, monkeypatch):
        """Line 576: no recommendations → 'All systems operational'."""
        monkeypatch.setattr(config, "CLEANUP_OLD_UPLOADS", False)
        monkeypatch.setattr(config, "AUTO_CLEAR_CACHE", False)
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")

        mock_stats = {
            "total_entries": 5,
            "total_size_mb": 0.1,
            "cache_hits": 3,
            "cache_misses": 2,
            "hit_rate": 60.0,
        }
        with patch.object(utils.cache, "get_statistics", return_value=mock_stats):
            ok, msg = main.mode_system_status()
        assert ok is True


class TestSelectFilesEdgeCases:
    """Test select_files uncovered branches."""

    def test_invalid_selection_index(self, tmp_path, monkeypatch):
        """Lines 627-629: selection index out of range."""
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        f1 = tmp_path / "doc1.txt"
        f1.write_text("hello")

        # First "99" is out of range, then "0" cancels
        inputs = iter(["99", "0"])
        with patch("builtins.input", side_effect=inputs):
            result = main.select_files()
        assert result == []

    def test_value_error_input(self, tmp_path, monkeypatch):
        """Line 635: non-numeric input."""
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        f1 = tmp_path / "doc1.txt"
        f1.write_text("hello")

        inputs = iter(["abc", "0"])
        with patch("builtins.input", side_effect=inputs):
            result = main.select_files()
        assert result == []


class TestInteractiveMenuExpanded:
    """Test interactive_menu uncovered branches."""

    def test_mode_selection_with_files(self, tmp_path, monkeypatch):
        """Lines 711-730: full mode dispatch with file selection."""
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path / "out")
        monkeypatch.setattr(config, "OUTPUT_TXT_DIR", tmp_path / "out_txt")
        (tmp_path / "out").mkdir()
        (tmp_path / "out_txt").mkdir()

        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        # Choose mode 2, select file 1, then exit
        inputs = iter(["2", "1", "", "0"])
        with patch("builtins.input", side_effect=inputs):
            with patch.object(local_converter, "convert_with_markitdown", return_value=(True, "content", None)):
                main.interactive_menu()

    def test_mode_no_valid_files(self, tmp_path, monkeypatch):
        """Lines 717-720: no valid files after filtering."""
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)

        # Create an empty file (0 bytes, will be filtered out)
        empty_file = tmp_path / "empty.txt"
        empty_file.touch()

        inputs = iter(["2", "1", "", "0"])
        with patch("builtins.input", side_effect=inputs):
            main.interactive_menu()

    def test_mode_handler_exception(self, tmp_path, monkeypatch):
        """Lines 736-739: unexpected exception in handler."""
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        def raise_handler(files):
            raise RuntimeError("unexpected boom")

        # Patch the dispatch table entry directly
        original = main.MODE_DISPATCH["2"]
        main.MODE_DISPATCH["2"] = ("markitdown", raise_handler)

        try:
            inputs = iter(["2", "1", "", "0"])
            with patch("builtins.input", side_effect=inputs):
                main.interactive_menu()
        finally:
            main.MODE_DISPATCH["2"] = original

    def test_select_files_returns_empty(self, tmp_path, monkeypatch):
        """Lines 711-712: select_files returns empty → continue."""
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)

        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Choose mode 2, cancel file selection (0), then exit
        inputs = iter(["2", "0", "0"])
        with patch("builtins.input", side_effect=inputs):
            main.interactive_menu()


class TestMainCliExpanded:
    """Test main() CLI uncovered branches."""

    def test_no_valid_files_exits_1(self, tmp_path, monkeypatch):
        """Lines 826-827: no valid files with --mode exits with code 1."""
        monkeypatch.setattr("sys.argv", ["main.py", "--mode", "markitdown", "--no-interactive"])
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)

        # Create an empty file that won't pass validation
        empty = tmp_path / "empty.txt"
        empty.touch()

        with pytest.raises(SystemExit) as exc_info:
            main.main()
        assert exc_info.value.code == 1


class TestModeDocumentQnaExpanded:
    """Test Document QnA mode with mocked interactions."""

    def test_no_client_available(self, tmp_path, monkeypatch):
        """Line 324: client returns None."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")

        with patch.object(mistral_converter, "get_mistral_client", return_value=None):
            ok, msg = main.mode_document_qna([pdf])
        assert ok is False
        assert "not available" in msg

    def test_file_too_large(self, tmp_path, monkeypatch):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"x" * (51 * 1024 * 1024))
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")

        with patch.object(mistral_converter, "get_mistral_client", return_value=MagicMock()):
            ok, msg = main.mode_document_qna([pdf])
        assert ok is False
        assert "too large" in msg.lower() or "50 MB" in msg

    def test_os_error_reading_file(self, tmp_path, monkeypatch):
        """Lines 333-334: OSError when checking file size."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")

        with patch.object(mistral_converter, "get_mistral_client", return_value=MagicMock()):
            with patch.object(Path, "stat", side_effect=OSError("disk error")):
                ok, msg = main.mode_document_qna([pdf])
        assert ok is False
        assert "Cannot read" in msg

    def test_upload_fails(self, tmp_path, monkeypatch):
        """Line 324 area: upload returns None."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_SIGNED_URL_EXPIRY", 1)

        mock_client = MagicMock()
        with patch.object(mistral_converter, "get_mistral_client", return_value=mock_client):
            with patch.object(mistral_converter, "upload_file_for_ocr", return_value=None):
                ok, msg = main.mode_document_qna([pdf])
        assert ok is False
        assert "Failed to upload" in msg

    def test_interactive_session(self, tmp_path, monkeypatch):
        """Lines 416-489: full interactive QnA loop."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_SIGNED_URL_EXPIRY", 1)
        monkeypatch.setattr(config, "MISTRAL_DOCUMENT_QNA_MODEL", "test-model")

        mock_client = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.data.choices = [MagicMock()]
        mock_chunk.data.choices[0].delta.content = "Answer text"

        inputs = iter(["What is this?", "exit"])

        with patch.object(mistral_converter, "get_mistral_client", return_value=mock_client):
            with patch.object(mistral_converter, "upload_file_for_ocr", return_value="https://example.com/doc"):
                with patch.object(mistral_converter, "query_document_stream", return_value=(True, [mock_chunk], None)):
                    with patch("builtins.input", side_effect=inputs):
                        ok, msg = main.mode_document_qna([pdf])

        assert ok is True
        assert "1 question" in msg

    def test_qna_stream_error(self, tmp_path, monkeypatch):
        """Lines 472-476: stream error in QnA."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_SIGNED_URL_EXPIRY", 1)
        monkeypatch.setattr(config, "MISTRAL_DOCUMENT_QNA_MODEL", "test-model")

        mock_client = MagicMock()
        inputs = iter(["What?", "exit"])

        with patch.object(mistral_converter, "get_mistral_client", return_value=mock_client):
            with patch.object(mistral_converter, "upload_file_for_ocr", return_value="https://example.com/doc"):
                with patch.object(mistral_converter, "query_document_stream", return_value=(False, None, "API error")):
                    with patch("builtins.input", side_effect=inputs):
                        ok, msg = main.mode_document_qna([pdf])

        assert ok is True

    def test_qna_keyboard_interrupt(self, tmp_path, monkeypatch):
        """KeyboardInterrupt breaks QnA loop."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_SIGNED_URL_EXPIRY", 1)
        monkeypatch.setattr(config, "MISTRAL_DOCUMENT_QNA_MODEL", "test-model")

        mock_client = MagicMock()

        with patch.object(mistral_converter, "get_mistral_client", return_value=mock_client):
            with patch.object(mistral_converter, "upload_file_for_ocr", return_value="https://example.com/doc"):
                with patch("builtins.input", side_effect=KeyboardInterrupt):
                    ok, msg = main.mode_document_qna([pdf])

        assert ok is True

    def test_qna_stream_iteration_error(self, tmp_path, monkeypatch):
        """Lines 378-379: stream raises exception during iteration."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_SIGNED_URL_EXPIRY", 1)
        monkeypatch.setattr(config, "MISTRAL_DOCUMENT_QNA_MODEL", "test-model")

        mock_client = MagicMock()

        def bad_stream():
            raise ConnectionError("stream broken")
            yield  # pragma: no cover -- unreachable; makes this a generator function

        inputs = iter(["What?", "exit"])

        with patch.object(mistral_converter, "get_mistral_client", return_value=mock_client):
            with patch.object(mistral_converter, "upload_file_for_ocr", return_value="https://example.com/doc"):
                with patch.object(mistral_converter, "query_document_stream", return_value=(True, bad_stream(), None)):
                    with patch("builtins.input", side_effect=inputs):
                        ok, msg = main.mode_document_qna([pdf])

        assert ok is True

    def test_qna_url_refresh_fails(self, tmp_path, monkeypatch):
        """URL refresh fails during loop."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "test_key")
        monkeypatch.setattr(config, "MISTRAL_SIGNED_URL_EXPIRY", 0)  # Force refresh
        monkeypatch.setattr(config, "MISTRAL_DOCUMENT_QNA_MODEL", "test-model")

        mock_client = MagicMock()
        # First call succeeds (initial upload), second call fails (refresh)
        upload_calls = iter(["https://example.com/doc", None])

        inputs = iter(["What?", "exit"])

        with patch.object(mistral_converter, "get_mistral_client", return_value=mock_client):
            with patch.object(mistral_converter, "upload_file_for_ocr", side_effect=upload_calls):
                with patch("builtins.input", side_effect=inputs):
                    ok, msg = main.mode_document_qna([pdf])

        assert ok is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
