"""
Enhanced Document Converter - Main Application

Interactive CLI for document conversion with 7 modes:
1. Convert (Smart)       - Auto-picks best engine per file type
2. Convert (MarkItDown)  - Force local conversion (no API)
3. Convert (Mistral OCR) - Force cloud OCR
4. PDF to Images         - Page rendering
5. Document QnA          - Query documents in natural language
6. Batch OCR             - 50% cost reduction batch jobs
7. System Status         - Cache and performance metrics

Usage:
    python main.py                      # Interactive menu
    python main.py --mode smart         # Smart auto-routing
    python main.py --mode markitdown    # Force MarkItDown
    python main.py --test               # Test mode

Documentation references:
- MarkItDown: https://github.com/microsoft/markitdown
- Mistral OCR: https://docs.mistral.ai/capabilities/document_ai/basic_ocr/
"""

import argparse
import re
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Suppress harmless version-check warning from requests when transitive
# dependency versions (urllib3, chardet) are newer than requests expects.
warnings.filterwarnings("ignore", message=".*urllib3.*chardet.*charset_normalizer.*")

import config
import local_converter
import mistral_converter
import utils

logger = utils.logger


# ============================================================================
# Helper: file listing and validation
# ============================================================================


def _list_input_files() -> List[Path]:
    """Return sorted list of files in the input directory."""
    return sorted(
        (f for f in config.INPUT_DIR.glob("*.*") if f.is_file()),
        key=lambda p: p.name.lower(),
    )


def _filter_valid_files(files: List[Path], mode: Optional[str] = None) -> List[Path]:
    """Return only valid files, logging warnings for invalid ones.

    Args:
        files: List of file paths to validate.
        mode: Conversion mode (``"markitdown"``, ``"mistral_ocr"``, etc.).
              Passed through to ``utils.validate_file`` for per-mode extension checks.
    """
    valid_files = []
    for file_path in files:
        is_valid, error = utils.validate_file(file_path, mode=mode)
        if is_valid:
            valid_files.append(file_path)
        else:
            logger.warning(error)
    return valid_files


# ============================================================================
# Helper: concurrent file processing
# ============================================================================


def _process_files_concurrently(
    file_paths: List[Path],
    process_fn,
    label: str = "Processing files",
) -> Tuple[int, int]:
    """Run *process_fn* on each file, using threads when there are multiple files.

    Args:
        file_paths: Files to process.
        process_fn: Callable(Path) -> Tuple[bool, ...].  First element must be a bool
                    indicating success.
        label: Progress bar label.

    Returns:
        (successful_count, failed_count)
    """
    successful = 0
    failed = 0

    total = len(file_paths)

    if total == 1:
        try:
            result = process_fn(file_paths[0])
            ok = result[0] if isinstance(result, tuple) else result
            if ok:
                successful += 1
            else:
                failed += 1
                err = result[2] if isinstance(result, tuple) and len(result) > 2 else "unknown error"
                logger.error("Failed: %s - %s", file_paths[0].name, err)
        except Exception as e:
            failed += 1
            logger.error("Error processing %s: %s", file_paths[0].name, e)
    else:
        with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_FILES) as executor:
            futures = {executor.submit(process_fn, fp): fp for fp in file_paths}

            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    result = future.result()
                    ok = result[0] if isinstance(result, tuple) else result
                    if ok:
                        successful += 1
                    else:
                        failed += 1
                        err = result[2] if isinstance(result, tuple) and len(result) > 2 else "unknown error"
                        logger.error("Failed: %s - %s", file_path.name, err)
                except Exception as e:
                    failed += 1
                    logger.error("Error processing %s: %s", file_path.name, e)

    utils.ui_print(f"\n{label}: {successful + failed}/{total} complete")

    return successful, failed


# ============================================================================
# Mode 1: Convert (Smart) -- auto-routes by file type
# ============================================================================


