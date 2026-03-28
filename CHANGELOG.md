# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.1] - 2026-03-28

### Added

- Shared `_BaseSchema` base class for all Pydantic schema models with `extra="forbid"`, `frozen=True`, `str_strip_whitespace=True`
- Numeric constraints on schema fields (`DocumentSection.level` ge=1/le=6, `TableAnnotation.rows`/`columns` ge=1)
- Getter functions in `schemas.py` now log warnings on unknown schema type keys
- Configuration validation for `MISTRAL_SERVER_URL`, `PDF_IMAGE_FORMAT`, and `MARKITDOWN_EXIFTOOL_PATH`
- `OSError` handling in `config.ensure_directories()` with friendly error messages
- `_extract_pdf_tables()` shared helper in `main.py` (eliminates duplication)
- `_prepare_qna_call()` shared helper in `mistral_converter.py` (eliminates QnA duplication)
- Argparse mutual exclusion validation (`_validate_args`) rejects invalid flag combinations
- Parse error surfacing in OCR pipeline -- `process_with_ocr` now logs and includes parse errors
- Terminal sanitization applied to file names in routing plan and file selection display
- Test gate in `publish.yml` -- PyPI publish now requires passing tests and lint
- Python >= 3.10 version checks in `quick_start.sh` and `run_converter.bat`
- 5 new test classes: `TestSanitizeForTerminal`, `TestAtomicWriteBinary`, `TestUiPrint`, `TestReadStdinBytesLimitedNegative`

### Changed

- `pyproject.toml` dependency lower bounds synced with `requirements*.txt` (pytest >=9.0, black >=26.3, etc.)
- Removed unused `setuptools_scm` from build-system requires
- `main()` refactored into `_validate_args()`, `_run_stdin_mode()`, `_collect_files_non_interactive()`, `_run_direct_mode()`
- `mode_batch_ocr` split into `_batch_submit()`, `_batch_status()`, `_batch_list()`, `_batch_download()` sub-actions
- Consistent `sys.exit()` exit codes for `--test`, `--mode status`, `--mode maintenance` paths
- Bare tool invocations replaced with `python3 -m` / `python -m` in Makefile and all CI workflows
- Bandit CI scope expanded from `*.py` (root-only) to recursive scan with excludes
- `_safe_int`/`_safe_float` in `config.py` catch only `ValueError` (removed dead `TypeError` catch)
- Schema getter return types improved from bare `Type` to `Type[BaseModel]`
- All documentation updated: test counts (~665), `python3` consistency, CI workflow descriptions

### Fixed

- `select_files` crash when a file disappears between listing and `stat()` call
- Silent data loss when OCR response parsing fails (parse_error now surfaced)
- Nonsensical CLI flag combinations silently accepted (now rejected with `parser.error()`)
- Empty input directory in non-interactive mode returned exit code 0 (now exits with 1)

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
- **665 tests** at 98%+ code coverage

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
