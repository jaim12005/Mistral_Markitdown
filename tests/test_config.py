"""
Tests for config.py module
"""

import os
from pathlib import Path
import pytest

# Add parent directory to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

import config


class TestDirectoryCreation:
    """Test directory creation functionality."""

    def test_ensure_directories_creates_paths(self):
        """Test that ensure_directories creates required paths."""
        # This test verifies the directories exist after config import
        assert config.INPUT_DIR.exists()
        assert config.OUTPUT_MD_DIR.exists()
        assert config.OUTPUT_TXT_DIR.exists()
        assert config.OUTPUT_IMAGES_DIR.exists()
        assert config.CACHE_DIR.exists()
        assert config.LOGS_DIR.exists()
        assert config.METADATA_DIR.exists()


class TestConfigurationValidation:
    """Test configuration validation."""

    def test_validate_configuration_returns_list(self):
        """Test that validation returns a list of issues."""
        issues = config.validate_configuration()
        assert isinstance(issues, list)

    def test_validate_configuration_warnings(self, monkeypatch):
        """Test validation warnings for missing API keys."""
        # Temporarily remove API key
        monkeypatch.setattr(config, "MISTRAL_API_KEY", "")

        issues = config.validate_configuration()

        # Should warn about missing Mistral API key
        assert any("MISTRAL_API_KEY" in issue for issue in issues)


class TestModelSelection:
    """Test model selection functionality."""

    def test_select_best_model_always_returns_ocr(self):
        """Test that select_best_model always returns OCR model."""
        # Should always return mistral-ocr-latest for OCR tasks
        model = config.select_best_model("pdf")
        assert model == config.MISTRAL_OCR_MODEL

        model = config.select_best_model("png")
        assert model == config.MISTRAL_OCR_MODEL

        model = config.select_best_model("docx")
        assert model == config.MISTRAL_OCR_MODEL

    def test_select_best_model_with_analysis(self):
        """Test model selection with content analysis."""
        content_analysis = {"has_images": True, "has_code": False, "is_complex": True}

        model = config.select_best_model("pdf", content_analysis)
        assert model == config.MISTRAL_OCR_MODEL


class TestFileTypeConfiguration:
    """Test file type configuration."""

    def test_markitdown_supported_types(self):
        """Test MarkItDown supported file types."""
        assert "pdf" in config.MARKITDOWN_SUPPORTED
        assert "docx" in config.MARKITDOWN_SUPPORTED
        assert "xlsx" in config.MARKITDOWN_SUPPORTED
        assert "png" in config.MARKITDOWN_SUPPORTED

    def test_mistral_ocr_supported_types(self):
        """Test Mistral OCR supported file types."""
        assert "pdf" in config.MISTRAL_OCR_SUPPORTED
        assert "png" in config.MISTRAL_OCR_SUPPORTED
        assert "jpg" in config.MISTRAL_OCR_SUPPORTED
        assert "docx" in config.MISTRAL_OCR_SUPPORTED

    def test_pdf_extensions(self):
        """Test PDF extensions."""
        assert "pdf" in config.PDF_EXTENSIONS

    def test_image_extensions(self):
        """Test image extensions."""
        assert "png" in config.IMAGE_EXTENSIONS
        assert "jpg" in config.IMAGE_EXTENSIONS
        assert "jpeg" in config.IMAGE_EXTENSIONS

    def test_office_extensions(self):
        """Test office document extensions."""
        assert "docx" in config.OFFICE_EXTENSIONS
        assert "pptx" in config.OFFICE_EXTENSIONS
        assert "xlsx" in config.OFFICE_EXTENSIONS


class TestMistralModels:
    """Test Mistral models configuration."""

    def test_mistral_models_defined(self):
        """Test that Mistral models are properly defined."""
        assert isinstance(config.MISTRAL_MODELS, dict)
        assert len(config.MISTRAL_MODELS) > 0

    def test_ocr_model_exists(self):
        """Test that the OCR model is defined."""
        assert "mistral-ocr-latest" in config.MISTRAL_MODELS

    def test_model_structure(self):
        """Test that models have required fields."""
        for model_id, model_info in config.MISTRAL_MODELS.items():
            assert "name" in model_info
            assert "description" in model_info
            assert "best_for" in model_info
            assert "max_tokens" in model_info


class TestConfigurationDefaults:
    """Test default configuration values."""

    def test_cache_duration_default(self):
        """Test cache duration default value."""
        assert isinstance(config.CACHE_DURATION_HOURS, int)
        assert config.CACHE_DURATION_HOURS > 0

    def test_max_concurrent_files_default(self):
        """Test max concurrent files default."""
        assert isinstance(config.MAX_CONCURRENT_FILES, int)
        assert config.MAX_CONCURRENT_FILES > 0

    def test_log_level_valid(self):
        """Test log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        assert config.LOG_LEVEL in valid_levels

    def test_ocr_model_correct(self):
        """Test OCR model is set correctly."""
        assert config.MISTRAL_OCR_MODEL == "mistral-ocr-latest"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
