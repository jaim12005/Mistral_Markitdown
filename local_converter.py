"""
Enhanced Document Converter v2.1.1 - Local Conversion Module

This module handles MarkItDown integration, PDF table extraction using pdfplumber
and camelot, and PDF to image conversion.

Documentation references:
- MarkItDown: https://github.com/microsoft/markitdown
- Camelot: https://camelot-py.readthedocs.io/
- pdf2image: https://github.com/Belval/pdf2image
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import sys

try:
    from markitdown import MarkItDown
except ImportError:
    MarkItDown = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import camelot
except ImportError:
    camelot = None

try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None

import config
import utils

logger = utils.logger

# ============================================================================
# MarkItDown Integration
# ============================================================================

@lru_cache(maxsize=1)
def get_markitdown_instance() -> Optional[MarkItDown]:
    """
    Create and configure a MarkItDown instance.

    Returns:
        Configured MarkItDown instance or None if unavailable
    """
    if MarkItDown is None:
        logger.error("MarkItDown not installed. Install with: pip install markitdown")
        return None

    try:
        # Configure MarkItDown based on settings
        md_kwargs = {
            "enable_plugins": config.MARKITDOWN_ENABLE_PLUGINS,
        }

        # Add LLM configuration if enabled
        if config.MARKITDOWN_USE_LLM and config.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                llm_client = OpenAI(api_key=config.OPENAI_API_KEY)
                md_kwargs["llm_client"] = llm_client
                md_kwargs["llm_model"] = config.MARKITDOWN_LLM_MODEL
            except ImportError:
                logger.warning("OpenAI package not installed. LLM features disabled.")

        return MarkItDown(**md_kwargs)

    except Exception as e:
        logger.error(f"Error initializing MarkItDown: {e}")
        return None

def convert_with_markitdown(file_path: Path) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Convert a file using MarkItDown.

    Args:
        file_path: Path to file to convert

    Returns:
        Tuple of (success, markdown_content, error_message)
    """
    md = get_markitdown_instance()
    if md is None:
        return False, None, "MarkItDown not available"

    try:
        logger.info(f"Converting with MarkItDown: {file_path.name}")

        # Convert the file
        result = md.convert(str(file_path))

        if result and hasattr(result, 'text_content'):
            markdown_content = result.text_content

            # Extract document metadata if available
            doc_metadata = {
                "file_size_bytes": file_path.stat().st_size,
                "file_extension": file_path.suffix.lower(),
            }
            
            # Try to extract document properties from MarkItDown result
            if hasattr(result, 'metadata') and result.metadata:
                metadata = result.metadata
                if isinstance(metadata, dict):
                    # Add common document properties
                    for key in ['title', 'author', 'subject', 'creator', 'producer',
                               'created', 'modified', 'pages', 'words']:
                        if key in metadata and metadata[key]:
                            doc_metadata[f"doc_{key}"] = metadata[key]
            
            # If no title in metadata, use filename
            if 'doc_title' not in doc_metadata:
                doc_metadata['doc_title'] = file_path.stem

            # Add YAML frontmatter with enriched metadata
            frontmatter = utils.generate_yaml_frontmatter(
                title=doc_metadata.get('doc_title', file_path.stem),
                file_name=file_path.name,
                conversion_method="MarkItDown",
                additional_fields=doc_metadata
            )

            full_content = frontmatter + markdown_content

            # Save output
            output_path = config.OUTPUT_MD_DIR / f"{file_path.stem}.md"
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(full_content)

            # Save text version
            utils.save_text_output(output_path, full_content)

            logger.info(f"Saved: {output_path.name}")
            return True, full_content, None

        else:
            return False, None, "No content returned from MarkItDown"

    except Exception as e:
        logger.error(f"Error converting with MarkItDown: {e}")
        return False, None, str(e)

# ============================================================================
# PDF Table Extraction
# ============================================================================

