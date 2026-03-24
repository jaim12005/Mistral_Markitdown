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
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import config
import utils
import local_converter
import mistral_converter

logger = utils.logger


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

    if len(file_paths) == 1:
        utils.print_progress(1, 1, label)
        result = process_fn(file_paths[0])
        ok = result[0] if isinstance(result, tuple) else result
        if ok:
            successful += 1
        else:
            failed += 1
            err = result[2] if isinstance(result, tuple) and len(result) > 2 else "unknown error"
            logger.error("Failed: %s - %s", file_paths[0].name, err)
        return successful, failed

    with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_FILES) as executor:
        submit_times = {}
        futures = {}
        for fp in file_paths:
            submit_times[fp] = time.time()
            futures[executor.submit(process_fn, fp)] = fp

        for i, future in enumerate(as_completed(futures), 1):
            file_path = futures[future]
            utils.print_progress(i, len(file_paths), label)

            try:
                result = future.result()
                ok = result[0] if isinstance(result, tuple) else result
                if ok:
                    successful += 1
                else:
                    failed += 1
                    err = result[2] if isinstance(result, tuple) and len(result) > 2 else "failed"
                    logger.error("Failed: %s - %s", file_path.name, err)
            except Exception as e:
                failed += 1
                logger.error("Error processing %s: %s", file_path.name, e)

    return successful, failed


# ============================================================================
# Mode 1: Convert (Smart) -- auto-routes by file type
# ============================================================================


def _route_label(ext: str) -> str:
    """Return a human-readable label for the engine that will handle this extension."""
    if ext in config.MISTRAL_OCR_SUPPORTED and config.MISTRAL_API_KEY:
        label = "Mistral OCR"
        if ext == "pdf":
            label += " (+ table extraction)"
        return label
    return "MarkItDown (local)"


def _process_single_smart(file_path: Path) -> Tuple[bool, Optional[Path], Optional[str]]:
    """Process one file with smart routing: OCR-supported -> Mistral, else -> MarkItDown.

    For PDFs, also runs table extraction via pdfplumber/camelot.
    """
    ext = file_path.suffix.lower().lstrip(".")

    # PDF table extraction (runs regardless of OCR engine choice)
    if ext == "pdf":
        try:
            table_result = local_converter.extract_all_tables(file_path)
            if table_result["table_count"] > 0:
                local_converter.save_tables_to_files(file_path, table_result["tables"])
                logger.info(
                    "Extracted %d tables from %s", table_result["table_count"], file_path.name
                )
        except Exception as e:
            logger.warning("Table extraction failed for %s: %s", file_path.name, e)

    # Route to the appropriate engine
    if ext in config.MISTRAL_OCR_SUPPORTED and config.MISTRAL_API_KEY:
        return mistral_converter.convert_with_mistral_ocr(file_path)
    else:
        success, content, error = local_converter.convert_with_markitdown(file_path)
        output_path = config.OUTPUT_MD_DIR / f"{file_path.stem}.md" if success else None
        return success, output_path, error


