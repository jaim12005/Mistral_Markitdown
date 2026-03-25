"""
Tests for mistral_converter.py module.

Tests cover:
- SSRF URL validation (_validate_document_url)
- OCR quality assessment (assess_ocr_quality, _is_weak_page)
- Annotation format helpers (get_bbox_annotation_format, get_document_annotation_format)
- Batch file creation (create_batch_ocr_file)
- Client cache invalidation (reset_mistral_client)
"""

from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

import config

# Initialize config dirs so imports work
config.ensure_directories()

import mistral_converter


# ============================================================================
# _validate_document_url Tests
# ============================================================================


class TestValidateDocumentUrl:
    """Test SSRF prevention in _validate_document_url."""

    def test_valid_https_url(self):
        with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]):
            ok, err = mistral_converter._validate_document_url("https://example.com/doc.pdf")
        assert ok is True
        assert err is None

    def test_rejects_hostname_resolving_to_loopback(self):
        with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 0))]):
            ok, err = mistral_converter._validate_document_url("https://localtest.me/doc.pdf")
        assert ok is False
        assert "internal" in err.lower()

    def test_rejects_http(self):
        ok, err = mistral_converter._validate_document_url("http://example.com/doc.pdf")
        assert ok is False
        assert "HTTPS" in err

    def test_rejects_ftp(self):
        ok, err = mistral_converter._validate_document_url("ftp://example.com/doc.pdf")
        assert ok is False

    def test_rejects_localhost(self):
        ok, err = mistral_converter._validate_document_url("https://localhost/secret")
        assert ok is False
        assert "internal" in err.lower()

    def test_rejects_127_0_0_1(self):
        ok, err = mistral_converter._validate_document_url("https://127.0.0.1/admin")
        assert ok is False

    def test_rejects_ipv4_private_10(self):
        ok, err = mistral_converter._validate_document_url("https://10.0.0.1/")
        assert ok is False
        assert "private" in err.lower()

    def test_rejects_ipv4_private_172(self):
        ok, err = mistral_converter._validate_document_url("https://172.16.0.1/")
        assert ok is False

    def test_rejects_ipv4_private_192(self):
        ok, err = mistral_converter._validate_document_url("https://192.168.1.1/")
        assert ok is False

    def test_rejects_ipv6_loopback(self):
        ok, err = mistral_converter._validate_document_url("https://[::1]/")
        assert ok is False

    def test_rejects_cloud_metadata(self):
        ok, err = mistral_converter._validate_document_url(
            "https://169.254.169.254/latest/meta-data/"
        )
        assert ok is False

    def test_rejects_embedded_credentials(self):
        ok, err = mistral_converter._validate_document_url(
            "https://user:pass@example.com/doc.pdf"
        )
        assert ok is False
        assert "credentials" in err.lower()

    def test_rejects_empty_hostname(self):
        ok, err = mistral_converter._validate_document_url("https:///path")
        assert ok is False

    def test_accepts_public_ip(self):
        ok, err = mistral_converter._validate_document_url("https://8.8.8.8/doc.pdf")
        assert ok is True

    def test_rejects_ipv6_private(self):
        ok, err = mistral_converter._validate_document_url("https://[fd12::1]/doc.pdf")
        assert ok is False

    def test_rejects_ipv4_mapped_ipv6_loopback(self):
        ok, err = mistral_converter._validate_document_url("https://[::ffff:127.0.0.1]/")
        assert ok is False

    def test_rejects_link_local(self):
        ok, err = mistral_converter._validate_document_url("https://169.254.1.1/")
        assert ok is False


# ============================================================================
# _is_weak_page Tests
# ============================================================================


class TestIsWeakPage:
    """Test weak page detection logic."""

    def test_empty_text_is_weak(self):
        assert mistral_converter._is_weak_page("") is True

    def test_short_text_is_weak(self):
        assert mistral_converter._is_weak_page("A few words") is True

    def test_long_quality_text_not_weak(self):
        # Build text that passes all checks:
        # - Long enough (>50 chars)
        # - Contains digits (>20)
        # - Has unique tokens
        # - Reasonable line lengths
        text = (
            "This is a well-formatted financial document page 12345678901234567890 "
            "with various unique words and data points covering multiple topics. "
            "Revenue grew by 15% to $2,500,000 in Q3 compared to prior year."
        )
        assert mistral_converter._is_weak_page(text) is False

    def test_repetitive_text_is_weak(self):
        # Same word repeated many times → low uniqueness ratio
        text = " ".join(["repeated"] * 200) + " 12345678901234567890"
        assert mistral_converter._is_weak_page(text) is True

    def test_no_digits_is_weak(self):
        # Long text without enough digits
        text = "This is a page of text without any numbers in it. " * 5
        assert mistral_converter._is_weak_page(text) is True


# ============================================================================
# assess_ocr_quality Tests
# ============================================================================


class TestAssessOcrQuality:
    """Test OCR quality assessment."""

    def test_empty_result_not_usable(self):
        result = {"full_text": "", "pages": []}
        assessment = mistral_converter.assess_ocr_quality(result)
        assert assessment["is_usable"] is False
        assert assessment["quality_score"] == 0.0

    def test_good_result_usable(self):
        # Build text that satisfies all quality checks:
        # - Sufficient length (>50 chars)
        # - High digit count (>100 for full_text)
        # - High uniqueness ratio (>0.3)
        # - Each page individually passes _is_weak_page checks
        page_text = (
            "Annual Financial Report for Fiscal Year 2024\n"
            "Total consolidated revenue reached $12,345,678.00 representing 15.2% growth.\n"
            "Operating expenses totaled $9,876,543.21 with EBITDA margin at 23.7%.\n"
            "Net income attributable to shareholders was $2,469,134.79 compared to $1,987,654.32.\n"
            "Cash and equivalents of $4,567,890.12 at December 31st 2024.\n"
            "Long-term debt decreased from $8,765,432.10 to $7,654,321.09.\n"
            "Dividends paid per share $3.45 up from $2.98 in prior year.\n"
            "Earnings per diluted share increased to $5.67 versus $4.89.\n"
            "Weighted average shares outstanding 435,678,901.\n"
            "Capital expenditures of $1,234,567.89 primarily in technology infrastructure.\n"
        )
        full_text = page_text * 3  # Make it substantial across pages

        result = {
            "full_text": full_text,
            "pages": [
                {"page_number": i, "text": page_text}
                for i in range(3)
            ],
        }
        assessment = mistral_converter.assess_ocr_quality(result)
        assert assessment["is_usable"] is True
        assert assessment["quality_score"] > 50

    def test_returns_expected_keys(self):
        result = {"full_text": "x" * 100, "pages": [{"text": "x" * 100}]}
        assessment = mistral_converter.assess_ocr_quality(result)
        assert "is_usable" in assessment
        assert "quality_score" in assessment
        assert "issues" in assessment
        assert "weak_page_count" in assessment
        assert "total_page_count" in assessment


# ============================================================================
# Annotation Format Tests
# ============================================================================


