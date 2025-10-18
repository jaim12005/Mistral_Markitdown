"""
Enhanced Document Converter v2.1 - Main Application

Interactive CLI for document conversion with 8 conversion modes:
1. HYBRID Mode - Intelligent combined processing
2. ENHANCED BATCH - Maximum performance batch processing
3. MarkItDown Only - Fast local conversion
4. Mistral OCR Only - High accuracy OCR
5. Transcription - Audio/video transcription
6. Standard Batch - Simple batch processing
7. Convert PDFs to Images - Page rendering
8. Show System Status - Cache and performance metrics

Usage:
    python main.py                      # Interactive menu
    python main.py --mode hybrid        # Direct mode execution
    python main.py --test               # Test mode

Documentation references:
- MarkItDown: https://github.com/microsoft/markitdown
- Mistral OCR: https://docs.mistral.ai/capabilities/document_ai/basic_ocr/
"""

import argparse
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

    results = []
    has_errors = False

    # Analyze file content to optimize processing strategy
    content_analysis = local_converter.analyze_file_content(file_path)

    logger.info(
        f"Content Analysis: text_based={content_analysis.get('is_text_based')}, "
        f"has_tables={content_analysis.get('has_tables')}, "
        f"pages={content_analysis.get('page_count')}"
    )

    # Step 1: MarkItDown conversion
    logger.info("Step 1/3: Converting with MarkItDown...")
    md_success, md_content, md_error = local_converter.convert_with_markitdown(file_path)

    if md_success:
        results.append("MarkItDown conversion successful")
    else:
        results.append(f"MarkItDown failed: {md_error}")
        has_errors = True

    # Step 2: Extract tables (PDF only)
    tables_extracted = []
    table_count = 0
    if file_path.suffix.lower() == '.pdf':
        logger.info("Step 2/3: Extracting PDF tables...")
        table_result = local_converter.extract_all_tables(file_path)
        table_count = table_result["table_count"]

        if table_count > 0:
            table_files = local_converter.save_tables_to_files(file_path, table_result["tables"])
            results.append(f"Extracted {table_count} tables")
            tables_extracted = table_result["tables"]
        else:
            results.append("No tables found")
    else:
        results.append("Table extraction skipped (not a PDF)")

    # Step 3: Mistral OCR
    # Mistral OCR works on ALL PDFs (both scanned and text-based)
    # It achieves ~95% accuracy across diverse document types
    ocr_quality = None
    ocr_path = None

    if not config.MISTRAL_API_KEY:
        logger.info("Step 3/3: Skipped (no Mistral API key)")
        results.append("Mistral OCR skipped (no API key)")
    else:
        logger.info("Step 3/3: Processing with Mistral OCR...")
        ocr_success, ocr_path, ocr_error = mistral_converter.convert_with_mistral_ocr(file_path)

        if ocr_success and ocr_path:
            # Load OCR result to assess quality (informational only)
            try:
                # Read the OCR metadata if it exists
                ocr_json_path = config.OUTPUT_MD_DIR / f"{file_path.stem}_ocr_metadata.json"
                if ocr_json_path.exists():
                    import json
                    with open(ocr_json_path, 'r', encoding='utf-8') as f:
                        ocr_result = json.load(f)
                    ocr_quality = mistral_converter.assess_ocr_quality(ocr_result)

                    results.append(f"Mistral OCR successful (quality: {ocr_quality['quality_score']:.0f}/100)")

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

    # Combine results
    logger.info("Combining results into hybrid output...")

    # Build data quality summary
    quality_summary = "## Data Quality Summary\n\n"
    quality_summary += f"**File Analysis:**\n"
    quality_summary += f"- Document type: {content_analysis.get('file_type', 'unknown').upper()}\n"
    quality_summary += f"- Has text layer: {'Yes' if content_analysis.get('is_text_based') else 'No'}\n"
    quality_summary += f"- Page count: {content_analysis.get('page_count', 'N/A')}\n"
    quality_summary += f"- File size: {content_analysis.get('file_size_mb', 0):.2f} MB\n\n"

    quality_summary += f"**Processing Results:**\n"
    for result in results:
        quality_summary += f"- {result}\n"
    quality_summary += "\n"

    if ocr_quality:
        quality_summary += f"**OCR Quality Details:**\n"
        quality_summary += f"- Quality score: {ocr_quality['quality_score']:.1f}/100\n"
        quality_summary += f"- Usable: {'Yes' if ocr_quality['is_usable'] else 'No'}\n"
        quality_summary += f"- Weak pages: {ocr_quality['weak_page_count']}/{ocr_quality['total_page_count']}\n"
        if ocr_quality['issues']:
            quality_summary += f"- Issues: {', '.join(ocr_quality['issues'])}\n"
        quality_summary += "\n"

    quality_summary += "---\n\n"

    # Create combined output with frontmatter
    combined_frontmatter = utils.generate_yaml_frontmatter(
        title=f"Combined Analysis: {file_path.name}",
        file_name=file_path.name,
        conversion_method="Hybrid Mode (MarkItDown + Tables + Mistral OCR)",
        additional_fields={
            "text_based": content_analysis.get('is_text_based'),
            "tables_extracted": table_count,
            "ocr_used": ocr_path is not None,
            "ocr_quality_score": ocr_quality['quality_score'] if ocr_quality else None,
        }
    )

    combined_content = combined_frontmatter + f"\n# Combined Analysis: {file_path.name}\n\n"

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
            combined_content += f"**OCR Quality Score: {ocr_quality['quality_score']:.1f}/100**\n\n"

            if not ocr_quality["is_usable"]:
                # Prominent warning for low-quality OCR
                combined_content += "⚠️ **Quality Warning**: OCR quality is below the recommended threshold.\n\n"
                combined_content += "**Detected Issues:**\n"
                for issue in ocr_quality['issues']:
                    combined_content += f"- {issue}\n"
                combined_content += "\n**Recommendation**: For this text-based PDF, prioritize the 'Extracted Tables' "
                combined_content += "and 'MarkItDown Conversion' sections above for higher accuracy.\n\n"
                combined_content += f"**Detailed Metrics**: {ocr_quality['weak_page_count']}/{ocr_quality['total_page_count']} "
                combined_content += f"weak pages, {ocr_quality['digit_count']} digits extracted, "
                combined_content += f"{ocr_quality['uniqueness_ratio']:.1%} content uniqueness\n\n"
                combined_content += "---\n\n"
            else:
                combined_content += f"✓ OCR quality is good. Extracted content from {ocr_quality['total_page_count']} page(s).\n\n"

        try:
            with open(ocr_path, 'r', encoding='utf-8') as f:
                ocr_content = f.read()

            # Strip both YAML frontmatter AND markdown headers from OCR file
            ocr_content = utils.strip_yaml_frontmatter(ocr_content)

            # Remove the main title (# OCR Result: ...)
            import re
            ocr_content = re.sub(r'^#\s+OCR Result:.*?\n+', '', ocr_content, flags=re.MULTILINE)

            # Remove section headers that duplicate our structure (## Full Text, ## OCR Content, ## Page-by-Page Content)
            ocr_content = re.sub(r'^##\s+(Full Text|OCR Content.*?|Page-by-Page Content)\n+', '', ocr_content, flags=re.MULTILINE)

            combined_content += ocr_content.strip()
        except Exception as e:
            logger.warning(f"Could not read OCR content: {e}")
            combined_content += "*OCR content available in separate file*\n"
        combined_content += "\n\n---\n\n"

    # Save combined output
    combined_path = config.OUTPUT_MD_DIR / f"{file_path.stem}_combined.md"

    with open(combined_path, 'w', encoding='utf-8') as f:
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
        futures = {
            executor.submit(mode_hybrid, fp): fp
            for fp in file_paths
        }

        for i, future in enumerate(as_completed(futures), 1):
            file_path = futures[future]
            start_time = time.time()

            utils.print_progress(i, len(file_paths), "Processing files")

            try:
                success, message = future.result()
                processing_time = time.time() - start_time

                if success:
                    successful += 1
                    metadata.add_file(file_path.name, "success", processing_time)
                else:
                    failed += 1
                    metadata.add_file(file_path.name, "failed", processing_time, error=message)

            except Exception as e:
                processing_time = time.time() - start_time
                failed += 1
                metadata.add_file(file_path.name, "failed", processing_time, error=str(e))
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

        success, output_path, error = mistral_converter.convert_with_mistral_ocr(file_path)

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
            # Save with _transcription suffix
            output_path = config.OUTPUT_MD_DIR / f"{file_path.stem}_transcription.md"

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            utils.save_text_output(output_path, content)

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
        ext = file_path.suffix.lower().lstrip('.')

        if ext in config.MISTRAL_OCR_SUPPORTED:
            success, _, error = mistral_converter.convert_with_mistral_ocr(file_path, use_cache=True, improve_weak=False)
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

        if file_path.suffix.lower() != '.pdf':
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

    print("\n" + "="*60)
    print("  ENHANCED DOCUMENT CONVERTER v2.1 - SYSTEM STATUS")
    print("="*60 + "\n")

    # Configuration Status
    print("Configuration:")
    print(f"  * Mistral API Key: {'Set' if config.MISTRAL_API_KEY else 'NOT SET'}")
    print(f"  * OpenAI API Key: {'Set' if config.OPENAI_API_KEY else 'Not set'}")
    print(f"  * Cache Duration: {config.CACHE_DURATION_HOURS} hours")
    print(f"  * Max Concurrent Files: {config.MAX_CONCURRENT_FILES}")
    print(f"  * Mistral OCR Model: {config.MISTRAL_OCR_MODEL}")
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
    print(f"Input Directory: {len([f for f in input_files if f.is_file()])} files ready")
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

    if cache_stats['total_entries'] > 100:
        recommendations.append("💡 Consider clearing old cache entries")

    if config.AUTO_CLEAR_CACHE:
        cleared = utils.cache.clear_old_entries()
        if cleared > 0:
            recommendations.append(f"✓ Cleared {cleared} expired cache entries")

    if not recommendations:
        recommendations.append("✓ All systems operational")

    for rec in recommendations:
        print(f"  {rec}")

    print("\n" + "="*60 + "\n")

    return True, "System status displayed"

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
            choice = input("Select file(s) to process (comma-separated or single number): ").strip()

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
    print("\n" + "="*60)
    print("  ENHANCED DOCUMENT CONVERTER v2.1")
    print("="*60)
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
    print("  0. Exit")
    print("\n" + "="*60 + "\n")

