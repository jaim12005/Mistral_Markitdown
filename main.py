"""
Enhanced Document Converter - Main Application

Interactive CLI for document conversion with 10 conversion modes:
1. HYBRID Mode - Intelligent combined processing
2. ENHANCED BATCH - Maximum performance batch processing
3. MarkItDown Only - Fast local conversion
4. Mistral OCR Only - High accuracy OCR
5. Transcription - Audio/video transcription
6. Standard Batch - Simple batch processing
7. Convert PDFs to Images - Page rendering
8. Show System Status - Cache and performance metrics
9. Document QnA - Query documents in natural language
10. Batch OCR Processing - 50% cost reduction batch jobs

Usage:
    python main.py                      # Interactive menu
    python main.py --mode hybrid        # Direct mode execution
    python main.py --test               # Test mode

Documentation references:
- MarkItDown: https://github.com/microsoft/markitdown
- Mistral OCR: https://docs.mistral.ai/capabilities/document_ai/basic_ocr/
"""

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple

import config
import utils
import local_converter
import mistral_converter

logger = utils.logger

# ============================================================================
# Mode 1: HYBRID Mode (Intelligent Processing)
# ============================================================================


def mode_hybrid(file_path: Path) -> Tuple[bool, str]:
    """
    HYBRID mode: Combines MarkItDown + Mistral OCR for optimal results.

    For PDFs:
    - MarkItDown text content
    - Extracted tables (pdfplumber + camelot)
    - Full OCR analysis from Mistral (ALWAYS runs for comprehensive analysis)
    - Quality assessment to identify OCR issues
    - Creates <name>_combined.md with all results and quality metrics

    Args:
        file_path: Path to file

    Returns:
        Tuple of (success, message)
    """
    logger.info(f"HYBRID MODE: Processing {file_path.name}")

    # Initialize all variables at function start to avoid scope issues
    results: List[str] = []
    has_errors: bool = False
    tables_extracted: List[List[List[str]]] = []
    table_count: int = 0
    ocr_result: Optional[dict] = None  # Initialize to avoid UnboundLocalError
    ocr_quality: Optional[dict] = None
    ocr_path: Optional[Path] = None
    md_success: bool = False
    md_content: Optional[str] = None
    md_error: Optional[str] = None

    # Analyze file content to optimize processing strategy
    content_analysis = local_converter.analyze_file_content(file_path)

    logger.info(
        f"Content Analysis: text_based={content_analysis.get('is_text_based')}, "
        f"has_tables={content_analysis.get('has_tables')}, "
        f"pages={content_analysis.get('page_count')}"
    )

    # Step 1: MarkItDown conversion
    logger.info("Step 1/3: Converting with MarkItDown...")
    md_success, md_content, md_error = local_converter.convert_with_markitdown(
        file_path
    )

    if md_success:
        results.append("MarkItDown conversion successful")
    else:
        results.append(f"MarkItDown failed: {md_error}")
        has_errors = True

    # Step 2: Extract tables (PDF only)
    if file_path.suffix.lower() == ".pdf":
        logger.info("Step 2/3: Extracting PDF tables...")
        table_result = local_converter.extract_all_tables(file_path)
        table_count = table_result["table_count"]

        if table_count > 0:
            # Save tables to files and use the result for better logging
            saved_table_files = local_converter.save_tables_to_files(
                file_path, table_result["tables"]
            )
            results.append(
                f"Extracted {table_count} tables to {len(saved_table_files)} files"
            )
            tables_extracted = table_result["tables"]
        else:
            results.append("No tables found")
    else:
        results.append("Table extraction skipped (not a PDF)")

    # Step 3: Mistral OCR
    # Mistral OCR works on ALL PDFs (both scanned and text-based)
    # It achieves ~95% accuracy across diverse document types
    ext = file_path.suffix.lower().lstrip(".")
    is_ocr_supported = ext in config.MISTRAL_OCR_SUPPORTED

    if not config.MISTRAL_API_KEY:
        logger.info("Step 3/3: Skipped (no Mistral API key)")
        results.append("Mistral OCR skipped (no API key)")
    elif not is_ocr_supported:
        logger.info(f"Step 3/3: Skipped (file type .{ext} not supported by Mistral OCR)")
        results.append(f"Mistral OCR skipped (.{ext} not supported)")
    else:
        logger.info("Step 3/3: Processing with Mistral OCR...")
        ocr_success, ocr_path, ocr_error = mistral_converter.convert_with_mistral_ocr(
            file_path
        )

        if ocr_success and ocr_path:
            # Load OCR result to assess quality (informational only)
            try:
                # Read the OCR metadata if it exists
                ocr_json_path = (
                    config.OUTPUT_MD_DIR / f"{file_path.stem}_ocr_metadata.json"
                )
                if ocr_json_path.exists() and config.ENABLE_OCR_QUALITY_ASSESSMENT:
                    with open(ocr_json_path, "r", encoding="utf-8") as f:
                        ocr_result = json.load(f)
                    ocr_quality = mistral_converter.assess_ocr_quality(ocr_result)

                    results.append(
                        f"Mistral OCR successful (quality: {ocr_quality['quality_score']:.0f}/100)"
                    )

                    # Note: We keep the OCR in the output even if quality is low
                    # Mistral OCR is designed to work on all PDFs and users paid for it
                    if not ocr_quality["is_usable"]:
                        logger.warning(
                            f"OCR quality score is low ({ocr_quality['quality_score']:.0f}/100). "
                            f"Issues: {', '.join(ocr_quality['issues'])}"
                        )
                else:
                    results.append("Mistral OCR successful")
            except Exception as e:
                logger.warning(f"Could not assess OCR quality: {e}")
                results.append("Mistral OCR successful")
        else:
            results.append(f"Mistral OCR failed: {ocr_error}")
            has_errors = True

    # NOTE: Weak page improvement is now handled entirely within the
    # convert_with_mistral_ocr pipeline via _process_ocr_result_pipeline.
    # The pipeline already: (1) assesses quality, (2) improves weak pages,
    # (3) re-assesses, and (4) saves updated results to disk.
    # Re-running improve_weak_pages here would trigger redundant API calls
    # without persisting the results - so we skip it.

    # Combine results
    logger.info("Combining results into hybrid output...")

    # Build data quality summary
    quality_summary = "## Data Quality Summary\n\n"
    quality_summary += f"**File Analysis:**\n"
    quality_summary += (
        f"- Document type: {content_analysis.get('file_type', 'unknown').upper()}\n"
    )
    quality_summary += f"- Has text layer: {'Yes' if content_analysis.get('is_text_based') else 'No'}\n"
    quality_summary += f"- Page count: {content_analysis.get('page_count', 'N/A')}\n"
    quality_summary += (
        f"- File size: {content_analysis.get('file_size_mb', 0):.2f} MB\n\n"
    )

    quality_summary += f"**Processing Results:**\n"
    for result in results:
        quality_summary += f"- {result}\n"
    quality_summary += "\n"

    if ocr_quality:
        quality_summary += f"**OCR Quality Details:**\n"
        quality_summary += f"- Quality score: {ocr_quality['quality_score']:.1f}/100\n"
        quality_summary += f"- Usable: {'Yes' if ocr_quality['is_usable'] else 'No'}\n"
        quality_summary += f"- Weak pages: {ocr_quality['weak_page_count']}/{ocr_quality['total_page_count']}\n"
        if ocr_quality["issues"]:
            quality_summary += f"- Issues: {', '.join(ocr_quality['issues'])}\n"
        quality_summary += "\n"

    quality_summary += "---\n\n"

    # Create combined output with frontmatter
    combined_frontmatter = utils.generate_yaml_frontmatter(
        title=f"Combined Analysis: {file_path.name}",
        file_name=file_path.name,
        conversion_method="Hybrid Mode (MarkItDown + Tables + Mistral OCR)",
        additional_fields={
            "text_based": content_analysis.get("is_text_based"),
            "tables_extracted": table_count,
            "ocr_used": ocr_path is not None,
            "ocr_quality_score": ocr_quality["quality_score"] if ocr_quality else None,
        },
    )

    combined_content = (
        combined_frontmatter + f"\n# Combined Analysis: {file_path.name}\n\n"
    )

    # Add quality summary FIRST
    combined_content += quality_summary

    # PRIORITY ORDER: Tables > MarkItDown > OCR (only if high quality)

    # Add extracted tables FIRST (highest priority for structured data)
    if tables_extracted:
        combined_content += f"## Extracted Tables ({len(tables_extracted)} total)\n\n"
        combined_content += "**High-quality structured data extracted from PDF:**\n\n"
        combined_content += f"See `{file_path.stem}_tables_all.md` for the full table extraction with all {len(tables_extracted)} tables.\n\n"
        combined_content += "---\n\n"

    # Add MarkItDown content (useful for prose/text, not tables)
    if md_success and md_content:
        combined_content += "## MarkItDown Conversion\n\n"
        combined_content += "*Note: MarkItDown may flatten table structures. Refer to 'Extracted Tables' above for structured data.*\n\n"
        combined_content += utils.strip_yaml_frontmatter(md_content)
        combined_content += "\n\n---\n\n"

    # Add Mistral OCR Analysis
    # Mistral OCR works on all PDFs (both scanned and text-based) with ~95% accuracy
    if ocr_path and ocr_path.exists():
        combined_content += "## Mistral OCR Analysis\n\n"

        # Add quality assessment banner
        if ocr_quality:
            combined_content += (
                f"**OCR Quality Score: {ocr_quality['quality_score']:.1f}/100**\n\n"
            )

            if not ocr_quality["is_usable"]:
                # Prominent warning for low-quality OCR
                combined_content += "⚠️ **Quality Warning**: OCR quality is below the recommended threshold.\n\n"
                combined_content += "**Detected Issues:**\n"
                for issue in ocr_quality["issues"]:
                    combined_content += f"- {issue}\n"
                combined_content += "\n**Recommendation**: For this text-based PDF, prioritize the 'Extracted Tables' "
                combined_content += "and 'MarkItDown Conversion' sections above for higher accuracy.\n\n"
                combined_content += f"**Detailed Metrics**: {ocr_quality['weak_page_count']}/{ocr_quality['total_page_count']} "
                combined_content += (
                    f"weak pages, {ocr_quality['digit_count']} digits extracted, "
                )
                combined_content += (
                    f"{ocr_quality['uniqueness_ratio']:.1%} content uniqueness\n\n"
                )
                combined_content += "---\n\n"
            else:
                combined_content += f"✓ OCR quality is good. Extracted content from {ocr_quality['total_page_count']} page(s).\n\n"

        try:
            with open(ocr_path, "r", encoding="utf-8") as f:
                ocr_content = f.read()

            # Strip both YAML frontmatter AND markdown headers from OCR file
            ocr_content = utils.strip_yaml_frontmatter(ocr_content)

            # Remove the main title (# OCR Result: ...)
            ocr_content = re.sub(
                r"^#\s+OCR Result:.*?\n+", "", ocr_content, flags=re.MULTILINE
            )

            # Remove section headers that duplicate our structure (## Full Text, ## OCR Content, ## Page-by-Page Content)
            ocr_content = re.sub(
                r"^##\s+(Full Text|OCR Content.*?|Page-by-Page Content)\n+",
                "",
                ocr_content,
                flags=re.MULTILINE,
            )

            combined_content += ocr_content.strip()
        except Exception as e:
            logger.warning(f"Could not read OCR content: {e}")
            combined_content += "*OCR content available in separate file*\n"
        combined_content += "\n\n---\n\n"

    # Save combined output
    combined_path = config.OUTPUT_MD_DIR / f"{file_path.stem}_combined.md"

    with open(combined_path, "w", encoding="utf-8") as f:
        f.write(combined_content)

    utils.save_text_output(combined_path, combined_content)

    logger.info(f"Saved curated combined output: {combined_path.name}")

    status = "completed with warnings" if has_errors else "completed successfully"
    return not has_errors, f"HYBRID mode {status}"