def mode_convert_smart(file_paths: List[Path]) -> Tuple[bool, str]:
    """
    Smart conversion mode: auto-routes each file to the best engine.

    - Files whose extension is in MISTRAL_OCR_SUPPORTED go to Mistral OCR
    - Everything else goes to MarkItDown (local)
    - PDFs also get table extraction via pdfplumber + camelot
    - Multiple files are processed concurrently

    Prints the routing decision for each file before processing begins.
    """
    logger.info("SMART CONVERT MODE: Processing %d file(s)", len(file_paths))

    if config.MAX_BATCH_FILES > 0 and len(file_paths) > config.MAX_BATCH_FILES:
        return False, (
            f"Batch size ({len(file_paths)}) exceeds MAX_BATCH_FILES ({config.MAX_BATCH_FILES}). "
            "Increase the limit or split into smaller batches."
        )

    # Show routing plan
    print("\nRouting plan:")
    if not config.MISTRAL_API_KEY:
        print("  NOTE: No MISTRAL_API_KEY set. All files will use MarkItDown (local).\n")

    for fp in file_paths:
        ext = fp.suffix.lower().lstrip(".")
        label = _route_label(ext)
        print(f"  {fp.name:<40} -> {label}")
    print()

    successful, failed = _process_files_concurrently(
        file_paths, _process_single_smart, "Converting files"
    )

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

    successful = 0
    failed = 0
    total_pages = 0

    for i, file_path in enumerate(file_paths, 1):
        utils.print_progress(i, len(file_paths), "Converting PDFs")

        if file_path.suffix.lower() != ".pdf":
            logger.warning("Skipping non-PDF file: %s", file_path.name)
            continue

        success, image_paths, error = local_converter.convert_pdf_to_images(file_path)

        if success:
            successful += 1
            total_pages += len(image_paths)
            logger.info("Converted %s to %d images", file_path.name, len(image_paths))
        else:
            failed += 1
            logger.error("Failed: %s - %s", file_path.name, error)

    return failed == 0, f"Converted {successful} PDFs ({total_pages} total pages)"


# ============================================================================
# Mode 5: Document QnA
# ============================================================================


def mode_document_qna(file_paths: List[Path]) -> Tuple[bool, str]:
    """Query a document in natural language using Mistral chat + OCR."""
    logger.info("DOCUMENT QnA MODE: %d file(s) selected", len(file_paths))

    if not config.MISTRAL_API_KEY:
        return False, "Document QnA requires MISTRAL_API_KEY to be set"

    if len(file_paths) != 1:
        print("\nPlease select exactly 1 file to query.\n")
        return False, "Document QnA works on one file at a time"

    file_path = file_paths[0]
    print(f"\nQuerying: {file_path.name}")
    print(f"Model: {config.MISTRAL_DOCUMENT_QNA_MODEL}")
    print("Type 'exit' or 'quit' to return to menu.\n")

    questions_asked = 0
    while True:
        try:
            question = input("Question: ").strip()
            if not question or question.lower() in ("exit", "quit"):
                break

            success, answer, error = mistral_converter.query_document_file(
                file_path, question
            )

            if success:
                print(f"\nAnswer: {answer}\n")
                questions_asked += 1
            else:
                print(f"\nError: {error}\n")

        except KeyboardInterrupt:
            break

    return True, f"Asked {questions_asked} question(s) about {file_path.name}"


# ============================================================================
# Mode 6: Batch OCR (50% cost savings)
# ============================================================================


