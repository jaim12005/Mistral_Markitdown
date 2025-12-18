"""
Enhanced Document Converter v2.1.1 - JSON Schemas for Structured Extraction

This module provides predefined JSON schemas AND Pydantic models for structured
data extraction from various document types using Mistral AI's structured output
capabilities.

Documentation references:
- Mistral Structured Outputs: https://docs.mistral.ai/capabilities/json_mode/
- Mistral OCR Annotations: https://docs.mistral.ai/capabilities/document_ai/annotations
- JSON Schema: https://json-schema.org/
"""

from typing import Dict, Any, Optional, List, Type

# Try to import Pydantic for model-based schema definitions
# The new Mistral SDK recommends using Pydantic models with response_format_from_pydantic_model
try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    BaseModel = None
    Field = None
    PYDANTIC_AVAILABLE = False


# ============================================================================
# Pydantic Models for BBox Annotations
# These are the recommended way to define schemas for Mistral OCR annotations
# Use with: from mistralai.extra import response_format_from_pydantic_model
# ============================================================================

if PYDANTIC_AVAILABLE:
    class ImageAnnotation(BaseModel):
        """Pydantic model for image/bbox annotation extraction."""
        image_type: str = Field(..., description="The type of the image (chart, diagram, photo, table, figure, etc.)")
        short_description: str = Field(..., description="A brief description in English describing the image content.")
        summary: str = Field(..., description="A detailed summary of the image including key information and data points.")
    
    class TableAnnotation(BaseModel):
        """Pydantic model for table bbox annotation extraction."""
        table_type: str = Field(..., description="The type of table (data, financial, comparison, schedule, etc.)")
        caption: Optional[str] = Field(None, description="Table caption or title if present.")
        rows: int = Field(..., description="Number of rows in the table.")
        columns: int = Field(..., description="Number of columns in the table.")
        has_header: bool = Field(..., description="Whether the table has a header row.")
        content_summary: str = Field(..., description="Summary of the table's content and purpose.")
    
    class ChartAnnotation(BaseModel):
        """Pydantic model for chart/graph bbox annotation extraction."""
        chart_type: str = Field(..., description="The type of chart (bar, line, pie, scatter, histogram, etc.)")
        title: Optional[str] = Field(None, description="Chart title if present.")
        x_axis_label: Optional[str] = Field(None, description="X-axis label if present.")
        y_axis_label: Optional[str] = Field(None, description="Y-axis label if present.")
        data_summary: str = Field(..., description="Summary of the data trends and key insights from the chart.")
        
    class BBoxStructuredAnnotation(BaseModel):
        """Comprehensive Pydantic model for bounding box annotation."""
        bbox_type: str = Field(..., description="Type of content in bounding box: text, table, figure, heading, list, chart, other")
        text_content: str = Field(..., description="Extracted text from the bounding box.")
        confidence: Optional[float] = Field(None, ge=0, le=1, description="Confidence score for extraction (0-1).")
        is_handwritten: Optional[bool] = Field(None, description="Whether content appears handwritten.")
        language: Optional[str] = Field(None, description="Detected language.")
    
    # Document-level Pydantic models
    class VendorInfo(BaseModel):
        """Vendor information for invoice extraction."""
        name: str = Field(..., description="Vendor name")
        address: Optional[str] = Field(None, description="Vendor address")
        tax_id: Optional[str] = Field(None, description="Tax ID or VAT number")
        contact: Optional[str] = Field(None, description="Contact information")
    
    class CustomerInfo(BaseModel):
        """Customer information for invoice extraction."""
        name: Optional[str] = Field(None, description="Customer name")
        address: Optional[str] = Field(None, description="Customer address")
        tax_id: Optional[str] = Field(None, description="Tax ID or VAT number")
    
    class InvoiceDetails(BaseModel):
        """Invoice details for extraction."""
        invoice_number: str = Field(..., description="Invoice number")
        invoice_date: str = Field(..., description="Invoice date (ISO format)")
        due_date: Optional[str] = Field(None, description="Payment due date")
        purchase_order: Optional[str] = Field(None, description="PO number if applicable")
    
    class LineItem(BaseModel):
        """Line item for invoice extraction."""
        description: str = Field(..., description="Item description")
        quantity: Optional[float] = Field(None, description="Quantity")
        unit_price: Optional[float] = Field(None, description="Unit price")
        amount: float = Field(..., description="Total amount for this line")
        tax_rate: Optional[float] = Field(None, description="Tax rate if applicable")
    
    class InvoiceTotals(BaseModel):
        """Invoice totals for extraction."""
        subtotal: Optional[float] = Field(None, description="Subtotal before tax")
        tax: Optional[float] = Field(None, description="Total tax amount")
        total: float = Field(..., description="Total amount due")
        currency: Optional[str] = Field(None, description="Currency code (USD, EUR, etc.)")
    
    class InvoiceDocument(BaseModel):
        """Complete invoice document extraction model."""
        document_type: str = Field(..., description="Type of financial document: invoice, receipt, bill")
        vendor: VendorInfo = Field(..., description="Vendor information")
        customer: Optional[CustomerInfo] = Field(None, description="Customer information")
        invoice_details: InvoiceDetails = Field(..., description="Invoice details")
        line_items: Optional[List[LineItem]] = Field(None, description="List of invoice line items")
        totals: InvoiceTotals = Field(..., description="Invoice totals")
        payment_terms: Optional[str] = Field(None, description="Payment terms and conditions")
        notes: Optional[str] = Field(None, description="Additional notes or comments")
    
    class DocumentSection(BaseModel):
        """Document section for generic extraction."""
        heading: str = Field(..., description="Section heading")
        level: Optional[int] = Field(None, description="Heading level (1-6)")
        content_summary: Optional[str] = Field(None, description="Brief summary of section content")
    
    class GenericDocument(BaseModel):
        """Generic document extraction model."""
        document_type: str = Field(..., description="Type or category of document")
        title: Optional[str] = Field(None, description="Document title")
        authors: Optional[List[str]] = Field(None, description="Document authors or creators")
        date: Optional[str] = Field(None, description="Document date (ISO format)")
        sections: Optional[List[DocumentSection]] = Field(None, description="Document sections and headings")
        summary: Optional[str] = Field(None, description="Brief document summary")