# ============================================================================
# Mode 2: ENHANCED BATCH (Maximum Performance)
# ============================================================================


def mode_enhanced_batch(file_paths: List[Path]) -> Tuple[bool, str]:
    """
    ENHANCED BATCH mode: Concurrent processing with caching and metadata.

    Args:
        file_paths: List of files to process

    Returns:
        Tuple of (success, message)
    """
    logger.info(f"ENHANCED BATCH MODE: Processing {len(file_paths)} files")

    metadata = utils.MetadataTracker()
    successful = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_FILES) as executor:
        # Record submission time per file for accurate timing
        submit_times = {}
        futures = {}
        for fp in file_paths:
            submit_times[fp] = time.time()
            future = executor.submit(mode_hybrid, fp)
            futures[future] = fp

        for i, future in enumerate(as_completed(futures), 1):
            file_path = futures[future]

            utils.print_progress(i, len(file_paths), "Processing files")

            try:
                success, message = future.result()
                processing_time = time.time() - submit_times[file_path]

                if success:
                    successful += 1
                    metadata.add_file(file_path.name, "success", processing_time)
                else:
                    failed += 1
                    metadata.add_file(
                        file_path.name, "failed", processing_time, error=message
                    )

            except Exception as e:
                processing_time = time.time() - submit_times[file_path]
                failed += 1
                metadata.add_file(
                    file_path.name, "failed", processing_time, error=str(e)
                )
                logger.error(f"Error processing {file_path.name}: {e}")

    # Save metadata
    if config.ENABLE_BATCH_METADATA:
        metadata_path = metadata.save()
        logger.info(f"Saved batch metadata: {metadata_path.name}")

    return failed == 0, f"Processed {successful}/{len(file_paths)} files successfully"