def mode_batch_ocr(file_paths: List[Path]) -> Tuple[bool, str]:
    """Submit files for batch OCR processing at 50% cost reduction."""
    logger.info("BATCH OCR MODE: %d file(s) selected", len(file_paths))

    if not config.MISTRAL_API_KEY:
        return False, "Batch OCR requires MISTRAL_API_KEY to be set"

    if not config.MISTRAL_BATCH_ENABLED:
        return False, "Batch processing is disabled (set MISTRAL_BATCH_ENABLED=true)"

    if len(file_paths) < config.MISTRAL_BATCH_MIN_FILES:
        print(
            f"\nNote: Batch processing is most cost-effective with {config.MISTRAL_BATCH_MIN_FILES}+ files."
        )
        print(f"You selected {len(file_paths)} file(s). Proceeding anyway.\n")

    print("\nBatch OCR Options:")
    print("  1. Submit new batch job")
    print("  2. Check job status")
    print("  3. List all batch jobs")
    print("  4. Download batch results")
    print("  0. Cancel\n")

    try:
        choice = input("Select option: ").strip()
    except (KeyboardInterrupt, EOFError):
        return False, "Cancelled"

    if choice == "1":
        batch_file = config.OUTPUT_MD_DIR / "batch_input.jsonl"
        print(f"\nCreating batch file for {len(file_paths)} document(s)...")

        success, batch_path, error = mistral_converter.create_batch_ocr_file(
            file_paths, batch_file
        )
        if not success:
            return False, f"Failed to create batch file: {error}"

        print("Submitting batch job...")
        success, job_id, error = mistral_converter.submit_batch_ocr_job(batch_path)
        if success:
            print(f"\nBatch job submitted: {job_id}")
            print("Use option 2 to check status, option 4 to download results when complete.")
            return True, f"Batch job submitted: {job_id}"
        else:
            return False, f"Failed to submit batch job: {error}"

    elif choice == "2":
        job_id = input("Enter job ID: ").strip()
        if not job_id:
            return False, "No job ID provided"
        success, status, error = mistral_converter.get_batch_job_status(job_id)
        if success:
            print(f"\nJob: {job_id}")
            print(f"  Status: {status['status']}")
            print(f"  Progress: {status['progress_percent']}%")
            print(f"  Succeeded: {status['succeeded_requests']}")
            print(f"  Failed: {status['failed_requests']}")
            return True, f"Job {job_id}: {status['status']}"
        else:
            return False, f"Error: {error}"

    elif choice == "3":
        success, jobs, error = mistral_converter.list_batch_jobs()
        if success and jobs:
            print(f"\n{len(jobs)} batch job(s):\n")
            for job in jobs:
                print(f"  {job['id']} | {job['status']} | {job['total_requests']} requests | {job['created_at']}")
            return True, f"Listed {len(jobs)} batch jobs"
        elif success:
            print("\nNo batch jobs found.")
            return True, "No batch jobs"
        else:
            return False, f"Error: {error}"

    elif choice == "4":
        job_id = input("Enter job ID: ").strip()
        if not job_id:
            return False, "No job ID provided"
        success, path, error = mistral_converter.download_batch_results(job_id)
        if success:
            print(f"\nResults saved to: {path}")
            return True, f"Results downloaded: {path}"
        else:
            return False, f"Error: {error}"

    return False, "Cancelled"


# ============================================================================
# Mode 7: System Status
# ============================================================================


def mode_system_status() -> Tuple[bool, str]:
    """Display cache statistics and system info."""
    logger.info("SYSTEM STATUS MODE")

    print("\n" + "=" * 60)
    print(f"  ENHANCED DOCUMENT CONVERTER v{config.VERSION} - SYSTEM STATUS")
    print("=" * 60 + "\n")

    print("Configuration:")
    print(f"  * Mistral API Key: {'Set' if config.MISTRAL_API_KEY else 'NOT SET'}")
    print(f"  * LLM Descriptions: {'Enabled (' + config.MARKITDOWN_LLM_MODEL + ')' if config.MARKITDOWN_ENABLE_LLM_DESCRIPTIONS else 'Disabled'}")
    print(f"  * Cache Duration: {config.CACHE_DURATION_HOURS} hours")
    print(f"  * Max Concurrent Files: {config.MAX_CONCURRENT_FILES}")
    print(f"  * Mistral OCR Model: {config.get_ocr_model()}")
    print(f"  * Table Format: {config.MISTRAL_TABLE_FORMAT or 'markdown (default)'}")
    print(f"  * Extract Headers/Footers: {config.MISTRAL_EXTRACT_HEADER}/{config.MISTRAL_EXTRACT_FOOTER}")
    print(f"  * ExifTool: {'Set' if config.MARKITDOWN_EXIFTOOL_PATH else 'Not configured'}")
    print(f"  * Style Map: {'Set' if config.MARKITDOWN_STYLE_MAP else 'Not configured'}")
    print()

    cache_stats = utils.cache.get_statistics()
    print("Cache Statistics:")
    print(f"  Total Entries: {cache_stats['total_entries']}")
    print(f"  Total Size: {cache_stats['total_size_mb']:.2f} MB")
    print(f"  Cache Hits: {cache_stats['cache_hits']}")
    print(f"  Cache Misses: {cache_stats['cache_misses']}")
    print(f"  Hit Rate: {cache_stats['hit_rate']:.1f}%")
    print()

    print("Output Statistics:")
    md_files = list(config.OUTPUT_MD_DIR.glob("*.md"))
    txt_files = list(config.OUTPUT_TXT_DIR.glob("*.txt"))
    image_dirs = list(config.OUTPUT_IMAGES_DIR.glob("*"))
    print(f"  Markdown Files: {len(md_files)}")
    print(f"  Text Files: {len(txt_files)}")
    print(f"  Image Directories: {len(image_dirs)}")
    print()

    input_files = list(config.INPUT_DIR.glob("*.*"))
    print(f"Input Directory: {len([f for f in input_files if f.is_file()])} files ready")
    print()

    print("Configured Mistral Models:")
    key_models = ["mistral-ocr-latest", "pixtral-large-latest", "ministral-8b-latest"]
    for model_id in key_models:
        if model_id in config.MISTRAL_MODELS:
            model_info = config.MISTRAL_MODELS[model_id]
            print(f"  * {model_info['name']}: {model_info['description']}")
    print()

    print("System Recommendations:")
    recommendations = []

    if not config.MISTRAL_API_KEY:
        recommendations.append("! Set MISTRAL_API_KEY to enable OCR features")

    if cache_stats["total_entries"] > 100:
        recommendations.append("* Consider clearing old cache entries")

    if config.AUTO_CLEAR_CACHE:
        cleared = utils.cache.clear_old_entries()
        if cleared > 0:
            recommendations.append(f"  Cleared {cleared} expired cache entries")

    if config.CLEANUP_OLD_UPLOADS and config.MISTRAL_API_KEY:
        try:
            client = mistral_converter.get_mistral_client()
            if client:
                deleted = mistral_converter.cleanup_uploaded_files(client)
                if deleted > 0:
                    recommendations.append(f"  Cleaned up {deleted} old uploaded files from Mistral")
        except Exception as e:
            logger.debug("Could not clean up uploads: %s", e)

    if not recommendations:
        recommendations.append("  All systems operational")

    for rec in recommendations:
        print(f"  {rec}")

    print("\n" + "=" * 60 + "\n")

    return True, "System status displayed"


