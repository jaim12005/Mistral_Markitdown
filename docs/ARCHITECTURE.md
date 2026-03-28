# Architecture

This document describes the high-level architecture of the Enhanced Document Converter.

## System Overview

The converter uses a **dual-engine** design: a local MarkItDown engine for fast, offline processing and a cloud-based Mistral AI OCR engine for high-fidelity document understanding.

```mermaid
flowchart TD
    A[Input Document] --> B{Smart Router}
    B -->|Text-based / Office| C[MarkItDown Engine]
    B -->|Scanned / Image-heavy| D[Mistral OCR Engine]
    B -->|auto mode| E[Content Analyzer]
    E -->|text density high| C
    E -->|text density low| D

    C --> F[Local Conversion]
    F --> G[Markdown Output]

    D --> H[Upload to Mistral Files API]
    H --> I[OCR Processing]
    I --> J[Quality Assessment]
    J -->|score ≥ threshold| G
    J -->|score < threshold| K[Re-process Weak Pages]
    K --> G

    G --> L{Local post-processing}
    L --> M[PDF Table Extraction]
    L --> P[Final Output]

    Q[Document QnA mode] --> P

    subgraph Local Engine
        C
        F
    end

    subgraph Cloud Engine
        D
        H
        I
        J
        K
    end

    subgraph Table Pipeline
        M
        M1[pdfplumber line-based] --> M
        M2[pdfplumber text-based] --> M
    end
```

## Module Responsibilities

| Module                 | Role                                                                                         |
| ---------------------- | -------------------------------------------------------------------------------------------- |
| `config.py`            | Environment loading, path setup, runtime constants, validation                               |
| `utils.py`             | Logging, caching (SHA-256 + TTL), table formatting, file validation, YAML frontmatter        |
| `schemas.py`           | Pydantic models and JSON schemas for structured extraction (invoices, contracts, etc.)       |
| `local_converter.py`   | MarkItDown wrapper, PDF table extraction (pdfplumber), PDF to images                         |
| `mistral_converter.py` | Mistral OCR client, upload/process/batch, QnA streaming, SSRF validation, image optimization |
| `main.py`              | CLI entry point, smart routing, concurrent processing, interactive menu                      |

## Data Flow

1. **Input** — User provides file path, URL, or directory
2. **Routing** — Smart router analyzes content to pick the best engine
3. **Conversion** — Selected engine produces Markdown
4. **Caching** — Results cached by SHA-256 content hash (24h TTL)
5. **Post-processing** — Optional pdfplumber table extraction on local/PDF paths. Bbox/document structured fields are returned by the **Mistral OCR** call when enabled (not a separate post-pass on markdown). **Document QnA** is a separate mode (chat over a document URL), not an automatic follow-up to conversion.
6. **Output** — Markdown saved to `output_md/`, plain text to `output_txt/`