def extract_tables_pdfplumber(pdf_path: Path) -> List[List[List[str]]]:
    """
    Extract tables from PDF using pdfplumber.

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of tables (each table is a list of rows)
    """
    if pdfplumber is None:
        logger.warning("pdfplumber not installed")
        return []

    tables = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                page_tables = page.extract_tables()

                if page_tables:
                    for table in page_tables:
                        if table and len(table) > 0:
                            tables.append(table)
                            logger.debug(f"Found table on page {page_num + 1} ({len(table)} rows)")

    except Exception as e:
        logger.error(f"Error extracting tables with pdfplumber: {e}")

    return tables

def extract_tables_camelot(
    pdf_path: Path,
    flavor: str = "lattice"
) -> List[List[List[str]]]:
    """
    Extract tables from PDF using camelot with tuned parameters for financial documents.

    Args:
        pdf_path: Path to PDF file
        flavor: Extraction flavor ('lattice' or 'stream')

    Returns:
        List of tables (each table is a list of rows)
    """
    if camelot is None:
        logger.warning("camelot not installed")
        return []

    tables = []

    try:
        # Extract tables with camelot using tuned parameters
        if flavor == "lattice":
            # Lattice mode: better for tables with clear grid lines
            # Tuned for wide financial tables (e.g., trial balances with many columns)
            table_list = camelot.read_pdf(
                str(pdf_path),
                pages='all',
                flavor='lattice',
                suppress_stdout=True,
                line_scale=40,  # Increase to detect more subtle grid lines
                shift_text=['l', 't'],  # Shift text left and top for better alignment
                strip_text=' \n',  # Strip whitespace and newlines from cells
            )
        else:
            # Stream mode: better for tables without clear grid lines
            table_list = camelot.read_pdf(
                str(pdf_path),
                pages='all',
                flavor='stream',
                suppress_stdout=True,
                edge_tol=50,  # Tolerance for detecting table edges
                row_tol=5,  # Tolerance for detecting rows
                column_tol=5,  # Tolerance for detecting columns
            )

        for table in table_list:
            # Quality filtering - skip low-accuracy tables
            if hasattr(table, 'accuracy') and table.accuracy < config.CAMELOT_MIN_ACCURACY:
                logger.debug(
                    f"Skipping low-accuracy table: {table.accuracy:.1f}% "
                    f"(threshold: {config.CAMELOT_MIN_ACCURACY}%)"
                )
                continue
            
            # Whitespace filtering - skip tables with too much empty space
            if hasattr(table, 'whitespace') and table.whitespace > config.CAMELOT_MAX_WHITESPACE:
                logger.debug(
                    f"Skipping high-whitespace table: {table.whitespace:.1f}% "
                    f"(threshold: {config.CAMELOT_MAX_WHITESPACE}%)"
                )
                continue
            
            # Convert DataFrame to list of lists
            table_data = table.df.values.tolist()

            if table_data and len(table_data) > 0:
                # Post-process: fix merged currency cells
                table_data = _fix_merged_currency_cells(table_data)
                tables.append(table_data)
                
                # Log quality metrics
                quality_info = ""
                if hasattr(table, 'accuracy'):
                    quality_info += f" (accuracy: {table.accuracy:.1f}%"
                if hasattr(table, 'whitespace'):
                    quality_info += f", whitespace: {table.whitespace:.1f}%)"
                else:
                    quality_info += ")" if quality_info else ""
                
                logger.debug(f"Camelot extracted table with {len(table_data)} rows{quality_info}")

    except Exception as e:
        logger.error(f"Error extracting tables with camelot ({flavor}): {e}")

    return tables

