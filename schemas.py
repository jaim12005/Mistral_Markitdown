"""
Enhanced Document Converter v2.1.1 - JSON Schemas for Structured Extraction

This module provides predefined JSON schemas for structured data extraction
from various document types using Mistral AI's structured output capabilities.

Documentation references:
- Mistral Structured Outputs: https://docs.mistral.ai/capabilities/json_mode/
- JSON Schema: https://json-schema.org/
"""

from typing import Dict, Any

# ============================================================================
# Document-Level Schemas (document_annotation_format)
# ============================================================================

INVOICE_DOCUMENT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "document_type": {
            "type": "string",
            "enum": ["invoice", "receipt", "bill"],
            "description": "Type of financial document",
        },
        "vendor": {
            "type": "object",
    "additionalProperties": False,
            "properties": {
                "name": {"type": "string", "description": "Vendor name"},
                "address": {"type": "string", "description": "Vendor address"},
                "tax_id": {"type": "string", "description": "Tax ID or VAT number"},
                "contact": {"type": "string", "description": "Contact information"},
            },
            "required": ["name"],
        },
        "customer": {
            "type": "object",
    "additionalProperties": False,
            "properties": {
                "name": {"type": "string", "description": "Customer name"},
                "address": {"type": "string", "description": "Customer address"},
                "tax_id": {"type": "string", "description": "Tax ID or VAT number"},
            },
        },
        "invoice_details": {
            "type": "object",
    "additionalProperties": False,
            "properties": {
                "invoice_number": {"type": "string", "description": "Invoice number"},
                "invoice_date": {
                    "type": "string",
                    "description": "Invoice date (ISO format)",
                },
                "due_date": {"type": "string", "description": "Payment due date"},
                "purchase_order": {
                    "type": "string",
                    "description": "PO number if applicable",
                },
            },
            "required": ["invoice_number", "invoice_date"],
        },
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
    "additionalProperties": False,
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit_price": {"type": "number"},
                    "amount": {"type": "number"},
                    "tax_rate": {"type": "number"},
                },
                "required": ["description", "amount"],
            },
            "description": "List of invoice line items",
        },
        "totals": {
            "type": "object",
    "additionalProperties": False,
            "properties": {
                "subtotal": {"type": "number", "description": "Subtotal before tax"},
                "tax": {"type": "number", "description": "Total tax amount"},
                "total": {"type": "number", "description": "Total amount due"},
                "currency": {
                    "type": "string",
                    "description": "Currency code (USD, EUR, etc.)",
                },
            },
            "required": ["total"],
        },
        "payment_terms": {
            "type": "string",
            "description": "Payment terms and conditions",
        },
        "notes": {"type": "string", "description": "Additional notes or comments"},
    },
    "required": ["document_type", "invoice_details", "totals"],
}


FINANCIAL_STATEMENT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "statement_type": {
            "type": "string",
            "enum": ["balance_sheet", "income_statement", "cash_flow", "trial_balance"],
            "description": "Type of financial statement",
        },
        "company": {
            "type": "object",
    "additionalProperties": False,
            "properties": {
                "name": {"type": "string"},
                "registration_number": {"type": "string"},
                "address": {"type": "string"},
            },
            "required": ["name"],
        },
        "period": {
            "type": "object",
    "additionalProperties": False,
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Period start (ISO format)",
                },
                "end_date": {
                    "type": "string",
                    "description": "Period end (ISO format)",
                },
                "fiscal_year": {"type": "integer"},
            },
            "required": ["end_date"],
        },
        "accounts": {
            "type": "array",
            "items": {
                "type": "object",
    "additionalProperties": False,
                "properties": {
                    "account_number": {"type": "string"},
                    "account_name": {"type": "string"},
                    "category": {
                        "type": "string",
                        "description": "Assets, Liabilities, Revenue, etc.",
                    },
                    "debit": {"type": "number"},
                    "credit": {"type": "number"},
                    "balance": {"type": "number"},
                },
                "required": ["account_name"],
            },
            "description": "List of accounts with balances",
        },
        "totals": {
            "type": "object",
    "additionalProperties": False,
            "properties": {
                "total_assets": {"type": "number"},
                "total_liabilities": {"type": "number"},
                "total_equity": {"type": "number"},
                "total_revenue": {"type": "number"},
                "total_expenses": {"type": "number"},
                "net_income": {"type": "number"},
            },
        },
        "currency": {"type": "string", "description": "Currency code"},
        "audited": {
            "type": "boolean",
            "description": "Whether the statement is audited",
        },
        "notes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Footnotes and additional information",
        },
    },
    "required": ["statement_type", "company", "period", "accounts"],
}


FORM_DOCUMENT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "form_type": {
            "type": "string",
            "description": "Type of form (application, survey, contract, etc.)",
        },
        "form_title": {"type": "string", "description": "Title or name of the form"},
        "form_number": {"type": "string", "description": "Form number or identifier"},
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
    "additionalProperties": False,
                "properties": {
                    "field_name": {"type": "string"},
                    "field_type": {
                        "type": "string",
                        "enum": [
                            "text",
                            "number",
                            "date",
                            "checkbox",
                            "signature",
                            "other",
                        ],
                    },
                    "field_value": {"type": "string"},
                    "is_filled": {"type": "boolean"},
                },
                "required": ["field_name", "field_value"],
            },
            "description": "Form fields and their values",
        },
        "signatures": {
            "type": "array",
            "items": {
                "type": "object",
    "additionalProperties": False,
                "properties": {
                    "signer_name": {"type": "string"},
                    "title": {"type": "string"},
                    "date": {"type": "string"},
                    "is_signed": {"type": "boolean"},
                },
            },
            "description": "Signature fields",
        },
        "dates": {
            "type": "object",
    "additionalProperties": False,
            "properties": {
                "submission_date": {"type": "string"},
                "effective_date": {"type": "string"},
                "expiration_date": {"type": "string"},
            },
        },
    },
    "required": ["form_title", "fields"],
}


