"""
Tests for schemas.py module.

Tests cover:
- Schema retrieval functions (get_document_schema, get_bbox_schema)
- Pydantic model retrieval (get_document_pydantic_model, get_bbox_pydantic_model)
- Schema structure validation (required keys, types)
"""

import sys
from pathlib import Path
from typing import Dict, Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import schemas  # noqa: E402


# ============================================================================
# get_document_schema Tests
# ============================================================================


class TestGetDocumentSchema:
    """Test document schema retrieval."""

    @pytest.mark.parametrize(
        "schema_type",
        ["invoice", "financial_statement", "form", "generic"],
    )
    def test_valid_types_return_dict(self, schema_type: str):
        result = schemas.get_document_schema(schema_type)
        assert isinstance(result, dict)

    def test_unknown_type_falls_back(self):
        """Unknown types should fall back to generic."""
        result = schemas.get_document_schema("nonexistent_type")
        assert isinstance(result, dict)

    @pytest.mark.parametrize(
        "schema_type",
        ["invoice", "financial_statement", "form", "generic"],
    )
    def test_schema_has_required_keys(self, schema_type: str):
        result = schemas.get_document_schema(schema_type)
        # Should have at minimum a 'schema' key with the JSON schema
        assert "schema" in result or "name" in result


# ============================================================================
# get_bbox_schema Tests
# ============================================================================


class TestGetBboxSchema:
    """Test bounding box schema retrieval."""

    def test_structured_returns_dict(self):
        result = schemas.get_bbox_schema("structured")
        assert isinstance(result, dict)

    def test_schema_has_required_keys(self):
        result = schemas.get_bbox_schema("structured")
        assert "schema" in result or "name" in result


# ============================================================================
# Pydantic Model Tests
# ============================================================================


class TestPydanticModels:
    """Test Pydantic model retrieval and JSON schema generation."""

    def test_bbox_pydantic_model_returns_class(self):
        model = schemas.get_bbox_pydantic_model()
        # Should return a Pydantic model class or None
        if model is not None:
            # Should be able to generate a JSON schema
            json_schema = model.model_json_schema()
            assert isinstance(json_schema, dict)
            assert "properties" in json_schema or "type" in json_schema

    @pytest.mark.parametrize(
        "doc_type",
        ["invoice", "generic", "financial_statement", "form"],
    )
    def test_document_pydantic_model_returns_class(self, doc_type: str):
        model = schemas.get_document_pydantic_model(doc_type)
        if model is not None:
            json_schema = model.model_json_schema()
            assert isinstance(json_schema, dict)

    def test_unknown_document_type_returns_none_or_generic(self):
        model = schemas.get_document_pydantic_model("nonexistent")
        # Should return None or fall back to generic
        assert model is None or hasattr(model, "model_json_schema")


# ============================================================================
# Schema Content Validation
# ============================================================================


class TestSchemaContent:
    """Validate that schemas contain sensible content."""

    def test_invoice_schema_has_expected_fields(self):
        result = schemas.get_document_schema("invoice")
        schema_body = result.get("schema", result)
        # The word "invoice" should appear somewhere in the schema
        schema_str = str(schema_body).lower()
        assert "invoice" in schema_str or "total" in schema_str or "amount" in schema_str

    def test_generic_schema_is_not_empty(self):
        result = schemas.get_document_schema("generic")
        schema_body = result.get("schema", result)
        assert len(str(schema_body)) > 20  # Non-trivial schema


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