def _fix_merged_currency_cells(table: List[List[str]]) -> List[List[str]]:
    """
    Fix cells where multiple currency values are merged into one cell.

    Example: "$ 1,234.56 $ 5,678.90" should be split into two cells.

    This commonly happens when Camelot misses a column boundary between
    the last two columns (e.g., December and Current Balance).

    Args:
        table: Table as list of rows

    Returns:
        Fixed table with currency cells properly split
    """
    import re

    # Pattern to detect multiple currency values in one cell
    # Matches: "$ 1,234.56 $ 5,678.90" or "$ (1,234.56) $ (5,678.90)"
    double_currency_pattern = re.compile(
        r'(\$\s*[\(\-]?[\d,]+\.?\d*[\)]?)\s+(\$\s*[\(\-]?[\d,]+\.?\d*[\)]?)'
    )

    fixed_table = []

    for row in table:
        fixed_row = []
        for cell in row:
            if not cell or not isinstance(cell, str):
                fixed_row.append(cell)
                continue

            # Check if this cell contains two currency values
            match = double_currency_pattern.search(cell)

            if match:
                # Split on the second $ sign
                parts = cell.split('$')
                if len(parts) >= 3:  # First element is before first $, rest after
                    # Reconstruct as two separate cells
                    first_value = '$' + parts[1].strip()
                    second_value = '$' + parts[2].strip()
                    fixed_row.append(first_value)
                    fixed_row.append(second_value)
                    logger.debug(f"Split merged currency cell: '{cell}' → '{first_value}' + '{second_value}'")
                else:
                    fixed_row.append(cell)
            else:
                fixed_row.append(cell)

        fixed_table.append(fixed_row)

    return fixed_table

def extract_all_tables(pdf_path: Path) -> Dict[str, Any]:
    """
    Extract tables from PDF using all available methods.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Dictionary with extracted tables and metadata
    """
    logger.info(f"Extracting tables from: {pdf_path.name}")

    result = {
        "tables": [],
        "table_count": 0,
        "methods_used": [],
    }

    # Try pdfplumber first (faster)
    pdfplumber_tables = extract_tables_pdfplumber(pdf_path)
    if pdfplumber_tables:
        result["tables"].extend(pdfplumber_tables)
        result["methods_used"].append("pdfplumber")

    # Try camelot lattice mode (requires Ghostscript)
    camelot_lattice_tables = extract_tables_camelot(pdf_path, flavor="lattice")
    if camelot_lattice_tables:
        result["tables"].extend(camelot_lattice_tables)
        result["methods_used"].append("camelot-lattice")

    # Try camelot stream mode
    camelot_stream_tables = extract_tables_camelot(pdf_path, flavor="stream")
    if camelot_stream_tables:
        result["tables"].extend(camelot_stream_tables)
        result["methods_used"].append("camelot-stream")

    # Remove duplicate tables (simple check by row count)
    result["tables"] = _deduplicate_tables(result["tables"])

    # Coalesce tables with identical headers across pages
    # This merges tables that were split across PDF pages
    original_count = len(result["tables"])
    result["tables"] = coalesce_tables(result["tables"])
    coalesced_count = original_count - len(result["tables"])

    if coalesced_count > 0:
        logger.info(f"Coalesced {coalesced_count} split table(s) across pages")

    result["table_count"] = len(result["tables"])

    logger.info(f"Extracted {result['table_count']} unique tables using {result['methods_used']}")

    return result

def _deduplicate_tables(tables: List[List[List[str]]]) -> List[List[List[str]]]:
    """
    Remove duplicate tables based on size and first row.

    Args:
        tables: List of tables

    Returns:
        Deduplicated list of tables
    """
    seen = set()
    unique_tables = []

    for table in tables:
        if not table:
            continue

        # Create signature: row count + first row content
        signature = (len(table), str(table[0]) if table else "")

        if signature not in seen:
            seen.add(signature)
            unique_tables.append(table)

    return unique_tables