# ============================================================================
# Mode 3: MarkItDown Only
# ============================================================================


def mode_markitdown_only(file_paths: List[Path]) -> Tuple[bool, str]:
    """
    MarkItDown Only mode: Fast local conversion without API calls.

    Args:
        file_paths: List of files to process

    Returns:
        Tuple of (success, message)
    """
    logger.info(f"MARKITDOWN ONLY MODE: Processing {len(file_paths)} files")

    successful = 0
    failed = 0

    for i, file_path in enumerate(file_paths, 1):
        utils.print_progress(i, len(file_paths), "Processing files")

        success, content, error = local_converter.convert_with_markitdown(file_path)

        if success:
            successful += 1
        else:
            failed += 1
            logger.error(f"Failed: {file_path.name} - {error}")

    return failed == 0, f"Processed {successful}/{len(file_paths)} files successfully"


# ============================================================================
# Mode 4: Mistral OCR Only
# ============================================================================


def mode_mistral_ocr_only(file_paths: List[Path]) -> Tuple[bool, str]:
    """
    Mistral OCR Only mode: High accuracy OCR with Mistral AI.

    Args:
        file_paths: List of files to process

    Returns:
        Tuple of (success, message)
    """
    logger.info(f"MISTRAL OCR ONLY MODE: Processing {len(file_paths)} files")

    successful = 0
    failed = 0

    for i, file_path in enumerate(file_paths, 1):
        utils.print_progress(i, len(file_paths), "Processing files")

        success, output_path, error = mistral_converter.convert_with_mistral_ocr(
            file_path
        )

        if success:
            successful += 1
        else:
            failed += 1
            logger.error(f"Failed: {file_path.name} - {error}")

    return failed == 0, f"Processed {successful}/{len(file_paths)} files successfully"