def _should_use_ocr(file_path: Path) -> bool:
    """Decide whether a file should be routed to Mistral OCR or MarkItDown.

    - Images (no text layer) -> OCR
    - Scanned / image-only PDFs -> OCR
    - Text-based PDFs -> MarkItDown (faster, free)
    - Office docs (DOCX, PPTX, XLSX) -> MarkItDown (text is directly extractable)
    - Everything else -> MarkItDown
    """
    if not config.MISTRAL_API_KEY:
        return False

    ext = file_path.suffix.lower().lstrip(".")

    # Images always need OCR -- there's no text layer to extract
    if ext in config.IMAGE_EXTENSIONS:
        return True

    # PDFs: check whether they have an extractable text layer
    if ext == "pdf":
        analysis = local_converter.analyze_file_content(file_path)
        if analysis.get("is_text_based"):
            return False  # Text-based PDF: MarkItDown is better
        return True  # Scanned / image-only PDF: needs OCR

    # Everything else (DOCX, PPTX, XLSX, CSV, HTML, TXT, etc.): MarkItDown
    return False


def _route_label_cached(file_path: Path, use_ocr: bool) -> str:
    """Return a human-readable label for the engine that will handle this file."""
    ext = file_path.suffix.lower().lstrip(".")
    if use_ocr:
        label = "Mistral OCR"
        if ext == "pdf":
            label += " (scanned + table extraction)"
        return label
    label = "MarkItDown (local)"
    if ext == "pdf":
        label += " (text-based + table extraction)"
    return label


def _process_single_smart(
    file_path: Path, *, use_ocr: Optional[bool] = None
) -> Tuple[bool, Optional[Path], Optional[str]]:
    """Process one file with smart routing based on file content analysis.

    Args:
        file_path: File to process.
        use_ocr: Pre-computed routing decision.  When *None* (legacy callers),
                 ``_should_use_ocr`` is called on the fly.
    """
    ext = file_path.suffix.lower().lstrip(".")

    # PDF table extraction runs regardless of engine choice
    if ext == "pdf":
        try:
            table_result = local_converter.extract_all_tables(file_path)
            if table_result["table_count"] > 0:
                local_converter.save_tables_to_files(file_path, table_result["tables"])
                logger.info("Extracted %d tables from %s", table_result["table_count"], file_path.name)
        except Exception as e:
            logger.warning("Table extraction failed for %s: %s", file_path.name, e)

    if use_ocr is None:
        use_ocr = _should_use_ocr(file_path)

    if use_ocr:
        return mistral_converter.convert_with_mistral_ocr(file_path)
    else:
        success, content, error = local_converter.convert_with_markitdown(file_path)
        output_path = config.OUTPUT_MD_DIR / f"{utils.safe_output_stem(file_path)}.md" if success else None
        return success, output_path, error


def mode_convert_smart(file_paths: List[Path]) -> Tuple[bool, str]:
    """
    Smart conversion mode: auto-routes each file to the best engine.

    Routing logic:
    - Images (no text layer) -> Mistral OCR
    - Scanned PDFs (no extractable text) -> Mistral OCR + table extraction
    - Text-based PDFs -> MarkItDown + table extraction
    - Office docs, data files, etc. -> MarkItDown

    Multiple files are processed concurrently.
    """
    logger.info("SMART CONVERT MODE: Processing %d file(s)", len(file_paths))

    if config.MAX_BATCH_FILES > 0 and len(file_paths) > config.MAX_BATCH_FILES:
        return False, (
            f"Batch size ({len(file_paths)}) exceeds MAX_BATCH_FILES ({config.MAX_BATCH_FILES}). "
            "Increase the limit or split into smaller batches."
        )

    # Pre-compute routing decisions once so we don't analyse each file twice
    # (once for the routing plan display, once for actual processing).
    routing_cache: Dict[Path, bool] = {fp: _should_use_ocr(fp) for fp in file_paths}

    # Show routing plan
    utils.ui_print("\nRouting plan:")
    if not config.MISTRAL_API_KEY:
        utils.ui_print("  NOTE: No MISTRAL_API_KEY set. All files will use MarkItDown (local).\n")

    for fp in file_paths:
        label = _route_label_cached(fp, routing_cache[fp])
        utils.ui_print(f"  {fp.name:<40} -> {label}")
    utils.ui_print()

    def _process_fn(file_path: Path) -> Tuple[bool, Optional[Path], Optional[str]]:
        return _process_single_smart(file_path, use_ocr=routing_cache[file_path])

    successful, failed = _process_files_concurrently(file_paths, _process_fn, "Converting files")

    total = len(file_paths)
    return failed == 0, f"Processed {successful}/{total} files successfully"