else:
    # Placeholder classes when Pydantic is not available
    ImageAnnotation = None
    TableAnnotation = None
    ChartAnnotation = None
    BBoxStructuredAnnotation = None
    InvoiceDocument = None
    GenericDocument = None

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


# ============================================================================
# Pydantic Model Getters
# These functions return Pydantic model classes for use with
# mistralai.extra.response_format_from_pydantic_model()
# ============================================================================

def get_bbox_pydantic_model(annotation_type: str = "image") -> Optional[Type]:
    """
    Get a Pydantic model class for bounding box annotation.
    
    Use with mistralai.extra.response_format_from_pydantic_model() for
    the bbox_annotation_format parameter.
    
    Args:
        annotation_type: Type of annotation model to return:
            - "image": General image/figure annotation (default, most versatile)
            - "table": Table-specific annotation with structure info
            - "chart": Chart/graph annotation with axis info
            - "structured": Comprehensive bbox annotation
    
    Returns:
        Pydantic model class, or None if Pydantic not available
    
    Example:
        >>> from mistralai.extra import response_format_from_pydantic_model
        >>> model = get_bbox_pydantic_model("image")
        >>> bbox_format = response_format_from_pydantic_model(model)
        >>> response = client.ocr.process(
        ...     model="mistral-ocr-latest",
        ...     document=DocumentURLChunk(document_url="..."),
        ...     bbox_annotation_format=bbox_format,
        ...     include_image_base64=True
        ... )
    """
    if not PYDANTIC_AVAILABLE:
        return None
    
    model_map = {
        "image": ImageAnnotation,
        "table": TableAnnotation,
        "chart": ChartAnnotation,
        "structured": BBoxStructuredAnnotation,
    }
    
    return model_map.get(annotation_type, ImageAnnotation)


def get_document_pydantic_model(doc_type: str = "generic") -> Optional[Type]:
    """
    Get a Pydantic model class for document-level annotation.
    
    Use with mistralai.extra.response_format_from_pydantic_model() for
    the document_annotation_format parameter.
    
    Args:
        doc_type: Type of document model to return:
            - "generic": General document structure (default)
            - "invoice": Invoice/receipt extraction
    
    Returns:
        Pydantic model class, or None if Pydantic not available
    
    Example:
        >>> from mistralai.extra import response_format_from_pydantic_model
        >>> model = get_document_pydantic_model("invoice")
        >>> doc_format = response_format_from_pydantic_model(model)
        >>> response = client.ocr.process(
        ...     model="mistral-ocr-latest",
        ...     document=DocumentURLChunk(document_url="..."),
        ...     document_annotation_format=doc_format
        ... )
    """
    if not PYDANTIC_AVAILABLE:
        return None
    
    model_map = {
        "generic": GenericDocument,
        "invoice": InvoiceDocument,
        # Note: financial_statement and form use JSON schemas only for now
        # Add Pydantic models as needed
    }
    
    return model_map.get(doc_type, GenericDocument)