# ============================================================================
# Mode 5: Transcription (Audio/Video)
# ============================================================================


def mode_transcription(file_paths: List[Path]) -> Tuple[bool, str]:
    """
    Transcription mode: Audio/video transcription using MarkItDown plugins.

    Note: Requires MarkItDown plugins to be installed and enabled.

    Args:
        file_paths: List of audio/video files

    Returns:
        Tuple of (success, message)
    """
    logger.info(f"TRANSCRIPTION MODE: Processing {len(file_paths)} files")

    if not config.MARKITDOWN_ENABLE_PLUGINS:
        return False, "Transcription requires MARKITDOWN_ENABLE_PLUGINS=true"

    # Use MarkItDown with plugins enabled
    successful = 0
    failed = 0

    for i, file_path in enumerate(file_paths, 1):
        utils.print_progress(i, len(file_paths), "Transcribing files")

        success, content, error = local_converter.convert_with_markitdown(file_path)

        if success:
            # Rename the default output to _transcription suffix
            default_path = config.OUTPUT_MD_DIR / f"{file_path.stem}.md"
            transcription_path = config.OUTPUT_MD_DIR / f"{file_path.stem}_transcription.md"

            if default_path.exists():
                default_path.rename(transcription_path)
            else:
                with open(transcription_path, "w", encoding="utf-8") as f:
                    f.write(content)

            # Also rename .txt output if it exists
            default_txt = config.OUTPUT_TXT_DIR / f"{file_path.stem}.txt"
            transcription_txt = config.OUTPUT_TXT_DIR / f"{file_path.stem}_transcription.txt"
            if default_txt.exists():
                default_txt.rename(transcription_txt)

            successful += 1
            logger.info(f"Transcribed: {file_path.name}")
        else:
            failed += 1
            logger.error(f"Failed: {file_path.name} - {error}")

    return failed == 0, f"Transcribed {successful}/{len(file_paths)} files successfully"