# ============================================================================
# Mode 2: Convert (MarkItDown) -- force local, no API
# ============================================================================


def mode_markitdown_only(file_paths: List[Path]) -> Tuple[bool, str]:
    """Force all files through MarkItDown (local conversion, no API calls)."""
    logger.info("MARKITDOWN MODE: Processing %d file(s)", len(file_paths))

    successful, failed = _process_files_concurrently(
        file_paths, local_converter.convert_with_markitdown, "Converting files"
    )

    return failed == 0, f"Processed {successful}/{len(file_paths)} files successfully"


# ============================================================================
# Mode 3: Convert (Mistral OCR) -- force cloud OCR
# ============================================================================


def mode_mistral_ocr_only(file_paths: List[Path]) -> Tuple[bool, str]:
    """Force all files through Mistral OCR (cloud processing)."""
    if not config.MISTRAL_API_KEY:
        return False, "Mistral OCR requires MISTRAL_API_KEY to be set"

    if config.MAX_BATCH_FILES > 0 and len(file_paths) > config.MAX_BATCH_FILES:
        return False, (
            f"Batch size ({len(file_paths)}) exceeds MAX_BATCH_FILES ({config.MAX_BATCH_FILES}). "
            "Increase the limit or split into smaller batches."
        )

    logger.info("MISTRAL OCR MODE: Processing %d file(s)", len(file_paths))

    successful, failed = _process_files_concurrently(
        file_paths, mistral_converter.convert_with_mistral_ocr, "OCR processing"
    )

    return failed == 0, f"Processed {successful}/{len(file_paths)} files successfully"


# ============================================================================
# Mode 4: PDF to Images
# ============================================================================


def mode_pdf_to_images(file_paths: List[Path]) -> Tuple[bool, str]:
    """Render each PDF page to PNG images."""
    logger.info("PDF TO IMAGES MODE: Converting %d PDF(s)", len(file_paths))

    pdf_files = [fp for fp in file_paths if fp.suffix.lower() == ".pdf"]
    skipped = len(file_paths) - len(pdf_files)
    if skipped:
        logger.warning("Skipping %d non-PDF file(s)", skipped)

    if not pdf_files:
        return False, "No PDF files to convert"

    successful, failed = _process_files_concurrently(
        pdf_files, local_converter.convert_pdf_to_images, "Converting PDFs"
    )

    return failed == 0, f"Converted {successful} PDFs"


# ============================================================================
# Mode 5: Document QnA
# ============================================================================