def interactive_menu():
    """Run the interactive menu loop."""
    while True:
        show_menu()

        try:
            choice = input("Enter your choice (0-8): ").strip()

            if choice == "0":
                print("\nExiting. Goodbye!\n")
                sys.exit(0)

            elif choice == "8":
                mode_system_status()
                input("\nPress Enter to continue...")
                continue

            elif choice in ["1", "2", "3", "4", "5", "6", "7"]:
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

                elapsed = time.time() - start_time
                print(f"Total processing time: {elapsed:.2f} seconds")

                input("\nPress Enter to continue...")

            else:
                print("\nInvalid choice. Please enter a number between 0 and 8.\n")

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
        description="Enhanced Document Converter v2.1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Interactive menu
  python main.py --mode hybrid      # Run hybrid mode
  python main.py --test             # Test mode
        """
    )

    parser.add_argument(
        "--mode",
        choices=["hybrid", "enhanced_batch", "markitdown", "mistral_ocr", "transcription", "batch", "pdf_to_images", "status"],
        help="Run specific mode directly"
    )

    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Disable interactive prompts"
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode"
    )

    args = parser.parse_args()

    # Print header
    print("\n" + "="*60)
    print("  Enhanced Document Converter v2.1")
    print("  https://github.com/microsoft/markitdown")
    print("  https://docs.mistral.ai/capabilities/document_ai/basic_ocr/")
    print("="*60 + "\n")

    # Show configuration issues
    issues = config.validate_configuration()
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
        files = select_files()
        if not files:
            return

        mode_map = {
            "hybrid": lambda: [mode_hybrid(f) for f in files],
            "enhanced_batch": lambda: [mode_enhanced_batch(files)],
            "markitdown": lambda: [mode_markitdown_only(files)],
            "mistral_ocr": lambda: [mode_mistral_ocr_only(files)],
            "transcription": lambda: [mode_transcription(files)],
            "batch": lambda: [mode_standard_batch(files)],
            "pdf_to_images": lambda: [mode_pdf_to_images(files)],
            "status": lambda: [mode_system_status()],
        }

        mode_map[args.mode]()
        return

    # Interactive menu
    interactive_menu()

if __name__ == "__main__":
    main()