# ============================================================================
# Mode 6: Standard Batch Process
# ============================================================================


def mode_standard_batch(file_paths: List[Path]) -> Tuple[bool, str]:
    """
    Standard Batch mode: Simple batch processing by file type.

    Args:
        file_paths: List of files to process

    Returns:
        Tuple of (success, message)
    """
    logger.info(f"STANDARD BATCH MODE: Processing {len(file_paths)} files")

    successful = 0
    failed = 0

    for i, file_path in enumerate(file_paths, 1):
        utils.print_progress(i, len(file_paths), "Processing files")

        # Determine processing method based on file type
        ext = file_path.suffix.lower().lstrip(".")

        if ext in config.MISTRAL_OCR_SUPPORTED:
            success, _, error = mistral_converter.convert_with_mistral_ocr(
                file_path, use_cache=True, improve_weak=False
            )
        else:
            success, _, error = local_converter.convert_with_markitdown(file_path)

        if success:
            successful += 1
        else:
            failed += 1
            logger.error(f"Failed: {file_path.name} - {error}")

    return failed == 0, f"Processed {successful}/{len(file_paths)} files successfully"


# ============================================================================
# Mode 7: Convert PDFs to Images
# ============================================================================


def mode_pdf_to_images(file_paths: List[Path]) -> Tuple[bool, str]:
    """
    PDF to Images mode: Render each PDF page to PNG.

    Args:
        file_paths: List of PDF files

    Returns:
        Tuple of (success, message)
    """
    logger.info(f"PDF TO IMAGES MODE: Converting {len(file_paths)} PDFs")

    successful = 0
    failed = 0
    total_pages = 0

    for i, file_path in enumerate(file_paths, 1):
        utils.print_progress(i, len(file_paths), "Converting PDFs")

        if file_path.suffix.lower() != ".pdf":
            logger.warning(f"Skipping non-PDF file: {file_path.name}")
            continue

        success, image_paths, error = local_converter.convert_pdf_to_images(file_path)

        if success:
            successful += 1
            total_pages += len(image_paths)
            logger.info(f"Converted {file_path.name} to {len(image_paths)} images")
        else:
            failed += 1
            logger.error(f"Failed: {file_path.name} - {error}")

    return failed == 0, f"Converted {successful} PDFs ({total_pages} total pages)"


# ============================================================================
# Mode 8: Show System Status
# ============================================================================


def mode_system_status() -> Tuple[bool, str]:
    """
    System Status mode: Display cache statistics and system info.

    Returns:
        Tuple of (success, message)
    """
    logger.info("SYSTEM STATUS MODE")

    print("\n" + "=" * 60)
    print(f"  ENHANCED DOCUMENT CONVERTER v{config.VERSION} - SYSTEM STATUS")
    print("=" * 60 + "\n")

    # Configuration Status
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

    # Cache Statistics
    cache_stats = utils.cache.get_statistics()
    print("Cache Statistics:")
    print(f"  Total Entries: {cache_stats['total_entries']}")
    print(f"  Total Size: {cache_stats['total_size_mb']:.2f} MB")
    print(f"  Cache Hits: {cache_stats['cache_hits']}")
    print(f"  Cache Misses: {cache_stats['cache_misses']}")
    print(f"  Hit Rate: {cache_stats['hit_rate']:.1f}%")
    print()

    # Directory Statistics
    print("Output Statistics:")
    md_files = list(config.OUTPUT_MD_DIR.glob("*.md"))
    txt_files = list(config.OUTPUT_TXT_DIR.glob("*.txt"))
    image_dirs = list(config.OUTPUT_IMAGES_DIR.glob("*"))

    print(f"  Markdown Files: {len(md_files)}")
    print(f"  Text Files: {len(txt_files)}")
    print(f"  Image Directories: {len(image_dirs)}")
    print()

    # Input Files
    input_files = list(config.INPUT_DIR.glob("*.*"))
    print(
        f"Input Directory: {len([f for f in input_files if f.is_file()])} files ready"
    )
    print()

    # Model Information
    print("Configured Mistral Models:")
    # Show the primary OCR model and a few other notable models
    key_models = ["mistral-ocr-latest", "pixtral-large-latest", "ministral-8b-latest"]
    for model_id in key_models:
        if model_id in config.MISTRAL_MODELS:
            model_info = config.MISTRAL_MODELS[model_id]
            print(f"  * {model_info['name']}: {model_info['description']}")
    print()

    # System Recommendations
    print("System Recommendations:")
    recommendations = []

    if not config.MISTRAL_API_KEY:
        recommendations.append("⚠ Set MISTRAL_API_KEY to enable OCR features")

    if cache_stats["total_entries"] > 100:
        recommendations.append("💡 Consider clearing old cache entries")

    if config.AUTO_CLEAR_CACHE:
        cleared = utils.cache.clear_old_entries()
        if cleared > 0:
            recommendations.append(f"✓ Cleared {cleared} expired cache entries")

    # Clean up old uploaded files from Mistral
    if config.CLEANUP_OLD_UPLOADS and config.MISTRAL_API_KEY:
        try:
            client = mistral_converter.get_mistral_client()
            if client:
                deleted = mistral_converter.cleanup_uploaded_files(client)
                if deleted > 0:
                    recommendations.append(f"✓ Cleaned up {deleted} old uploaded files from Mistral")
        except Exception as e:
            logger.debug(f"Could not clean up uploads: {e}")

    if not recommendations:
        recommendations.append("✓ All systems operational")

    for rec in recommendations:
        print(f"  {rec}")

    print("\n" + "=" * 60 + "\n")

    return True, "System status displayed"