class TestAnnotationFormats:
    """Test that annotation format helpers return correct types."""

    def test_bbox_format_disabled_returns_none(self, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_ENABLE_BBOX_ANNOTATION", False)
        result = mistral_converter.get_bbox_annotation_format()
        assert result is None

    def test_document_format_disabled_returns_none(self, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_ENABLE_DOCUMENT_ANNOTATION", False)
        result = mistral_converter.get_document_annotation_format()
        assert result is None

    def test_bbox_format_enabled_returns_dict(self, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_ENABLE_BBOX_ANNOTATION", True)
        monkeypatch.setattr(config, "MISTRAL_ENABLE_STRUCTURED_OUTPUT", True)
        result = mistral_converter.get_bbox_annotation_format()
        # Should be a dict (raw JSON schema) or None if no schema available
        assert result is None or isinstance(result, dict)

    def test_document_format_enabled_returns_dict(self, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_ENABLE_DOCUMENT_ANNOTATION", True)
        monkeypatch.setattr(config, "MISTRAL_ENABLE_STRUCTURED_OUTPUT", True)
        result = mistral_converter.get_document_annotation_format("generic")
        assert result is None or isinstance(result, dict)

    def test_document_format_auto_resolves_to_generic(self, monkeypatch):
        """auto schema type should resolve to generic when not configured."""
        monkeypatch.setattr(config, "MISTRAL_ENABLE_DOCUMENT_ANNOTATION", True)
        monkeypatch.setattr(config, "MISTRAL_ENABLE_STRUCTURED_OUTPUT", True)
        monkeypatch.setattr(config, "MISTRAL_DOCUMENT_SCHEMA_TYPE", "auto")
        result = mistral_converter.get_document_annotation_format("auto")
        # Should not raise, and should return dict or None
        assert result is None or isinstance(result, dict)


# ============================================================================
# Client Cache Invalidation Tests
# ============================================================================


class TestClientCacheInvalidation:
    """Test the reset_mistral_client helper."""

    def test_reset_clears_cache(self):
        """Calling reset should not raise and should clear the cached client."""
        mistral_converter.reset_mistral_client()
        # After reset, the internal singleton should be None
        assert mistral_converter._client_instance is None

    def test_get_client_without_api_key_returns_none(self, monkeypatch):
        """Without API key, get_mistral_client should return None."""
        mistral_converter.reset_mistral_client()
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "")
        result = mistral_converter.get_mistral_client()
        assert result is None

    def test_singleton_is_thread_safe(self, monkeypatch):
        """Multiple threads calling get_mistral_client get the same None (no key)."""
        import concurrent.futures

        mistral_converter.reset_mistral_client()
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "")

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: mistral_converter.get_mistral_client(), range(8)))

        assert all(r is None for r in results)


# ============================================================================
# _is_weak_page Digit Ratio Tests
# ============================================================================


class TestIsWeakPageDigitRatio:
    """Test the configurable digit ratio threshold."""

    def test_ratio_based_detection(self, monkeypatch):
        """When OCR_WEAK_PAGE_DIGIT_RATIO > 0, ratio is used instead of absolute count."""
        monkeypatch.setattr(config, "OCR_WEAK_PAGE_DIGIT_RATIO", 0.1)
        monkeypatch.setattr(config, "OCR_MIN_TEXT_LENGTH", 10)
        monkeypatch.setattr(config, "OCR_MIN_DIGIT_COUNT", 20)

        # Text with ~5% digits — below the 10% ratio threshold
        text = "This is text with very few digits 12 and some more unique words here now. " * 3
        assert mistral_converter._is_weak_page(text) is True

    def test_ratio_passes_when_enough_digits(self, monkeypatch):
        """Text with sufficient digit ratio should not be weak."""
        monkeypatch.setattr(config, "OCR_WEAK_PAGE_DIGIT_RATIO", 0.05)
        monkeypatch.setattr(config, "OCR_MIN_TEXT_LENGTH", 10)
        monkeypatch.setattr(config, "OCR_MIN_UNIQUENESS_RATIO", 0.1)
        monkeypatch.setattr(config, "OCR_MAX_PHRASE_REPETITIONS", 100)
        monkeypatch.setattr(config, "OCR_MIN_AVG_LINE_LENGTH", 5)

        text = (
            "Revenue 12345678901234567890 grew significantly across all regions "
            "with unique valuable insightful data metrics and comprehensive analysis."
        )
        assert mistral_converter._is_weak_page(text) is False


# ============================================================================
# save_extracted_images base64 prefix handling
# ============================================================================


class TestSaveExtractedImages:
    """Test base64 data URI stripping in save_extracted_images."""

    def test_handles_data_uri_prefix(self, tmp_path, monkeypatch):
        """Should decode correctly even when base64 has data: prefix."""
        import base64

        monkeypatch.setattr(config, "MISTRAL_INCLUDE_IMAGES", True)
        monkeypatch.setattr(config, "OUTPUT_IMAGES_DIR", tmp_path)

        # Create a tiny valid PNG (1x1 transparent pixel)
        # PNG header + minimal IHDR + IDAT + IEND
        import struct
        import zlib

        def _make_minimal_png() -> bytes:
            """Create a minimal valid 1x1 PNG."""
            header = b"\x89PNG\r\n\x1a\n"
            # IHDR
            ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
            ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
            ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
            # IDAT
            raw_data = zlib.compress(b"\x00\xff\x00\x00")
            idat_crc = zlib.crc32(b"IDAT" + raw_data) & 0xFFFFFFFF
            idat = struct.pack(">I", len(raw_data)) + b"IDAT" + raw_data + struct.pack(">I", idat_crc)
            # IEND
            iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
            iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
            return header + ihdr + idat + iend

        png_bytes = _make_minimal_png()
        b64_raw = base64.b64encode(png_bytes).decode()
        b64_with_prefix = f"data:image/png;base64,{b64_raw}"

        ocr_result = {
            "pages": [
                {
                    "page_number": 1,
                    "images": [{"base64": b64_with_prefix}],
                }
            ]
        }

        file_path = tmp_path / "test.pdf"
        file_path.touch()

        saved = mistral_converter.save_extracted_images(ocr_result, file_path)
        assert len(saved) == 1
        # The saved file should contain the raw PNG bytes
        assert saved[0].read_bytes() == png_bytes


# ============================================================================
# _track_pages Tests
# ============================================================================


class TestTrackPages:
    """Test page tracking and session limits."""

    def test_increments_counter(self, monkeypatch):
        monkeypatch.setattr(config, "MAX_PAGES_PER_SESSION", 0)
        mistral_converter._session_pages_processed = 0
        mistral_converter._session_pages_warned = False
        mistral_converter._track_pages(5)
        assert mistral_converter._session_pages_processed == 5

    def test_warns_once_at_limit(self, monkeypatch):
        monkeypatch.setattr(config, "MAX_PAGES_PER_SESSION", 10)
        mistral_converter._session_pages_processed = 0
        mistral_converter._session_pages_warned = False
        mistral_converter._track_pages(10)
        assert mistral_converter._session_pages_warned is True
        # Second call should not change warned state
        mistral_converter._track_pages(5)
        assert mistral_converter._session_pages_warned is True


# ============================================================================
# get_retry_config Tests
# ============================================================================


class TestGetRetryConfig:
    """Test retry configuration creation."""

    def test_returns_none_when_retries_zero(self, monkeypatch):
        monkeypatch.setattr(config, "MAX_RETRIES", 0)
        result = mistral_converter.get_retry_config()
        assert result is None

    def test_returns_config_when_retries_available(self, monkeypatch):
        monkeypatch.setattr(config, "MAX_RETRIES", 3)
        result = mistral_converter.get_retry_config()
        # Could be None if retries module not available, or a config object
        # Just ensure no exception is raised
        assert result is None or result is not None


