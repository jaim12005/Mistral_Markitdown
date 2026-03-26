# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-03-24

### Added

- **Streaming Document QnA** — `query_document_stream()` delivers answer tokens in real-time for interactive experiences
- **Batch OCR mode** — Submit 10+ documents to Mistral Batch API at 50% cost reduction with job tracking
- **OCR quality assessment** — Automated 0-100 scoring with weak page auto-reprocessing
- **Structured data extraction** — Built-in Pydantic schemas for invoices, financial statements, contracts, forms, and generic documents
- **Contract document schema** — Dedicated `ContractDocument` model for extracting parties, dates, clauses, signatures
- **Smart routing** — Auto-picks MarkItDown or Mistral OCR based on file content analysis, not just extension
- **PDF table extraction** — Multi-strategy pipeline: pdfplumber + Camelot lattice + Camelot stream with post-processing
- **Image optimization** — Automatic resize, contrast, and sharpness enhancement before OCR upload
- **File cleanup** — Auto-delete uploaded files from Mistral after configurable retention period
- **CI/CD workflows** — GitHub Actions for multi-platform testing and linting
- **603 tests** at 98%+ code coverage

### Changed

- Upgraded Mistral SDK to v2.1.3 (Files API, `response_format_from_pydantic_model`, `chat.stream`)
- Upgraded MarkItDown to v0.1.5 (StreamInfo support, plugin architecture)
- Rearchitected from single-engine to dual-engine design
- Concurrent file processing via ThreadPoolExecutor
- SHA-256 content-based caching with 24-hour TTL

### Fixed

- Windows Poppler path detection in PDF-to-image conversion
- Merged currency cell splitting in financial documents
- Split header fragment rejoining in PDF tables
- Thread safety for MarkItDown and Mistral client singletons
- SSRF protection on document URL validation (private networks, IPv6-mapped IPv4)

## [2.0.0] - 2024-10-27

### Added

- Mistral OCR integration via Files API with signed URLs
- Multi-format support (30+ document types via MarkItDown)
- Interactive 7-mode CLI menu
- Intelligent caching system
- PDF to image conversion

### Changed

- Migrated from single-file script to modular architecture
- Added configuration management with 70+ environment variables

## [1.0.0] - 2024-10-01

### Added

- Initial release with basic document conversion
- MarkItDown integration for local processing
- Simple CLI interface