# ============================================================================
# Mode 9: Document QnA
# ============================================================================


def mode_document_qna(file_paths: List[Path]) -> Tuple[bool, str]:
    """
    Document QnA mode: Query documents in natural language.

    Args:
        file_paths: List of files to query

    Returns:
        Tuple of (success, message)
    """
    logger.info(f"DOCUMENT QnA MODE: {len(file_paths)} file(s) selected")

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
# Mode 10: Batch OCR Management
# ============================================================================


def mode_batch_ocr(file_paths: List[Path]) -> Tuple[bool, str]:
    """
    Batch OCR mode: Submit files for batch processing at 50% cost reduction.

    Args:
        file_paths: List of files to process

    Returns:
        Tuple of (success, message)
    """
    logger.info(f"BATCH OCR MODE: {len(file_paths)} file(s) selected")

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
        # Submit new batch job
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
# File Selection
# ============================================================================


def select_files() -> List[Path]:
    """
    Prompt user to select files from input directory.

    Returns:
        List of selected file paths
    """
    input_files = [f for f in config.INPUT_DIR.glob("*.*") if f.is_file()]

    if not input_files:
        logger.warning(f"No files found in {config.INPUT_DIR}")
        print(f"\nNo files found in '{config.INPUT_DIR}'")
        print("Please add files to the input directory and try again.\n")
        return []

    print(f"\nFound {len(input_files)} file(s) in input directory:\n")

    for i, file_path in enumerate(input_files, 1):
        file_size = file_path.stat().st_size / 1024  # KB
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

            # Check for "all" option
            if choice == str(len(input_files) + 1):
                return input_files

            # Parse comma-separated choices
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
    print("  1. HYBRID Mode (Intelligent Processing)")
    print("     Combines MarkItDown + Mistral OCR for optimal results")
    print()
    print("  2. ENHANCED BATCH (Maximum Performance)")
    print("     Concurrent processing with caching and metadata")
    print()
    print("  3. MarkItDown Only (Fast, Local)")
    print("     Local conversion without API calls")
    print()
    print("  4. Mistral OCR Only (High Accuracy)")
    print("     High-accuracy OCR using Mistral AI")
    print()
    print("  5. Transcription (Audio/Video)")
    print("     Audio/video transcription (requires plugins)")
    print()
    print("  6. Standard Batch Process")
    print("     Simple batch processing by file type")
    print()
    print("  7. Convert PDFs to Images")
    print("     Render each PDF page to PNG images")
    print()
    print("  8. Show System Status")
    print("     Display cache statistics and system info")
    print()
    print("  9. Document QnA (NEW)")
    print("     Query documents in natural language")
    print()
    print("  10. Batch OCR Processing (NEW)")
    print("      Submit batch jobs at 50% cost reduction")
    print()
    print("  0. Exit")
    print("\n" + "=" * 60 + "\n")