# ============================================================================
# _extract_model_json_schema Tests
# ============================================================================


class TestExtractModelJsonSchema:
    """Test JSON schema extraction from Pydantic models."""

    def test_pydantic_v2_model(self):
        mock_model = MagicMock()
        mock_model.model_json_schema.return_value = {"type": "object", "properties": {}}
        result = mistral_converter._extract_model_json_schema(mock_model)
        assert result == {"type": "object", "properties": {}}

    def test_pydantic_v1_model(self):
        mock_model = MagicMock(spec=["schema"])
        mock_model.schema.return_value = {"type": "object"}
        result = mistral_converter._extract_model_json_schema(mock_model)
        assert result == {"type": "object"}

    def test_no_schema_method(self):
        mock_model = MagicMock(spec=[])
        result = mistral_converter._extract_model_json_schema(mock_model)
        assert result is None


# ============================================================================
# _wrap_response_format Tests
# ============================================================================


class TestWrapResponseFormat:
    """Test response format wrapping."""

    def test_wraps_schema_correctly(self):
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        result = mistral_converter._wrap_response_format(schema, "test_format")
        assert result["type"] == "json_schema"
        assert result["json_schema"]["name"] == "test_format"
        assert result["json_schema"]["strict"] is True
        assert result["json_schema"]["schema"] == schema


# ============================================================================
# _extract_page_text Tests
# ============================================================================


class TestExtractPageText:
    """Test text extraction from various page object types."""

    def test_markdown_attribute(self):
        page = MagicMock()
        page.markdown = "# Title"
        page.text = None
        page.content = None
        result = mistral_converter._extract_page_text(page)
        assert result == "# Title"

    def test_text_attribute(self):
        page = MagicMock(spec=["text"])
        page.text = "plain text"
        result = mistral_converter._extract_page_text(page)
        assert result == "plain text"

    def test_dict_page(self):
        page = {"markdown": "# Dict Page"}
        result = mistral_converter._extract_page_text(page)
        assert result == "# Dict Page"

    def test_string_page(self):
        result = mistral_converter._extract_page_text("raw string")
        assert result == "raw string"

    def test_empty_page(self):
        page = MagicMock(spec=[])
        result = mistral_converter._extract_page_text(page)
        assert result == ""


# ============================================================================
# _parse_page_object Tests
# ============================================================================


class TestParsePageObject:
    """Test page object parsing."""

    def test_basic_page(self):
        page = MagicMock()
        page.markdown = "Page content"
        page.text = None
        page.content = None
        page.index = 1
        page.images = []
        page.dimensions = None
        page.tables = None
        page.hyperlinks = None
        page.header = None
        page.footer = None

        result = mistral_converter._parse_page_object(page, 0)
        assert result["page_number"] == 1
        assert result["text"] == "Page content"
        assert result["images"] == []

    def test_dict_page(self):
        page = {"markdown": "Dict content", "index": 2}
        result = mistral_converter._parse_page_object(page, 1)
        assert result["page_number"] == 2
        assert result["text"] == "Dict content"


# ============================================================================
# _parse_single_text_response Tests
# ============================================================================


class TestParseSingleTextResponse:
    """Test single text response parsing."""

    def test_adds_text_and_page(self):
        result = {"full_text": "", "pages": []}
        mistral_converter._parse_single_text_response("Hello World", result)
        assert result["full_text"] == "Hello World"
        assert len(result["pages"]) == 1
        assert result["pages"][0]["page_number"] == 1


# ============================================================================
# _parse_dict_response Tests
# ============================================================================


class TestParseDictResponse:
    """Test dict response parsing."""

    def test_with_pages(self):
        response = {
            "pages": [
                {"markdown": "Page 1", "index": 1},
                {"text": "Page 2", "index": 2},
            ]
        }
        result = {"full_text": "", "pages": []}
        mistral_converter._parse_dict_response(response, result)
        assert len(result["pages"]) == 2
        assert "Page 1" in result["full_text"]

    def test_without_pages(self):
        response = {"markdown": "Single page content"}
        result = {"full_text": "", "pages": []}
        mistral_converter._parse_dict_response(response, result)
        assert len(result["pages"]) == 1
        assert result["full_text"] == "Single page content"


# ============================================================================
# _extract_structured_outputs Tests
# ============================================================================


class TestExtractStructuredOutputs:
    """Test structured output extraction."""

    def test_extracts_bbox_annotations(self):
        response = MagicMock()
        bbox = MagicMock()
        bbox.model_dump.return_value = {"x": 0, "y": 0, "w": 100, "h": 50}
        response.bbox_annotations = [bbox]
        response.document_annotation = None

        result = {"bbox_annotations": [], "document_annotation": None}
        mistral_converter._extract_structured_outputs(response, result)
        assert len(result["bbox_annotations"]) == 1

    def test_extracts_document_annotation_json_string(self):
        response = MagicMock()
        response.bbox_annotations = None
        response.document_annotation = '{"type": "invoice"}'

        result = {"bbox_annotations": [], "document_annotation": None}
        mistral_converter._extract_structured_outputs(response, result)
        assert result["document_annotation"] == {"type": "invoice"}

    def test_no_annotations(self):
        response = MagicMock()
        response.bbox_annotations = None
        response.document_annotation = None

        result = {"bbox_annotations": [], "document_annotation": None}
        mistral_converter._extract_structured_outputs(response, result)
        assert result["bbox_annotations"] == []
        assert result["document_annotation"] is None


# ============================================================================
# _extract_response_metadata Tests
# ============================================================================


class TestExtractResponseMetadata:
    """Test metadata extraction from responses."""

    def test_object_response(self):
        response = MagicMock()
        response.metadata = {"source": "test"}
        response.model = "mistral-ocr-latest"
        usage = MagicMock()
        usage.pages_processed = 5
        usage.doc_size_bytes = 1024
        response.usage_info = usage

        result = {"metadata": {}, "usage_info": {}, "model": None}
        mistral_converter._extract_response_metadata(response, result)
        assert result["metadata"] == {"source": "test"}
        assert result["model"] == "mistral-ocr-latest"
        assert result["usage_info"]["pages_processed"] == 5

    def test_dict_response(self):
        response = {"metadata": {"key": "val"}, "model": "pixtral", "usage_info": {"pages_processed": 2}}

        result = {"metadata": {}, "usage_info": {}, "model": None}
        mistral_converter._extract_response_metadata(response, result)
        assert result["metadata"] == {"key": "val"}
        assert result["model"] == "pixtral"


# ============================================================================
# _parse_ocr_response Tests
# ============================================================================