# ============================================================================
# File Selection
# ============================================================================


def select_files() -> List[Path]:
    """Prompt user to select files from input directory."""
    input_files = [f for f in config.INPUT_DIR.glob("*.*") if f.is_file()]

    if not input_files:
        logger.warning("No files found in %s", config.INPUT_DIR)
        print(f"\nNo files found in '{config.INPUT_DIR}'")
        print("Please add files to the input directory and try again.\n")
        return []

    print(f"\nFound {len(input_files)} file(s) in input directory:\n")

    for i, file_path in enumerate(input_files, 1):
        file_size = file_path.stat().st_size / 1024
        print(f"  {i}. {file_path.name} ({file_size:.1f} KB)")

    print(f"\n  {len(input_files) + 1}. Process ALL files")
    print("  0. Cancel\n")

    while True:
        try:
            choice = input(
                "Select file(s) to process (comma-separated or single number): "
            ).strip()

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
                    print(f"Invalid selection: {idx}")
                    selected = []
                    break

            if selected:
                return selected

        except (ValueError, IndexError):
            print("Invalid input. Please enter numbers separated by commas.\n")


# ============================================================================
# Interactive Menu
# ============================================================================


def show_menu():
    """Display the interactive menu."""
    print("\n" + "=" * 60)
    print(f"  ENHANCED DOCUMENT CONVERTER v{config.VERSION}")
    print("=" * 60)
    print("\nSelect conversion mode:\n")
    print("  1. Convert (Smart)")
    print("     Auto-picks best engine per file type")
    print()
    print("  2. Convert (MarkItDown)")
    print("     Force local conversion (no API calls)")
    print()
    print("  3. Convert (Mistral OCR)")
    print("     Force cloud OCR for highest accuracy")
    print()
    print("  4. PDF to Images")
    print("     Render each PDF page to PNG images")
    print()
    print("  5. Document QnA")
    print("     Query documents in natural language")
    print()
    print("  6. Batch OCR (50% savings)")
    print("     Submit batch jobs to Mistral Batch API")
    print()
    print("  7. System Status")
    print("     Cache stats, config info, and diagnostics")
    print()
    print("  0. Exit")
    print("\n" + "=" * 60 + "\n")