def mode_document_qna(file_paths: List[Path]) -> Tuple[bool, str]:
    """Query a document in natural language using Mistral chat + OCR."""
    logger.info("DOCUMENT QnA MODE: %d file(s) selected", len(file_paths))

    if not config.MISTRAL_API_KEY:
        return False, "Document QnA requires MISTRAL_API_KEY to be set"

    if len(file_paths) != 1:
        utils.ui_print("\nPlease select exactly 1 file to query.\n")
        return False, "Document QnA works on one file at a time"

    file_path = file_paths[0]

    client = mistral_converter.get_mistral_client()
    if client is None:
        return False, "Mistral client not available"

    try:
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > 50:
            return False, (
                f"File too large for Document QnA ({file_size_mb:.1f} MB). "
                "Mistral limits documents to 50 MB. Consider splitting the document."
            )
    except OSError as e:
        return False, f"Cannot read file: {e}"

    ttl_seconds = config.MISTRAL_SIGNED_URL_EXPIRY * 3600
    upload_started_at = 0.0
    signed_url: Optional[str] = None

    def _get_document_url() -> Optional[str]:
        nonlocal signed_url, upload_started_at
        if signed_url and (time.time() - upload_started_at) < ttl_seconds * 0.9:
            return signed_url
        signed_url = mistral_converter.upload_file_for_ocr(client, file_path)
        upload_started_at = time.time()
        return signed_url

    if not _get_document_url():
        return False, f"Failed to upload {file_path.name} for QnA"

    utils.ui_print(f"\nQuerying: {file_path.name}")
    utils.ui_print(f"Model: {config.MISTRAL_DOCUMENT_QNA_MODEL}")
    utils.ui_print("Type 'exit' or 'quit' to return to menu.\n")

    questions_asked = 0
    while True:
        try:
            question = input("Question: ").strip()
            if not question or question.lower() in ("exit", "quit"):
                break

            document_url = _get_document_url()
            if not document_url:
                utils.ui_print(f"\nError: Failed to refresh document URL for {file_path.name}\n")
                continue

            success, stream, error = mistral_converter.query_document_stream(
                document_url,
                question,
            )

            if success and stream is not None:
                utils.ui_print("\nAnswer: ", end="", flush=True)
                try:
                    for chunk in stream:
                        if chunk.data.choices and chunk.data.choices[0].delta.content:
                            safe_text = utils.sanitize_for_terminal(
                                chunk.data.choices[0].delta.content
                            )
                            utils.ui_print(safe_text, end="", flush=True)
                except Exception as e:
                    utils.ui_print(f"\n\nStream error: {e}")
                utils.ui_print("\n")
                questions_asked += 1
            else:
                utils.ui_print(f"\nError: {error}\n")

        except KeyboardInterrupt:
            break

    return True, f"Asked {questions_asked} question(s) about {file_path.name}"


# ============================================================================
# Mode 6: Batch OCR (50% cost savings)
# ============================================================================


# Batch job ID validation
_JOB_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")


def _validate_job_id(job_id: str) -> bool:
    """Return True if *job_id* looks like a valid Mistral batch job identifier."""
    return bool(_JOB_ID_RE.match(job_id))