def interactive_menu():
    """Run the interactive menu loop."""
    while True:
        show_menu()

        try:
            choice = input("Enter your choice (0-10): ").strip()

            if choice == "0":
                print("\nExiting. Goodbye!\n")
                sys.exit(0)

            elif choice == "8":
                mode_system_status()
                input("\nPress Enter to continue...")
                continue

            elif choice in ["1", "2", "3", "4", "5", "6", "7", "9", "10"]:
                files = select_files()

                if not files:
                    continue

                # Validate files
                valid_files = []
                for file_path in files:
                    is_valid, error = utils.validate_file(file_path)
                    if is_valid:
                        valid_files.append(file_path)
                    else:
                        logger.warning(error)

                if not valid_files:
                    print("\nNo valid files to process.\n")
                    input("Press Enter to continue...")
                    continue

                # Execute selected mode
                start_time = time.time()

                if choice == "1":
                    for file_path in valid_files:
                        success, message = mode_hybrid(file_path)
                        print(f"\n{message}")

                elif choice == "2":
                    success, message = mode_enhanced_batch(valid_files)
                    print(f"\n{message}")

                elif choice == "3":
                    success, message = mode_markitdown_only(valid_files)
                    print(f"\n{message}")

                elif choice == "4":
                    success, message = mode_mistral_ocr_only(valid_files)
                    print(f"\n{message}")

                elif choice == "5":
                    success, message = mode_transcription(valid_files)
                    print(f"\n{message}")

                elif choice == "6":
                    success, message = mode_standard_batch(valid_files)
                    print(f"\n{message}")

                elif choice == "7":
                    success, message = mode_pdf_to_images(valid_files)
                    print(f"\n{message}")

                elif choice == "9":
                    success, message = mode_document_qna(valid_files)
                    print(f"\n{message}")

                elif choice == "10":
                    success, message = mode_batch_ocr(valid_files)
                    print(f"\n{message}")

                elapsed = time.time() - start_time
                print(f"Total processing time: {elapsed:.2f} seconds")

                input("\nPress Enter to continue...")

            else:
                print("\nInvalid choice. Please enter a number between 0 and 10.\n")

        except KeyboardInterrupt:
            print("\n\nInterrupted. Exiting...\n")
            sys.exit(0)

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
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
  python main.py                    # Interactive menu
  python main.py --mode hybrid      # Run hybrid mode
  python main.py --test             # Test mode
        """,
    )

    parser.add_argument(
        "--mode",
        choices=[
            "hybrid",
            "enhanced_batch",
            "markitdown",
            "mistral_ocr",
            "transcription",
            "batch",
            "pdf_to_images",
            "status",
            "qna",
            "batch_ocr",
        ],
        help="Run specific mode directly",
    )

    parser.add_argument(
        "--no-interactive", action="store_true", help="Disable interactive prompts and process all files in input directory"
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
        # Handle non-interactive mode
        if args.no_interactive:
            # Process all files in input directory
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

        # Execute mode and collect results
        start_time = time.time()
        all_success = True

        if args.mode == "hybrid":
            # Process each file individually and report results
            for file_path in files:
                success, message = mode_hybrid(file_path)
                print(f"  {file_path.name}: {message}")
                if not success:
                    all_success = False
        elif args.mode == "enhanced_batch":
            success, message = mode_enhanced_batch(files)
            print(f"\n{message}")
            all_success = success
        elif args.mode == "markitdown":
            success, message = mode_markitdown_only(files)
            print(f"\n{message}")
            all_success = success
        elif args.mode == "mistral_ocr":
            success, message = mode_mistral_ocr_only(files)
            print(f"\n{message}")
            all_success = success
        elif args.mode == "transcription":
            success, message = mode_transcription(files)
            print(f"\n{message}")
            all_success = success
        elif args.mode == "batch":
            success, message = mode_standard_batch(files)
            print(f"\n{message}")
            all_success = success
        elif args.mode == "pdf_to_images":
            success, message = mode_pdf_to_images(files)
            print(f"\n{message}")
            all_success = success
        elif args.mode == "qna":
            success, message = mode_document_qna(files)
            print(f"\n{message}")
            all_success = success
        elif args.mode == "batch_ocr":
            success, message = mode_batch_ocr(files)
            print(f"\n{message}")
            all_success = success
        elif args.mode == "status":
            mode_system_status()

        elapsed = time.time() - start_time
        print(f"\nTotal processing time: {elapsed:.2f} seconds")

        # Exit with appropriate code
        sys.exit(0 if all_success else 1)

    # Interactive menu
    interactive_menu()


if __name__ == "__main__":
    main()