def save_tables_to_files(
    pdf_path: Path,
    tables: List[List[List[str]]]
) -> List[Path]:
    """
    Save extracted tables to multiple output formats.

    Creates:
    - <name>_tables_all.md: All tables
    - <name>_table_N.csv: Individual table CSVs

    Args:
        pdf_path: Original PDF path
        tables: List of extracted tables

    Returns:
        List of created file paths
    """
    if not tables:
        return []

    created_files = []
    base_name = pdf_path.stem

    # Save all tables as markdown
    md_path = config.OUTPUT_MD_DIR / f"{base_name}_tables_all.md"

    frontmatter = utils.generate_yaml_frontmatter(
        title=f"Tables from {pdf_path.name}",
        file_name=pdf_path.name,
        conversion_method="Table Extraction (Enhanced)",
        additional_fields={"table_count": len(tables)}
    )

    md_content = frontmatter + f"\n# Tables Extracted from {pdf_path.name}\n\n"
    md_content += f"**Total tables found:** {len(tables)}\n\n"

    for i, table in enumerate(tables, 1):
        md_content += f"## Table {i}\n\n"

        # Normalize headers and clean the table
        headers, data_rows = utils.normalize_table_headers(table)

        if headers and data_rows:
            md_content += utils.format_table_to_markdown(data_rows, headers=headers)
        else:
            # Fallback if normalization fails
            md_content += utils.format_table_to_markdown(table)

        md_content += "\n\n---\n\n"

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    created_files.append(md_path)
    logger.info(f"Saved: {md_path.name}")

    # Save text version
    utils.save_text_output(md_path, md_content)

    # Save as CSV if requested
    if "csv" in config.TABLE_OUTPUT_FORMATS:
        for i, table in enumerate(tables, 1):
            csv_path = config.OUTPUT_MD_DIR / f"{base_name}_table_{i}.csv"

            try:
                import csv

                # Normalize headers for CSV as well
                headers, data_rows = utils.normalize_table_headers(table)

                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)

                    # Write header row
                    if headers:
                        writer.writerow(headers)

                    # Write data rows
                    if data_rows:
                        writer.writerows(data_rows)

                created_files.append(csv_path)
                logger.debug(f"Saved: {csv_path.name}")

            except Exception as e:
                logger.error(f"Error saving CSV: {e}")

    return created_files

# ============================================================================
# PDF to Images
# ============================================================================

def convert_pdf_to_images(
    pdf_path: Path,
    output_dir: Optional[Path] = None,
    dpi: Optional[int] = None
) -> Tuple[bool, List[Path], Optional[str]]:
    """
    Convert PDF pages to PNG/JPEG images using pdf2image.

    Args:
        pdf_path: Path to PDF file
        output_dir: Optional output directory (default: output_images/<pdf_name>_pages/)
        dpi: Image resolution (default: from config)

    Returns:
        Tuple of (success, list_of_image_paths, error_message)
    """
    if convert_from_path is None:
        return False, [], "pdf2image not installed"

    try:
        # Set output directory
        if output_dir is None:
            output_dir = config.OUTPUT_IMAGES_DIR / f"{pdf_path.stem}_pages"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Use config defaults if not specified
        if dpi is None:
            dpi = config.PDF_IMAGE_DPI

        logger.info(f"Converting PDF to images: {pdf_path.name} (DPI: {dpi}, Format: {config.PDF_IMAGE_FORMAT})")

        # Configure poppler path for Windows
        poppler_path = config.POPPLER_PATH if sys.platform == "win32" else None

        # Build conversion parameters
        convert_params = {
            'pdf_path': str(pdf_path),
            'dpi': dpi,
            'output_folder': str(output_dir),
            'fmt': config.PDF_IMAGE_FORMAT,
            'poppler_path': poppler_path,
            'thread_count': config.PDF_IMAGE_THREAD_COUNT,
            'use_pdftocairo': config.PDF_IMAGE_USE_PDFTOCAIRO,
        }

        # Convert PDF to images
        images = convert_from_path(**convert_params)

        # Save images
        image_paths = []
        file_extension = 'jpg' if config.PDF_IMAGE_FORMAT == 'jpeg' else config.PDF_IMAGE_FORMAT
        
        for i, image in enumerate(images, 1):
            image_path = output_dir / f"page_{i:03d}.{file_extension}"
            
            # Save with format-specific options
            if config.PDF_IMAGE_FORMAT == 'jpeg':
                image.save(str(image_path), 'JPEG', quality=85, optimize=True, progressive=True)
            elif config.PDF_IMAGE_FORMAT == 'png':
                image.save(str(image_path), 'PNG', optimize=True)
            else:
                image.save(str(image_path), config.PDF_IMAGE_FORMAT.upper())
            
            image_paths.append(image_path)
            logger.debug(f"Saved page {i} to {image_path.name}")

        logger.info(f"Converted {len(image_paths)} pages to {config.PDF_IMAGE_FORMAT.upper()} images")
        return True, image_paths, None

    except Exception as e:
        error_msg = f"Error converting PDF to images: {e}"
        logger.error(error_msg)
        return False, [], error_msg