def mode_batch_ocr(file_paths: List[Path]) -> Tuple[bool, str]:
    """Submit files for batch OCR processing at 50% cost reduction."""
    logger.info("BATCH OCR MODE: %d file(s) selected", len(file_paths))

    if not config.MISTRAL_API_KEY:
        return False, "Batch OCR requires MISTRAL_API_KEY to be set"

    if not config.MISTRAL_BATCH_ENABLED:
        return False, "Batch processing is disabled (set MISTRAL_BATCH_ENABLED=true)"

    if config.MAX_BATCH_FILES > 0 and len(file_paths) > config.MAX_BATCH_FILES:
        return False, (
            f"Batch size ({len(file_paths)}) exceeds MAX_BATCH_FILES ({config.MAX_BATCH_FILES}). "
            "Increase the limit or split into smaller batches."
        )

    if len(file_paths) < config.MISTRAL_BATCH_MIN_FILES:
        utils.ui_print(f"\nNote: Batch processing is most cost-effective with {config.MISTRAL_BATCH_MIN_FILES}+ files.")
        utils.ui_print(f"You selected {len(file_paths)} file(s). Proceeding anyway.\n")

    utils.ui_print("\nBatch OCR Options:")
    utils.ui_print("  1. Submit new batch job")
    utils.ui_print("  2. Check job status")
    utils.ui_print("  3. List all batch jobs")
    utils.ui_print("  4. Download batch results")
    utils.ui_print("  0. Cancel\n")

    try:
        choice = input("Select option: ").strip()
    except (KeyboardInterrupt, EOFError):
        return False, "Cancelled"

    if choice == "1":
        batch_file = config.OUTPUT_MD_DIR / "batch_input.jsonl"
        utils.ui_print(f"\nCreating batch file for {len(file_paths)} document(s)...")

        success, batch_path, error = mistral_converter.create_batch_ocr_file(file_paths, batch_file)
        if not success or batch_path is None:
            return False, f"Failed to create batch file: {error}"

        utils.ui_print("Submitting batch job...")
        success, job_id, error = mistral_converter.submit_batch_ocr_job(batch_path)
        if success:
            utils.ui_print(f"\nBatch job submitted: {job_id}")
            utils.ui_print("Use option 2 to check status, option 4 to download results when complete.")
            return True, f"Batch job submitted: {job_id}"
        else:
            return False, f"Failed to submit batch job: {error}"

    elif choice == "2":
        job_id = input("Enter job ID: ").strip()
        if not job_id:
            return False, "No job ID provided"
        if not _validate_job_id(job_id):
            return False, "Invalid job ID format"
        success, status, error = mistral_converter.get_batch_job_status(job_id)
        if success and status is not None:
            utils.ui_print(f"\nJob: {job_id}")
            utils.ui_print(f"  Status: {status['status']}")
            utils.ui_print(f"  Progress: {status['progress_percent']}%")
            utils.ui_print(f"  Succeeded: {status['succeeded_requests']}")
            utils.ui_print(f"  Failed: {status['failed_requests']}")
            return True, f"Job {job_id}: {status['status']}"
        else:
            return False, f"Error: {error}"

    elif choice == "3":
        success, jobs, error = mistral_converter.list_batch_jobs()
        if success and jobs:
            utils.ui_print(f"\n{len(jobs)} batch job(s):\n")
            for job in jobs:
                utils.ui_print(
                    f"  {job['id']} | {job['status']} | {job['total_requests']} requests | {job['created_at']}"
                )
            return True, f"Listed {len(jobs)} batch jobs"
        elif success:
            utils.ui_print("\nNo batch jobs found.")
            return True, "No batch jobs"
        else:
            return False, f"Error: {error}"

    elif choice == "4":
        job_id = input("Enter job ID: ").strip()
        if not job_id:
            return False, "No job ID provided"
        if not _validate_job_id(job_id):
            return False, "Invalid job ID format"
        success, path, error = mistral_converter.download_batch_results(job_id)
        if success:
            utils.ui_print(f"\nResults saved to: {path}")
            return True, f"Results downloaded: {path}"
        else:
            return False, f"Error: {error}"

    return False, "Cancelled"


# ============================================================================
# Mode 7: System Status
# ============================================================================