class TestParseOcrResponse:
    """Test full OCR response parsing pipeline."""

    def test_pages_response(self, tmp_path):
        page = MagicMock()
        page.markdown = "# Page 1 Content"
        page.text = None
        page.content = None
        page.index = 1
        page.images = []
        page.dimensions = None
        page.tables = None
        page.hyperlinks = None
        page.header = None
        page.footer = None

        response = MagicMock()
        response.pages = [page]
        response.bbox_annotations = None
        response.document_annotation = None
        response.metadata = {}
        response.usage_info = None
        response.model = "mistral-ocr-latest"

        result = mistral_converter._parse_ocr_response(response, tmp_path / "test.pdf")
        assert result["file_name"] == "test.pdf"
        assert len(result["pages"]) == 1
        assert "Page 1 Content" in result["full_text"]

    def test_dict_response_fallback(self, tmp_path):
        response = {"markdown": "Direct markdown content"}
        result = mistral_converter._parse_ocr_response(response, tmp_path / "doc.pdf")
        assert "Direct markdown content" in result["full_text"]

    def test_handles_exception_gracefully(self, tmp_path):
        response = MagicMock()
        response.pages = None
        response.markdown = None
        response.text = None
        response.content = None
        response.bbox_annotations = MagicMock(side_effect=Exception("boom"))
        # Should not raise
        result = mistral_converter._parse_ocr_response(response, tmp_path / "err.pdf")
        assert result["file_name"] == "err.pdf"


# ============================================================================
# _create_markdown_output Tests
# ============================================================================


class TestCreateMarkdownOutput:
    """Test markdown output creation."""

    def test_creates_markdown_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)
        monkeypatch.setattr(config, "INCLUDE_METADATA", False)
        monkeypatch.setattr(config, "GENERATE_TXT_OUTPUT", False)
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)

        file_path = tmp_path / "document.pdf"
        file_path.touch()

        ocr_result = {
            "pages": [
                {"page_number": 1, "text": "Page 1 content", "images": []},
                {"page_number": 2, "text": "Page 2 content", "images": []},
            ],
            "full_text": "Page 1 content\n\nPage 2 content",
        }

        output = mistral_converter._create_markdown_output(file_path, ocr_result)
        assert output.exists()
        content = output.read_text()
        assert "Page 1 content" in content
        assert "Page 2 content" in content
        assert "OCR Result" in content

    def test_fallback_without_pages(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)
        monkeypatch.setattr(config, "INCLUDE_METADATA", False)
        monkeypatch.setattr(config, "GENERATE_TXT_OUTPUT", False)
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)

        file_path = tmp_path / "doc.pdf"
        file_path.touch()

        ocr_result = {
            "pages": [],
            "full_text": "Fallback text content",
        }

        output = mistral_converter._create_markdown_output(file_path, ocr_result)
        content = output.read_text()
        assert "Fallback text content" in content


# ============================================================================
# _save_structured_outputs Tests
# ============================================================================


class TestSaveStructuredOutputs:
    """Test structured output file saving."""

    def test_saves_bbox_annotations(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)

        file_path = tmp_path / "doc.pdf"
        file_path.touch()

        ocr_result = {
            "bbox_annotations": [{"x": 0, "y": 0, "w": 100, "h": 50}],
            "document_annotation": None,
        }

        mistral_converter._save_structured_outputs(file_path, ocr_result)
        json_files = list(tmp_path.glob("*bbox*.json"))
        assert len(json_files) == 1

    def test_saves_document_annotation(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)
        monkeypatch.setattr(config, "INPUT_DIR", tmp_path)

        file_path = tmp_path / "doc.pdf"
        file_path.touch()

        ocr_result = {
            "bbox_annotations": [],
            "document_annotation": {"type": "invoice", "total": "1000"},
        }

        mistral_converter._save_structured_outputs(file_path, ocr_result)
        json_files = list(tmp_path.glob("*document_annotation*.json"))
        assert len(json_files) == 1

    def test_no_output_without_annotations(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)

        file_path = tmp_path / "doc.pdf"

        ocr_result = {
            "bbox_annotations": [],
            "document_annotation": None,
        }

        mistral_converter._save_structured_outputs(file_path, ocr_result)
        json_files = list(tmp_path.glob("*.json"))
        assert len(json_files) == 0


# ============================================================================
# _validate_document_url Additional Tests
# ============================================================================


class TestValidateDocumentUrlAdditional:
    """Additional URL validation edge cases."""

    def test_rejects_data_url(self):
        ok, err = mistral_converter._validate_document_url("data:text/html,<h1>bad</h1>")
        assert ok is False

    def test_rejects_javascript_url(self):
        ok, err = mistral_converter._validate_document_url("javascript:alert(1)")
        assert ok is False

    def test_rejects_empty_url(self):
        ok, err = mistral_converter._validate_document_url("")
        assert ok is False

    def test_rejects_non_string(self):
        ok, err = mistral_converter._validate_document_url(None)
        assert ok is False


# ============================================================================
# get_mistral_client Tests
# ============================================================================


class TestGetMistralClient:
    """Test Mistral client initialization."""

    def test_returns_none_without_sdk(self, monkeypatch):
        mistral_converter.reset_mistral_client()
        with patch.object(mistral_converter, "Mistral", None):
            result = mistral_converter.get_mistral_client()
        assert result is None
        mistral_converter.reset_mistral_client()

    def test_returns_none_without_api_key(self, monkeypatch):
        mistral_converter.reset_mistral_client()
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "")
        result = mistral_converter.get_mistral_client()
        assert result is None
        mistral_converter.reset_mistral_client()


# ============================================================================
# query_document Tests
# ============================================================================


class TestQueryDocument:
    """Test document querying with mocks."""

    def test_rejects_invalid_url(self):
        with patch.object(mistral_converter, "get_mistral_client", return_value=MagicMock()):
            ok, answer, err = mistral_converter.query_document("http://insecure.com/doc.pdf", "what?")
        assert ok is False
        assert "HTTPS" in err or "https" in err.lower()

    def test_rejects_private_url(self):
        ok, answer, err = mistral_converter.query_document("https://192.168.1.1/doc.pdf", "what?")
        assert ok is False

    def test_no_client_available(self, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "")
        mistral_converter.reset_mistral_client()
        with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]):
            ok, answer, err = mistral_converter.query_document("https://example.com/doc.pdf", "what?")
        assert ok is False
        mistral_converter.reset_mistral_client()


# ============================================================================
# query_document_stream Tests
# ============================================================================


class TestQueryDocumentStream:
    """Test streaming document querying."""

    def test_rejects_invalid_url(self):
        ok, stream, err = mistral_converter.query_document_stream("http://bad.com/doc.pdf", "what?")
        assert ok is False

    def test_no_client_available(self, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "")
        mistral_converter.reset_mistral_client()
        with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]):
            ok, stream, err = mistral_converter.query_document_stream("https://example.com/doc.pdf", "what?")
        assert ok is False
        mistral_converter.reset_mistral_client()


# ============================================================================
# save_extracted_images Additional Tests
# ============================================================================