GENERIC_DOCUMENT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "document_type": {
            "type": "string",
            "description": "Type or category of document",
        },
        "title": {"type": "string", "description": "Document title"},
        "authors": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Document authors or creators",
        },
        "date": {"type": "string", "description": "Document date (ISO format)"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
    "additionalProperties": False,
                "properties": {
                    "heading": {"type": "string"},
                    "level": {"type": "integer", "description": "Heading level (1-6)"},
                    "content_summary": {
                        "type": "string",
                        "description": "Brief summary of section content",
                    },
                },
                "required": ["heading"],
            },
            "description": "Document sections and headings",
        },
        "tables": {
            "type": "array",
            "items": {
                "type": "object",
    "additionalProperties": False,
                "properties": {
                    "caption": {"type": "string"},
                    "rows": {"type": "integer"},
                    "columns": {"type": "integer"},
                    "summary": {
                        "type": "string",
                        "description": "Brief description of table content",
                    },
                },
            },
            "description": "Tables found in document",
        },
        "figures": {
            "type": "array",
            "items": {
                "type": "object",
    "additionalProperties": False,
                "properties": {
                    "caption": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["chart", "graph", "diagram", "photo", "other"],
                    },
                    "description": {"type": "string"},
                },
            },
            "description": "Figures, charts, and images",
        },
        "metadata": {
            "type": "object",
    "additionalProperties": False,
            "properties": {
                "language": {"type": "string"},
                "page_count": {"type": "integer"},
                "keywords": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string", "description": "Document summary"},
            },
        },
    },
    "required": ["document_type"],
}


# ============================================================================
# Bounding Box Schemas (bbox_annotation_format)
# ============================================================================

BBOX_STRUCTURED_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "bbox_type": {
            "type": "string",
            "enum": ["text", "table", "figure", "heading", "list", "other"],
            "description": "Type of content in bounding box",
        },
        "text_content": {
            "type": "string",
            "description": "Extracted text from bounding box",
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Confidence score for extraction",
        },
        "is_handwritten": {
            "type": "boolean",
            "description": "Whether content appears handwritten",
        },
        "language": {"type": "string", "description": "Detected language"},
        "formatting": {
            "type": "object",
    "additionalProperties": False,
            "properties": {
                "bold": {"type": "boolean"},
                "italic": {"type": "boolean"},
                "underline": {"type": "boolean"},
                "font_size": {"type": "number"},
                "font_family": {"type": "string"},
            },
        },
        "table_structure": {
            "type": "object",
    "additionalProperties": False,
            "properties": {
                "rows": {"type": "integer"},
                "columns": {"type": "integer"},
                "has_header": {"type": "boolean"},
            },
            "description": "For table bounding boxes",
        },
        "metadata": {
            "type": "object",
    "additionalProperties": False,
            "properties": {
                "page_number": {"type": "integer"},
                "position": {
                    "type": "string",
                    "enum": ["header", "body", "footer", "sidebar"],
                },
            },
        },
    },
    "required": ["bbox_type", "text_content"],
}


# ============================================================================
# Schema Registry
# ============================================================================

DOCUMENT_SCHEMAS = {
    "invoice": {
        "name": "invoice_extraction",
        "schema": INVOICE_DOCUMENT_SCHEMA,
        "description": "Structured extraction of invoice data including vendor, line items, and totals",
    },
    "financial_statement": {
        "name": "financial_statement_extraction",
        "schema": FINANCIAL_STATEMENT_SCHEMA,
        "description": "Structured extraction of financial statements including accounts and balances",
    },
    "form": {
        "name": "form_extraction",
        "schema": FORM_DOCUMENT_SCHEMA,
        "description": "Structured extraction of form fields and values",
    },
    "generic": {
        "name": "generic_document_extraction",
        "schema": GENERIC_DOCUMENT_SCHEMA,
        "description": "Structured extraction of general document metadata and structure",
    },
}

BBOX_SCHEMAS = {
    "structured": {
        "name": "bbox_structured_extraction",
        "schema": BBOX_STRUCTURED_SCHEMA,
        "description": "Structured extraction of bounding box content with type and formatting",
    }
}


def get_document_schema(schema_type: str = "generic") -> Dict[str, Any]:
    """
    Get a document-level schema by type.

    Args:
        schema_type: Type of schema (invoice, financial_statement, form, generic)

    Returns:
        Schema definition dictionary
    """
    return DOCUMENT_SCHEMAS.get(schema_type, DOCUMENT_SCHEMAS["generic"])


def get_bbox_schema(schema_type: str = "structured") -> Dict[str, Any]:
    """
    Get a bounding box schema by type.

    Args:
        schema_type: Type of schema (currently only 'structured' available)

    Returns:
        Schema definition dictionary
    """
    return BBOX_SCHEMAS.get(schema_type, BBOX_SCHEMAS["structured"])