def mode_system_status() -> Tuple[bool, str]:
    """Display cache statistics and system info (read-only, no side effects)."""
    logger.info("SYSTEM STATUS MODE")

    out = utils.ui_print

    out("\n" + "=" * 60)
    out(f"  ENHANCED DOCUMENT CONVERTER v{config.VERSION} - SYSTEM STATUS")
    out("=" * 60 + "\n")

    out("Configuration:")
    out(f"  * Mistral API Key: {'Set' if config.MISTRAL_API_KEY else 'NOT SET'}")
    llm_status = (
        f"Enabled ({config.MARKITDOWN_LLM_MODEL})"
        if config.MARKITDOWN_ENABLE_LLM_DESCRIPTIONS
        else "Disabled"
    )
    out(f"  * LLM Descriptions: {llm_status}")
    out(f"  * Cache Duration: {config.CACHE_DURATION_HOURS} hours")
    out(f"  * Max Concurrent Files: {config.MAX_CONCURRENT_FILES}")
    out(f"  * Mistral OCR Model: {config.get_ocr_model()}")
    out(f"  * Table Format: {config.MISTRAL_TABLE_FORMAT or 'API default (unset)'}")
    out(f"  * Extract Headers/Footers: {config.MISTRAL_EXTRACT_HEADER}/{config.MISTRAL_EXTRACT_FOOTER}")
    out(f"  * ExifTool: {'Set' if config.MARKITDOWN_EXIFTOOL_PATH else 'Not configured'}")
    out(f"  * Style Map: {'Set' if config.MARKITDOWN_STYLE_MAP else 'Not configured'}")
    out()

    cache_stats = utils.cache.get_statistics()
    out("Cache Statistics:")
    out(f"  Total Entries: {cache_stats['total_entries']}")
    out(f"  Total Size: {cache_stats['total_size_mb']:.2f} MB")
    out(f"  Cache Hits: {cache_stats['cache_hits']}")
    out(f"  Cache Misses: {cache_stats['cache_misses']}")
    out(f"  Hit Rate: {cache_stats['hit_rate']:.1f}%")
    out()

    out("Output Statistics:")
    md_files = list(config.OUTPUT_MD_DIR.glob("*.md"))
    txt_files = list(config.OUTPUT_TXT_DIR.glob("*.txt"))
    image_dirs = list(config.OUTPUT_IMAGES_DIR.glob("*"))
    out(f"  Markdown Files: {len(md_files)}")
    out(f"  Text Files: {len(txt_files)}")
    out(f"  Image Directories: {len(image_dirs)}")
    out()

    input_files = list(config.INPUT_DIR.glob("*.*"))
    out(f"Input Directory: {len([f for f in input_files if f.is_file()])} files ready")
    out()

    out("Configured Mistral Models:")
    key_models = ["mistral-ocr-latest", "pixtral-large-latest", "ministral-8b-latest"]
    for model_id in key_models:
        if model_id in config.MISTRAL_MODELS:
            model_info = config.MISTRAL_MODELS[model_id]
            out(f"  * {model_info['name']}: {model_info['description']}")
    out()

    out("System Recommendations:")
    recommendations = []

    if not config.MISTRAL_API_KEY:
        recommendations.append("! Set MISTRAL_API_KEY to enable OCR features")

    if cache_stats["total_entries"] > 100:
        recommendations.append("* Consider running Maintenance (option 8) to clear old cache entries")

    if not recommendations:
        recommendations.append("  All systems operational")

    for rec in recommendations:
        out(f"  {rec}")

    out("\n" + "=" * 60 + "\n")

    return True, "System status displayed"


def mode_maintenance() -> Tuple[bool, str]:
    """Run maintenance tasks: clear expired cache entries and old uploaded files."""
    logger.info("MAINTENANCE MODE")

    out = utils.ui_print

    out("\n" + "=" * 60)
    out("  MAINTENANCE")
    out("=" * 60 + "\n")

    actions_taken = []

    # 1. Clear expired cache entries
    if config.AUTO_CLEAR_CACHE:
        cleared = utils.cache.clear_old_entries()
        if cleared > 0:
            msg = f"Cleared {cleared} expired cache entries"
            out(f"  ✓ {msg}")
            actions_taken.append(msg)
        else:
            out("  - No expired cache entries to clear")
    else:
        out("  - Cache auto-clear is disabled (AUTO_CLEAR_CACHE=false)")

    # 2. Clean up old uploaded files from Mistral
    if config.CLEANUP_OLD_UPLOADS and config.MISTRAL_API_KEY:
        try:
            client = mistral_converter.get_mistral_client()
            if client:
                deleted = mistral_converter.cleanup_uploaded_files(client)
                if deleted > 0:
                    msg = f"Cleaned up {deleted} old uploaded files from Mistral (>{config.UPLOAD_RETENTION_DAYS} days)"
                    out(f"  ✓ {msg}")
                    actions_taken.append(msg)
                else:
                    out("  - No old uploaded files to clean up")
            else:
                out("  - Mistral client not available")
        except Exception as e:
            logger.debug("Could not clean up uploads: %s", e)
            out(f"  ! Upload cleanup failed: {e}")
    elif not config.MISTRAL_API_KEY:
        out("  - Skipping upload cleanup (no API key)")
    else:
        out("  - Upload cleanup is disabled (CLEANUP_OLD_UPLOADS=false)")

    if not actions_taken:
        out("\n  No maintenance actions were needed.")

    out("\n" + "=" * 60 + "\n")

    summary = "; ".join(actions_taken) if actions_taken else "No actions needed"
    return True, f"Maintenance complete: {summary}"


