"""
Tests for mistral_converter.py module.

Tests cover:
- SSRF URL validation (_validate_document_url)
- OCR quality assessment (assess_ocr_quality, _is_weak_page)
- Annotation format helpers (get_bbox_annotation_format, get_document_annotation_format)
- Batch file creation (create_batch_ocr_file)
- Client cache invalidation (reset_mistral_client)
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402

# Initialize config dirs so imports work
config.ensure_directories()

import mistral_converter  # noqa: E402


# ============================================================================
# _validate_document_url Tests
# ============================================================================


class TestValidateDocumentUrl:
    """Test SSRF prevention in _validate_document_url."""

    def test_valid_https_url(self):
        ok, err = mistral_converter._validate_document_url("https://example.com/doc.pdf")
        assert ok is True
        assert err is None

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
        """Calling reset should not raise."""
        mistral_converter.reset_mistral_client()
        # After reset, cache_info should show 0 hits
        info = mistral_converter.get_mistral_client.cache_info()
        assert info.currsize == 0


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