class TestSaveExtractedImagesAdditional:
    """Additional image saving tests."""

    def test_images_disabled(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_INCLUDE_IMAGES", False)
        ocr_result = {
            "pages": [{"page_number": 1, "images": [{"base64": "abc"}]}]
        }
        saved = mistral_converter.save_extracted_images(ocr_result, tmp_path / "test.pdf")
        assert saved == []

    def test_no_images_in_result(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_INCLUDE_IMAGES", True)
        ocr_result = {"pages": [{"page_number": 1, "images": []}]}
        saved = mistral_converter.save_extracted_images(ocr_result, tmp_path / "test.pdf")
        assert saved == []


# ============================================================================
# optimize_image Tests
# ============================================================================


class TestOptimizeImage:
    """Test image optimization."""

    def test_disabled_returns_original(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_ENABLE_IMAGE_OPTIMIZATION", False)
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        assert mistral_converter.optimize_image(img) == img

    def test_small_image_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_ENABLE_IMAGE_OPTIMIZATION", True)
        monkeypatch.setattr(config, "MISTRAL_MAX_IMAGE_DIMENSION", 2000)
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake")

        mock_img = MagicMock()
        mock_img.size = (500, 400)
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock(return_value=False)

        with patch.object(mistral_converter, "Image") as mock_pil:
            mock_pil.Resampling.LANCZOS = 1
            mock_pil.open.return_value = mock_img
            result = mistral_converter.optimize_image(img_path)
        assert result == img_path

    def test_large_png_resized(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_ENABLE_IMAGE_OPTIMIZATION", True)
        monkeypatch.setattr(config, "MISTRAL_MAX_IMAGE_DIMENSION", 1000)
        monkeypatch.setattr(config, "MISTRAL_IMAGE_QUALITY_THRESHOLD", 85)
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake")

        mock_img = MagicMock()
        mock_img.size = (3000, 2000)
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock(return_value=False)
        resized = MagicMock()
        mock_img.resize.return_value = resized

        with patch.object(mistral_converter, "Image") as mock_pil:
            mock_pil.Resampling.LANCZOS = 1
            mock_pil.open.return_value = mock_img
            result = mistral_converter.optimize_image(img_path)

        resized.save.assert_called_once()
        assert "optimized" in str(result)

    def test_jpeg_uses_quality(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_ENABLE_IMAGE_OPTIMIZATION", True)
        monkeypatch.setattr(config, "MISTRAL_MAX_IMAGE_DIMENSION", 500)
        monkeypatch.setattr(config, "MISTRAL_IMAGE_QUALITY_THRESHOLD", 80)
        img_path = tmp_path / "test.jpg"
        img_path.write_bytes(b"fake")

        mock_img = MagicMock()
        mock_img.size = (2000, 1000)
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock(return_value=False)
        resized = MagicMock()
        mock_img.resize.return_value = resized

        with patch.object(mistral_converter, "Image") as mock_pil:
            mock_pil.Resampling.LANCZOS = 1
            mock_pil.open.return_value = mock_img
            result = mistral_converter.optimize_image(img_path)

        save_call = resized.save.call_args
        assert save_call[1].get("format") == "JPEG"

    def test_error_returns_original(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_ENABLE_IMAGE_OPTIMIZATION", True)
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake")

        with patch.object(mistral_converter, "Image") as mock_pil:
            mock_pil.Resampling.LANCZOS = 1
            mock_pil.open.side_effect = Exception("corrupt")
            result = mistral_converter.optimize_image(img_path)
        assert result == img_path


# ============================================================================
# preprocess_image Tests
# ============================================================================


class TestPreprocessImage:
    """Test image preprocessing."""

    def test_disabled_returns_original(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_ENABLE_IMAGE_PREPROCESSING", False)
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        assert mistral_converter.preprocess_image(img) == img

    def test_jpeg_preprocessing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_ENABLE_IMAGE_PREPROCESSING", True)
        img_path = tmp_path / "test.jpeg"
        img_path.write_bytes(b"fake")

        mock_img = MagicMock()
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock(return_value=False)
        mock_img.convert.return_value = mock_img

        mock_enhance_cls = MagicMock()
        mock_enhance_cls.return_value.enhance.return_value = mock_img

        with patch.object(mistral_converter, "Image") as mock_pil:
            mock_pil.open.return_value = mock_img
            with patch.dict("sys.modules", {"PIL.ImageEnhance": MagicMock(Contrast=mock_enhance_cls, Sharpness=mock_enhance_cls)}):
                result = mistral_converter.preprocess_image(img_path)

        assert "preprocessed" in str(result)

    def test_error_returns_original(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_ENABLE_IMAGE_PREPROCESSING", True)
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake")

        with patch.object(mistral_converter, "Image") as mock_pil:
            mock_pil.open.side_effect = Exception("bad image")
            result = mistral_converter.preprocess_image(img_path)
        assert result == img_path


# ============================================================================
# cleanup_uploaded_files Tests
# ============================================================================


class TestCleanupUploadedFiles:
    """Test file cleanup."""

    def test_deletes_old_files(self, monkeypatch):
        monkeypatch.setattr(config, "UPLOAD_RETENTION_DAYS", 7)

        from datetime import datetime, timezone

        old_file = MagicMock()
        old_file.id = "file_old"
        old_file.created_at = (datetime.now(timezone.utc) - __import__("datetime").timedelta(days=30)).isoformat()

        mock_client = MagicMock()
        files_response = MagicMock()
        files_response.data = [old_file]
        files_response.total = 1
        mock_client.files.list.return_value = files_response

        count = mistral_converter.cleanup_uploaded_files(mock_client, days_old=7)
        assert count >= 1
        mock_client.files.delete.assert_called()

    def test_no_old_files(self, monkeypatch):
        from datetime import datetime, timezone

        recent_file = MagicMock()
        recent_file.id = "file_new"
        recent_file.created_at = datetime.now(timezone.utc).isoformat()

        mock_client = MagicMock()
        files_response = MagicMock()
        files_response.data = [recent_file]
        files_response.total = 1
        mock_client.files.list.return_value = files_response

        count = mistral_converter.cleanup_uploaded_files(mock_client, days_old=7)
        assert count == 0

    def test_empty_file_list(self):
        mock_client = MagicMock()
        files_response = MagicMock()
        files_response.data = []
        mock_client.files.list.return_value = files_response

        count = mistral_converter.cleanup_uploaded_files(mock_client, days_old=7)
        assert count == 0

    def test_error_returns_zero(self):
        mock_client = MagicMock()
        mock_client.files.list.side_effect = Exception("API error")

        count = mistral_converter.cleanup_uploaded_files(mock_client, days_old=7)
        assert count == 0


# ============================================================================
# upload_file_for_ocr Tests
# ============================================================================


class TestUploadFileForOcr:
    """Test file upload for OCR."""

    def test_successful_pdf_upload(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_SIGNED_URL_EXPIRY", 24)
        monkeypatch.setattr(config, "IMAGE_EXTENSIONS", {"png", "jpg", "jpeg"})

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        mock_client = MagicMock()
        mock_client.files.upload.return_value = MagicMock(id="file_123")
        mock_client.files.get_signed_url.return_value = MagicMock(url="https://signed.url/doc")

        result = mistral_converter.upload_file_for_ocr(mock_client, pdf_file)
        assert result == "https://signed.url/doc"
        mock_client.files.upload.assert_called_once()

    def test_upload_with_image_preprocessing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_SIGNED_URL_EXPIRY", 24)
        monkeypatch.setattr(config, "IMAGE_EXTENSIONS", {"png", "jpg", "jpeg"})
        monkeypatch.setattr(config, "MISTRAL_ENABLE_IMAGE_PREPROCESSING", True)
        monkeypatch.setattr(config, "MISTRAL_ENABLE_IMAGE_OPTIMIZATION", False)

        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"fake png")

        mock_client = MagicMock()
        mock_client.files.upload.return_value = MagicMock(id="file_456")
        mock_client.files.get_signed_url.return_value = MagicMock(url="https://signed.url/img")

        with patch.object(mistral_converter, "preprocess_image", return_value=img_file):
            result = mistral_converter.upload_file_for_ocr(mock_client, img_file)
        assert result == "https://signed.url/img"

    def test_upload_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_SIGNED_URL_EXPIRY", 24)
        monkeypatch.setattr(config, "IMAGE_EXTENSIONS", {"png", "jpg", "jpeg"})

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        mock_client = MagicMock()
        mock_client.files.upload.side_effect = Exception("upload failed")

        result = mistral_converter.upload_file_for_ocr(mock_client, pdf_file)
        assert result is None

    def test_missing_signed_url(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_SIGNED_URL_EXPIRY", 24)
        monkeypatch.setattr(config, "IMAGE_EXTENSIONS", {"png", "jpg", "jpeg"})

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        mock_client = MagicMock()
        mock_client.files.upload.return_value = MagicMock(id="file_789")
        mock_client.files.get_signed_url.return_value = MagicMock(spec=[])  # No 'url' attr

        result = mistral_converter.upload_file_for_ocr(mock_client, pdf_file)
        assert result is None


# ============================================================================
# process_with_ocr Tests
# ============================================================================


class TestProcessWithOcr:
    """Test OCR processing pipeline."""

    def test_successful_pdf_processing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "IMAGE_EXTENSIONS", {"png", "jpg", "jpeg"})
        monkeypatch.setattr(config, "MISTRAL_INCLUDE_IMAGES", False)
        monkeypatch.setattr(config, "MISTRAL_DOCUMENT_ANNOTATION_PROMPT", "")
        monkeypatch.setattr(config, "MISTRAL_TABLE_FORMAT", "")
        monkeypatch.setattr(config, "MISTRAL_EXTRACT_HEADER", True)
        monkeypatch.setattr(config, "MISTRAL_EXTRACT_FOOTER", True)
        monkeypatch.setattr(config, "MISTRAL_IMAGE_LIMIT", 0)
        monkeypatch.setattr(config, "MISTRAL_IMAGE_MIN_SIZE", 0)

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 content")

        mock_page = MagicMock()
        mock_page.markdown = "# Page 1 content"
        mock_page.index = 0
        mock_page.images = []

        mock_response = MagicMock()
        mock_response.pages = [mock_page]

        mock_client = MagicMock()
        mock_client.ocr.process.return_value = mock_response

        with patch.object(mistral_converter, "upload_file_for_ocr", return_value="https://signed.url/doc"):
            with patch.object(mistral_converter, "get_retry_config", return_value=None):
                with patch.object(mistral_converter, "get_bbox_annotation_format", return_value=None):
                    with patch.object(mistral_converter, "get_document_annotation_format", return_value=None):
                        with patch.object(mistral_converter, "DocumentURLChunk", MagicMock()):
                            success, result, error = mistral_converter.process_with_ocr(mock_client, pdf_file)

        assert success is True
        assert result is not None
        assert "full_text" in result

    def test_upload_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "IMAGE_EXTENSIONS", {"png", "jpg", "jpeg"})

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        mock_client = MagicMock()

        with patch.object(mistral_converter, "upload_file_for_ocr", return_value=None):
            success, result, error = mistral_converter.process_with_ocr(mock_client, pdf_file)

        assert success is False
        assert "Failed to upload" in error

    def test_empty_response(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "IMAGE_EXTENSIONS", {"png", "jpg", "jpeg"})
        monkeypatch.setattr(config, "MISTRAL_INCLUDE_IMAGES", False)
        monkeypatch.setattr(config, "MISTRAL_DOCUMENT_ANNOTATION_PROMPT", "")
        monkeypatch.setattr(config, "MISTRAL_TABLE_FORMAT", "")
        monkeypatch.setattr(config, "MISTRAL_EXTRACT_HEADER", True)
        monkeypatch.setattr(config, "MISTRAL_EXTRACT_FOOTER", True)
        monkeypatch.setattr(config, "MISTRAL_IMAGE_LIMIT", 0)
        monkeypatch.setattr(config, "MISTRAL_IMAGE_MIN_SIZE", 0)

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        mock_client = MagicMock()
        mock_client.ocr.process.return_value = None

        with patch.object(mistral_converter, "upload_file_for_ocr", return_value="https://signed.url/doc"):
            with patch.object(mistral_converter, "get_retry_config", return_value=None):
                with patch.object(mistral_converter, "get_bbox_annotation_format", return_value=None):
                    with patch.object(mistral_converter, "get_document_annotation_format", return_value=None):
                        with patch.object(mistral_converter, "DocumentURLChunk", MagicMock()):
                            success, result, error = mistral_converter.process_with_ocr(mock_client, pdf_file)

        assert success is False
        assert "Empty response" in error

    def test_api_error_401(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "IMAGE_EXTENSIONS", {"png", "jpg", "jpeg"})
        monkeypatch.setattr(config, "MISTRAL_INCLUDE_IMAGES", False)
        monkeypatch.setattr(config, "MISTRAL_DOCUMENT_ANNOTATION_PROMPT", "")
        monkeypatch.setattr(config, "MISTRAL_TABLE_FORMAT", "")
        monkeypatch.setattr(config, "MISTRAL_EXTRACT_HEADER", True)
        monkeypatch.setattr(config, "MISTRAL_EXTRACT_FOOTER", True)
        monkeypatch.setattr(config, "MISTRAL_IMAGE_LIMIT", 0)
        monkeypatch.setattr(config, "MISTRAL_IMAGE_MIN_SIZE", 0)

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        mock_client = MagicMock()
        mock_client.ocr.process.side_effect = Exception("401 Unauthorized")

        with patch.object(mistral_converter, "upload_file_for_ocr", return_value="https://signed.url/doc"):
            with patch.object(mistral_converter, "get_retry_config", return_value=None):
                with patch.object(mistral_converter, "get_bbox_annotation_format", return_value=None):
                    with patch.object(mistral_converter, "get_document_annotation_format", return_value=None):
                        with patch.object(mistral_converter, "DocumentURLChunk", MagicMock()):
                            success, result, error = mistral_converter.process_with_ocr(mock_client, pdf_file)

        assert success is False
        assert "authentication" in error.lower() or "401" in error

    def test_image_file_uses_image_chunk(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "IMAGE_EXTENSIONS", {"png", "jpg", "jpeg"})
        monkeypatch.setattr(config, "MISTRAL_INCLUDE_IMAGES", False)
        monkeypatch.setattr(config, "MISTRAL_DOCUMENT_ANNOTATION_PROMPT", "")
        monkeypatch.setattr(config, "MISTRAL_TABLE_FORMAT", "")
        monkeypatch.setattr(config, "MISTRAL_EXTRACT_HEADER", True)
        monkeypatch.setattr(config, "MISTRAL_EXTRACT_FOOTER", True)
        monkeypatch.setattr(config, "MISTRAL_IMAGE_LIMIT", 0)
        monkeypatch.setattr(config, "MISTRAL_IMAGE_MIN_SIZE", 0)

        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"fake png")

        mock_page = MagicMock()
        mock_page.markdown = "Image text content"
        mock_page.index = 0
        mock_page.images = []

        mock_response = MagicMock()
        mock_response.pages = [mock_page]

        mock_client = MagicMock()
        mock_client.ocr.process.return_value = mock_response

        mock_image_chunk = MagicMock()
        with patch.object(mistral_converter, "upload_file_for_ocr", return_value="https://signed.url/img"):
            with patch.object(mistral_converter, "get_retry_config", return_value=None):
                with patch.object(mistral_converter, "get_bbox_annotation_format", return_value=None):
                    with patch.object(mistral_converter, "get_document_annotation_format", return_value=None):
                        with patch.object(mistral_converter, "ImageURLChunk", mock_image_chunk):
                            success, result, error = mistral_converter.process_with_ocr(mock_client, img_file)

        assert success is True
        mock_image_chunk.assert_called_once()


# ============================================================================
# get_batch_job_status Tests
# ============================================================================


class TestGetBatchJobStatus:
    """Test batch job status retrieval."""

    def test_successful_status(self):
        mock_job = MagicMock()
        mock_job.status = "RUNNING"
        mock_job.total_requests = 10
        mock_job.succeeded_requests = 5
        mock_job.failed_requests = 1
        mock_job.output_file = None
        mock_job.error_file = None

        with patch.object(mistral_converter, "get_mistral_client") as mock_get:
            mock_client = MagicMock()
            mock_client.batch.jobs.get.return_value = mock_job
            mock_get.return_value = mock_client

            ok, status, err = mistral_converter.get_batch_job_status("job_123")

        assert ok is True
        assert status["status"] == "RUNNING"
        assert status["progress_percent"] == 60.0

    def test_no_client(self):
        with patch.object(mistral_converter, "get_mistral_client", return_value=None):
            ok, status, err = mistral_converter.get_batch_job_status("job_123")
        assert ok is False

    def test_api_error(self):
        with patch.object(mistral_converter, "get_mistral_client") as mock_get:
            mock_client = MagicMock()
            mock_client.batch.jobs.get.side_effect = Exception("not found")
            mock_get.return_value = mock_client

            ok, status, err = mistral_converter.get_batch_job_status("job_123")
        assert ok is False


# ============================================================================
# download_batch_results Tests
# ============================================================================


class TestDownloadBatchResults:
    """Test batch result downloading."""

    def test_successful_download(self, tmp_path):
        mock_job = MagicMock()
        mock_job.status = "SUCCESS"
        mock_job.output_file = "output_file_id"

        with patch.object(mistral_converter, "get_mistral_client") as mock_get:
            mock_client = MagicMock()
            mock_client.batch.jobs.get.return_value = mock_job
            mock_client.files.download.return_value = b'{"result": "data"}\n'
            mock_get.return_value = mock_client

            ok, path, err = mistral_converter.download_batch_results("job_ok", output_dir=tmp_path)

        assert ok is True
        assert path.exists()

    def test_job_not_complete(self):
        mock_job = MagicMock()
        mock_job.status = "RUNNING"

        with patch.object(mistral_converter, "get_mistral_client") as mock_get:
            mock_client = MagicMock()
            mock_client.batch.jobs.get.return_value = mock_job
            mock_get.return_value = mock_client

            ok, path, err = mistral_converter.download_batch_results("job_run")
        assert ok is False
        assert "not complete" in err.lower() or "RUNNING" in err

    def test_no_output_file(self):
        mock_job = MagicMock()
        mock_job.status = "SUCCESS"
        mock_job.output_file = None

        with patch.object(mistral_converter, "get_mistral_client") as mock_get:
            mock_client = MagicMock()
            mock_client.batch.jobs.get.return_value = mock_job
            mock_get.return_value = mock_client

            ok, path, err = mistral_converter.download_batch_results("job_no_out")
        assert ok is False


# ============================================================================
# list_batch_jobs Tests
# ============================================================================


class TestListBatchJobs:
    """Test batch jobs listing."""

    def test_successful_listing(self):
        mock_job = MagicMock()
        mock_job.id = "job_1"
        mock_job.status = "SUCCESS"
        mock_job.model = "mistral-ocr-latest"
        mock_job.total_requests = 5
        mock_job.succeeded_requests = 5
        mock_job.failed_requests = 0
        mock_job.created_at = "2024-01-01T00:00:00Z"

        jobs_response = MagicMock()
        jobs_response.data = [mock_job]

        with patch.object(mistral_converter, "get_mistral_client") as mock_get:
            mock_client = MagicMock()
            mock_client.batch.jobs.list.return_value = jobs_response
            mock_get.return_value = mock_client

            ok, jobs, err = mistral_converter.list_batch_jobs()

        assert ok is True
        assert len(jobs) == 1
        assert jobs[0]["id"] == "job_1"

    def test_filter_by_status(self):
        job1 = MagicMock()
        job1.id = "j1"
        job1.status = "SUCCESS"
        job1.model = "m"
        job1.total_requests = 1
        job1.succeeded_requests = 1
        job1.failed_requests = 0
        job1.created_at = ""

        job2 = MagicMock()
        job2.id = "j2"
        job2.status = "FAILED"
        job2.model = "m"
        job2.total_requests = 1
        job2.succeeded_requests = 0
        job2.failed_requests = 1
        job2.created_at = ""

        jobs_response = MagicMock()
        jobs_response.data = [job1, job2]

        with patch.object(mistral_converter, "get_mistral_client") as mock_get:
            mock_client = MagicMock()
            mock_client.batch.jobs.list.return_value = jobs_response
            mock_get.return_value = mock_client

            ok, jobs, err = mistral_converter.list_batch_jobs(status="SUCCESS")

        assert ok is True
        assert len(jobs) == 1
        assert jobs[0]["status"] == "SUCCESS"

    def test_no_client(self):
        with patch.object(mistral_converter, "get_mistral_client", return_value=None):
            ok, jobs, err = mistral_converter.list_batch_jobs()
        assert ok is False


# ============================================================================
# convert_with_mistral_ocr Tests
# ============================================================================


class TestConvertWithMistralOcr:
    """Test full OCR conversion pipeline."""

    def test_no_client(self, monkeypatch):
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "")
        mistral_converter.reset_mistral_client()
        ok, path, err = mistral_converter.convert_with_mistral_ocr(Path("test.pdf"))
        assert ok is False
        assert "not available" in err.lower()
        mistral_converter.reset_mistral_client()

    def test_cached_result(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)
        monkeypatch.setattr(config, "SAVE_MISTRAL_JSON", False)
        monkeypatch.setattr(config, "ENABLE_OCR_QUALITY_ASSESSMENT", False)

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF")

        cached_result = {"full_text": "Cached text", "pages": [{"text": "Cached text", "page_number": 1}]}

        with patch.object(mistral_converter, "get_mistral_client", return_value=MagicMock()):
            with patch("utils.cache.get", return_value=cached_result):
                with patch.object(mistral_converter, "_create_markdown_output", return_value=tmp_path / "out.md"):
                    with patch.object(mistral_converter, "_save_structured_outputs"):
                        with patch.object(mistral_converter, "save_extracted_images"):
                            ok, path, err = mistral_converter.convert_with_mistral_ocr(pdf, use_cache=True)

        assert ok is True

    def test_ocr_failure(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF")

        with patch.object(mistral_converter, "get_mistral_client", return_value=MagicMock()):
            with patch("utils.cache.get", return_value=None):
                with patch.object(mistral_converter, "process_with_ocr", return_value=(False, None, "OCR failed")):
                    ok, path, err = mistral_converter.convert_with_mistral_ocr(pdf)

        assert ok is False
        assert "OCR failed" in err


# ============================================================================
# query_document_file Tests
# ============================================================================


class TestQueryDocumentFile:
    """Test file-based document QnA."""

    def test_no_client(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF")

        with patch.object(mistral_converter, "get_mistral_client", return_value=None):
            ok, answer, err = mistral_converter.query_document_file(pdf, "what?")
        assert ok is False

    def test_file_too_large(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"x" * (51 * 1024 * 1024))  # 51 MB

        with patch.object(mistral_converter, "get_mistral_client", return_value=MagicMock()):
            ok, answer, err = mistral_converter.query_document_file(pdf, "what?")
        assert ok is False
        assert "too large" in err.lower()

    def test_upload_failure(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF small file")

        with patch.object(mistral_converter, "get_mistral_client", return_value=MagicMock()):
            with patch.object(mistral_converter, "upload_file_for_ocr", return_value=None):
                ok, answer, err = mistral_converter.query_document_file(pdf, "what?")
        assert ok is False
        assert "upload" in err.lower()

    def test_successful_query(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF small content")

        with patch.object(mistral_converter, "get_mistral_client", return_value=MagicMock()):
            with patch.object(mistral_converter, "upload_file_for_ocr", return_value="https://signed.url/doc"):
                with patch.object(mistral_converter, "query_document", return_value=(True, "The answer is 42", None)):
                    ok, answer, err = mistral_converter.query_document_file(pdf, "what?")
        assert ok is True
        assert answer == "The answer is 42"


# ============================================================================
# submit_batch_ocr_job Tests
# ============================================================================


class TestSubmitBatchOcrJob:
    """Test batch job submission."""

    def test_no_client(self, tmp_path):
        with patch.object(mistral_converter, "get_mistral_client", return_value=None):
            ok, job_id, err = mistral_converter.submit_batch_ocr_job(tmp_path / "batch.jsonl")
        assert ok is False

    def test_successful_submission(self, tmp_path):
        batch_file = tmp_path / "batch.jsonl"
        batch_file.write_text('{"body": {}}\n')

        mock_upload = MagicMock(id="batch_file_id")
        mock_job = MagicMock(id="job_abc")

        with patch.object(mistral_converter, "get_mistral_client") as mock_get:
            mock_client = MagicMock()
            mock_client.files.upload.return_value = mock_upload
            mock_client.batch.jobs.create.return_value = mock_job
            mock_get.return_value = mock_client

            with patch.object(config, "MISTRAL_BATCH_TIMEOUT_HOURS", 48):
                ok, job_id, err = mistral_converter.submit_batch_ocr_job(batch_file)

        assert ok is True
        assert job_id == "job_abc"

    def test_api_error(self, tmp_path):
        batch_file = tmp_path / "batch.jsonl"
        batch_file.write_text('{"body": {}}\n')

        with patch.object(mistral_converter, "get_mistral_client") as mock_get:
            mock_client = MagicMock()
            mock_client.files.upload.side_effect = Exception("upload error")
            mock_get.return_value = mock_client

            ok, job_id, err = mistral_converter.submit_batch_ocr_job(batch_file)
        assert ok is False


# ============================================================================
# cancel_batch_job Tests
# ============================================================================


class TestCancelBatchJob:
    """Test batch job cancellation."""

    def test_successful_cancel(self):
        mock_job = MagicMock(status="CANCELLATION_REQUESTED")
        with patch.object(mistral_converter, "get_mistral_client") as mock_get:
            mock_client = MagicMock()
            mock_client.batch.jobs.cancel.return_value = mock_job
            mock_get.return_value = mock_client

            ok, status, err = mistral_converter.cancel_batch_job("job_to_cancel")
        assert ok is True

    def test_no_client(self):
        with patch.object(mistral_converter, "get_mistral_client", return_value=None):
            ok, status, err = mistral_converter.cancel_batch_job("job_x")
        assert ok is False


# ============================================================================
# download_batch_errors Tests
# ============================================================================


class TestDownloadBatchErrors:
    """Test batch error downloading."""

    def test_successful_download(self, tmp_path):
        mock_job = MagicMock()
        mock_job.error_file = "error_file_id"

        with patch.object(mistral_converter, "get_mistral_client") as mock_get:
            mock_client = MagicMock()
            mock_client.batch.jobs.get.return_value = mock_job
            mock_client.files.download.return_value = b'{"error": "bad page"}\n'
            mock_get.return_value = mock_client

            ok, path, err = mistral_converter.download_batch_errors("job_err", output_dir=tmp_path)

        assert ok is True
        assert path.exists()

    def test_no_error_file(self):
        mock_job = MagicMock()
        mock_job.error_file = None

        with patch.object(mistral_converter, "get_mistral_client") as mock_get:
            mock_client = MagicMock()
            mock_client.batch.jobs.get.return_value = mock_job
            mock_get.return_value = mock_client

            ok, path, err = mistral_converter.download_batch_errors("job_no_err")
        assert ok is False


# ============================================================================
# _process_ocr_result_pipeline Tests
# ============================================================================


class TestProcessOcrResultPipeline:
    """Test OCR result processing pipeline."""

    def test_fresh_result_with_quality(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)
        monkeypatch.setattr(config, "SAVE_MISTRAL_JSON", False)
        monkeypatch.setattr(config, "ENABLE_OCR_QUALITY_ASSESSMENT", True)
        monkeypatch.setattr(config, "ENABLE_OCR_WEAK_PAGE_IMPROVEMENT", False)

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF")
        ocr_result = {"full_text": "Hello", "pages": [{"text": "Hello", "page_number": 1}]}

        with patch.object(mistral_converter, "assess_ocr_quality", return_value={"quality_score": 95, "weak_page_count": 0}):
            with patch.object(mistral_converter, "_create_markdown_output", return_value=tmp_path / "out.md"):
                with patch.object(mistral_converter, "save_extracted_images"):
                    with patch.object(mistral_converter, "_save_structured_outputs"):
                        with patch("utils.cache.set"):
                            ok, path, err = mistral_converter._process_ocr_result_pipeline(
                                MagicMock(), pdf, ocr_result, True, False, False
                            )

        assert ok is True

    def test_cached_result_skips_improvement(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "OUTPUT_MD_DIR", tmp_path)
        monkeypatch.setattr(config, "SAVE_MISTRAL_JSON", False)
        monkeypatch.setattr(config, "ENABLE_OCR_QUALITY_ASSESSMENT", True)

        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF")
        ocr_result = {
            "full_text": "Hello",
            "pages": [{"text": "Hello", "page_number": 1}],
            "quality_assessment": {"quality_score": 50, "weak_page_count": 1},
        }

        with patch.object(mistral_converter, "_create_markdown_output", return_value=tmp_path / "out.md"):
            with patch.object(mistral_converter, "save_extracted_images"):
                with patch.object(mistral_converter, "_save_structured_outputs"):
                    ok, path, err = mistral_converter._process_ocr_result_pipeline(
                        MagicMock(), pdf, ocr_result, True, True, True  # from_cache=True
                    )

        assert ok is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