# ============================================================================
# File Selection
# ============================================================================


def select_files() -> List[Path]:
    """Prompt user to select files from input directory."""
    input_files = _list_input_files()

    out = utils.ui_print

    if not input_files:
        logger.warning("No files found in %s", config.INPUT_DIR)
        out(f"\nNo files found in '{config.INPUT_DIR}'")
        out("Please add files to the input directory and try again.\n")
        return []

    out(f"\nFound {len(input_files)} file(s) in input directory:\n")

    for i, file_path in enumerate(input_files, 1):
        file_size = file_path.stat().st_size / 1024
        out(f"  {i}. {file_path.name} ({file_size:.1f} KB)")

    out(f"\n  {len(input_files) + 1}. Process ALL files")
    out("  0. Cancel\n")

    while True:
        try:
            choice = input("Select file(s) to process (comma-separated or single number): ").strip()

            if choice == "0":
                return []

            if choice == str(len(input_files) + 1):
                return input_files

            indices = [int(c.strip()) for c in choice.split(",")]

            selected = []
            for idx in indices:
                if 1 <= idx <= len(input_files):
                    selected.append(input_files[idx - 1])
                else:
                    utils.ui_print(f"Invalid selection: {idx}")
                    selected = []
                    break

            if selected:
                return selected

        except (ValueError, IndexError):
            utils.ui_print("Invalid input. Please enter numbers separated by commas.\n")
        except (KeyboardInterrupt, EOFError):
            return []


# ============================================================================
# Interactive Menu
# ============================================================================


def show_menu():
    """Display the interactive menu."""
    out = utils.ui_print
    out("\n" + "=" * 60)
    out(f"  ENHANCED DOCUMENT CONVERTER v{config.VERSION}")
    out("=" * 60)
    out("\nSelect conversion mode:\n")
    out("  1. Convert (Smart)")
    out("     Auto-picks best engine per file type")
    out()
    out("  2. Convert (MarkItDown)")
    out("     Force local conversion (no API calls)")
    out()
    out("  3. Convert (Mistral OCR)")
    out("     Force cloud OCR for highest accuracy")
    out()
    out("  4. PDF to Images")
    out("     Render each PDF page to PNG images")
    out()
    out("  5. Document QnA")
    out("     Query documents in natural language")
    out()
    out("  6. Batch OCR (50% savings)")
    out("     Submit batch jobs to Mistral Batch API")
    out()
    out("  7. System Status")
    out("     Cache stats, config info, and diagnostics")
    out()
    out("  8. Maintenance")
    out("     Clear cache, clean up old uploads")
    out()
    out("  0. Exit")
    out("\n" + "=" * 60 + "\n")


# Dispatch table: menu_choice -> (cli_mode_name, handler)
MODE_DISPATCH: Dict[str, Tuple[str, Any]] = {
    "1": ("smart", mode_convert_smart),
    "2": ("markitdown", mode_markitdown_only),
    "3": ("mistral_ocr", mode_mistral_ocr_only),
    "4": ("pdf_to_images", mode_pdf_to_images),
    "5": ("qna", mode_document_qna),
    "6": ("batch_ocr", mode_batch_ocr),
}

# Reverse lookup: cli mode name -> handler
_CLI_MODE_DISPATCH = {cli_name: handler for _, (cli_name, handler) in MODE_DISPATCH.items()}