# Dispatch table: menu_choice -> (cli_mode_name, handler)
MODE_DISPATCH: Dict[str, Tuple[str, Any]] = {
    "1": ("smart",        mode_convert_smart),
    "2": ("markitdown",   mode_markitdown_only),
    "3": ("mistral_ocr",  mode_mistral_ocr_only),
    "4": ("pdf_to_images", mode_pdf_to_images),
    "5": ("qna",          mode_document_qna),
    "6": ("batch_ocr",    mode_batch_ocr),
}

# Reverse lookup: cli mode name -> handler
_CLI_MODE_DISPATCH = {cli_name: handler for _, (cli_name, handler) in MODE_DISPATCH.items()}


def interactive_menu():
    """Run the interactive menu loop."""
    while True:
        show_menu()

        try:
            choice = input("Enter your choice (0-7): ").strip()

            if choice == "0":
                print("\nExiting. Goodbye!\n")
                return

            if choice == "7":
                mode_system_status()
                input("\nPress Enter to continue...")
                continue

            if choice not in MODE_DISPATCH:
                print("\nInvalid choice. Please enter a number between 0 and 7.\n")
                continue

            files = select_files()
            if not files:
                continue

            valid_files = [f for f in files if utils.validate_file(f)[0]]
            for f in files:
                is_valid, error = utils.validate_file(f)
                if not is_valid:
                    logger.warning(error)

            if not valid_files:
                print("\nNo valid files to process.\n")
                input("Press Enter to continue...")
                continue

            start_time = time.time()
            _, handler = MODE_DISPATCH[choice]
            success, message = handler(valid_files)
            print(f"\n{message}")

            elapsed = time.time() - start_time
            print(f"Total processing time: {elapsed:.2f} seconds")

            input("\nPress Enter to continue...")

        except KeyboardInterrupt:
            print("\n\nInterrupted. Exiting...\n")
            return

        except Exception as e:
            logger.error("Unexpected error: %s", e)
            print(f"\nError: {e}\n")
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
            "status",
            "qna",
            "batch_ocr",
        ],
        help="Run specific mode directly",
    )

    parser.add_argument(
        "--no-interactive", action="store_true",
        help="Disable interactive prompts and process all files in input directory",
    )

    parser.add_argument("--test", action="store_true", help="Run in test mode")

    args = parser.parse_args()

    # Print header
    print("\n" + "=" * 60)
    print(f"  Enhanced Document Converter v{config.VERSION}")
    print("  https://github.com/microsoft/markitdown")
    print("  https://docs.mistral.ai/capabilities/document_ai/basic_ocr/")
    print("=" * 60 + "\n")

    # Initialize config (creates directories, validates settings)
    issues = config.initialize()
    if issues:
        for issue in issues:
            print(issue)
        print()

    # Test mode
    if args.test:
        logger.info("Running in test mode...")
        mode_system_status()
        return

    # Direct mode execution
    if args.mode:
        if args.no_interactive:
            input_files = [f for f in config.INPUT_DIR.glob("*.*") if f.is_file()]
            if not input_files:
                print(f"No files found in {config.INPUT_DIR}")
                return
            files = input_files
            print(f"Non-interactive mode: Processing {len(files)} files from input directory")
        else:
            files = select_files()
            if not files:
                return

        start_time = time.time()
        all_success = True

        if args.mode == "status":
            mode_system_status()
        elif args.mode in _CLI_MODE_DISPATCH:
            handler = _CLI_MODE_DISPATCH[args.mode]
            success, message = handler(files)
            print(f"\n{message}")
            all_success = success
        else:
            print(f"Unknown mode: {args.mode}")
            all_success = False

        elapsed = time.time() - start_time
        print(f"\nTotal processing time: {elapsed:.2f} seconds")

        sys.exit(0 if all_success else 1)

    # Interactive menu
    interactive_menu()


if __name__ == "__main__":
    main()