# ============================================================================
# Table Coalescing (Merge tables across pages)
# ============================================================================

def coalesce_tables(tables: List[List[List[str]]]) -> List[List[List[str]]]:
    """
    Merge tables with identical headers across pages.

    Args:
        tables: List of tables

    Returns:
        Coalesced list of tables
    """
    if not tables:
        return []

    coalesced = []
    current_table = None
    current_header = None

    for table in tables:
        if not table or len(table) < 1:
            continue

        # Assume first row is header
        header = tuple(table[0])

        if current_header == header:
            # Same header, append rows (skip header row)
            if current_table is not None:
                current_table.extend(table[1:])
        else:
            # New table
            if current_table is not None:
                coalesced.append(current_table)

            current_table = list(table)  # Copy
            current_header = header

    # Add last table
    if current_table is not None:
        coalesced.append(current_table)

    logger.info(f"Coalesced {len(tables)} tables into {len(coalesced)} tables")

    return coalesced

# ============================================================================
# File Type Detection
# ============================================================================

def analyze_file_content(file_path: Path) -> Dict[str, Any]:
    """
    Analyze file to determine optimal processing strategy.

    Args:
        file_path: Path to file

    Returns:
        Dictionary with content analysis
    """
    analysis = {
        "file_type": file_path.suffix.lower().lstrip('.'),
        "file_size_mb": file_path.stat().st_size / (1024 * 1024),
        "has_images": False,
        "has_code": False,
        "is_complex": False,
        "page_count": 0,
        "is_text_based": False,  # NEW: Can we extract text directly?
        "has_tables": False,      # NEW: Contains tables
    }

    # PDF-specific analysis
    if analysis["file_type"] == "pdf" and pdfplumber is not None:
        try:
            with pdfplumber.open(file_path) as pdf:
                analysis["page_count"] = len(pdf.pages)

                # Check first page for content type
                first_page = pdf.pages[0] if pdf.pages else None
                if first_page:
                    # Check if text-based (can extract text directly)
                    text = first_page.extract_text()
                    analysis["is_text_based"] = bool(text and len(text.strip()) > 50)

                    # Check for tables
                    tables = first_page.extract_tables()
                    analysis["has_tables"] = bool(tables)

                # Check for images in first few pages
                for page in pdf.pages[:min(3, len(pdf.pages))]:
                    if page.images:
                        analysis["has_images"] = True
                        break

                # Complex if: multi-page with images OR text-based but lots of tables
                analysis["is_complex"] = (
                    (analysis["page_count"] > 5 and analysis["has_images"]) or
                    (analysis["has_tables"] and not analysis["is_text_based"])
                )

        except Exception as e:
            logger.debug(f"Error analyzing PDF: {e}")

    # Image files
    elif analysis["file_type"] in config.IMAGE_EXTENSIONS:
        analysis["has_images"] = True

    # Large files are complex
    if analysis["file_size_mb"] > 10:
        analysis["is_complex"] = True

    return analysis