def interactive_menu():
    """Run the interactive menu loop."""
    while True:
        show_menu()

        try:
            choice = input("Enter your choice (0-8): ").strip()

            if choice == "0":
                utils.ui_print("\nExiting. Goodbye!\n")
                return

            if choice == "7":
                mode_system_status()
                input("\nPress Enter to continue...")
                continue

            if choice == "8":
                mode_maintenance()
                input("\nPress Enter to continue...")
                continue

            if choice not in MODE_DISPATCH:
                utils.ui_print("\nInvalid choice. Please enter a number between 0 and 8.\n")
                continue

            files = select_files()
            if not files:
                continue

            _, (cli_mode, handler) = choice, MODE_DISPATCH[choice]
            valid_files = _filter_valid_files(files, mode=cli_mode)

            if not valid_files:
                utils.ui_print("\nNo valid files to process.\n")
                input("Press Enter to continue...")
                continue

            start_time = time.time()
            success, message = handler(valid_files)
            utils.ui_print(f"\n{message}")

            elapsed = time.time() - start_time
            utils.ui_print(f"Total processing time: {elapsed:.2f} seconds")

            input("\nPress Enter to continue...")

        except KeyboardInterrupt:
            utils.ui_print("\n\nInterrupted. Exiting...\n")
            return

        except Exception as e:
            logger.error("Unexpected error: %s", e)
            utils.ui_print(f"\nError: {e}\n")
            input("Press Enter to continue...")


# ============================================================================
# Command-Line Interface
# ============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description=f"Enhanced Document Converter v{config.VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                     # Interactive menu
  python main.py --mode smart        # Smart auto-routing
  python main.py --mode markitdown   # Force MarkItDown
  python main.py --mode mistral_ocr  # Force Mistral OCR
  python main.py --test              # Test mode
        """,
    )

    parser.add_argument(
        "--mode",
        choices=[
            "smart",
            "markitdown",
            "mistral_ocr",
            "pdf_to_images",
            "maintenance",
            "status",
            "qna",
            "batch_ocr",
        ],
        help="Run specific mode directly",
    )

    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Disable interactive prompts and process all files in input directory",
    )

    parser.add_argument("--test", action="store_true", help="Run in test mode")

    args = parser.parse_args()

    # Print header
    utils.ui_print("\n" + "=" * 60)
    utils.ui_print(f"  Enhanced Document Converter v{config.VERSION}")
    utils.ui_print("  https://github.com/microsoft/markitdown")
    utils.ui_print("  https://docs.mistral.ai/capabilities/document_ai/basic_ocr/")
    utils.ui_print("=" * 60 + "\n")

    # Initialize config (creates directories, validates settings)
    issues = config.initialize()
    if issues:
        for issue in issues:
            utils.ui_print(issue)

    # Wire up file-based processing log if enabled
    if config.SAVE_PROCESSING_LOGS:
        utils.setup_logging(log_file=str(config.LOGS_DIR / "processing.log"))
        utils.ui_print()

    # Test mode
    if args.test:
        logger.info("Running in test mode...")
        mode_system_status()
        return

    # Status mode doesn't need file selection
    if args.mode == "status":
        mode_system_status()
        return

    if args.mode == "maintenance":
        mode_maintenance()
        return

    # Direct mode execution
    if args.mode:
        if args.no_interactive:
            files = _list_input_files()
            if not files:
                utils.ui_print(f"No files found in {config.INPUT_DIR}")
                return
            utils.ui_print(f"Non-interactive mode: Processing {len(files)} files from input directory")
        else:
            files = select_files()
            if not files:
                return

        files = _filter_valid_files(files, mode=args.mode)
        if not files:
            utils.ui_print("No valid files to process.")
            sys.exit(1)

        start_time = time.time()
        handler = _CLI_MODE_DISPATCH.get(args.mode)
        if handler is None:
            utils.ui_print(f"Unknown mode: {args.mode}")
            sys.exit(1)
        success, message = handler(files)
        utils.ui_print(f"\n{message}")

        elapsed = time.time() - start_time
        utils.ui_print(f"\nTotal processing time: {elapsed:.2f} seconds")

        sys.exit(0 if success else 1)

    # Interactive menu
    interactive_menu()


if __name__ == "__main__":
    main()
