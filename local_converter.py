"""
Enhanced Document Converter - Local Conversion Module

This module handles MarkItDown integration, PDF table extraction using pdfplumber
and camelot, and PDF to image conversion.

Documentation references:
- MarkItDown: https://github.com/microsoft/markitdown
- Camelot: https://camelot-py.readthedocs.io/
- pdf2image: https://github.com/Belval/pdf2image
"""

import csv
import re
import sys
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

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

_MARKITDOWN_UNSET = object()  # sentinel: init never attempted
_markitdown_instance = _MARKITDOWN_UNSET
_markitdown_lock = threading.Lock()


def get_markitdown_instance() -> Optional[MarkItDown]:
    """
    Create and configure a MarkItDown instance (thread-safe).

    Uses a module-level cache protected by a lock so concurrent threads
    in batch processing don't race on initialization.  A failed init is
    remembered (instance set to ``None``) so subsequent calls return
    immediately without retrying or logging duplicate errors.
    """
    global _markitdown_instance

    cached = _markitdown_instance
    if cached is not _MARKITDOWN_UNSET:
        return cached  # either a live instance or None (failed init)

    with _markitdown_lock:
        if _markitdown_instance is not _MARKITDOWN_UNSET:
            return _markitdown_instance

        if MarkItDown is None:
            logger.error("MarkItDown not installed. Install with: pip install markitdown")
            _markitdown_instance = None
            return None

        try:
            md_kwargs = {
                "enable_plugins": config.MARKITDOWN_ENABLE_PLUGINS,
                "enable_builtins": config.MARKITDOWN_ENABLE_BUILTINS,
            }

            if config.MARKITDOWN_KEEP_DATA_URIS:
                md_kwargs["keep_data_uris"] = True

            if config.MARKITDOWN_ENABLE_LLM_DESCRIPTIONS and config.MISTRAL_API_KEY:
                try:
                    from openai import OpenAI
                    llm_client = OpenAI(
                        api_key=config.MISTRAL_API_KEY,
                        base_url="https://api.mistral.ai/v1"
                    )
                    md_kwargs["llm_client"] = llm_client
                    md_kwargs["llm_model"] = config.MARKITDOWN_LLM_MODEL
                except ImportError:
                    logger.warning("OpenAI package not installed. LLM image descriptions disabled.")

            if config.MARKITDOWN_LLM_PROMPT:
                md_kwargs["llm_prompt"] = config.MARKITDOWN_LLM_PROMPT

            if config.MARKITDOWN_STYLE_MAP:
                md_kwargs["style_map"] = config.MARKITDOWN_STYLE_MAP

            if config.MARKITDOWN_EXIFTOOL_PATH:
                md_kwargs["exiftool_path"] = config.MARKITDOWN_EXIFTOOL_PATH

            _markitdown_instance = MarkItDown(**md_kwargs)
            return _markitdown_instance

        except Exception as e:
            logger.error("Error initializing MarkItDown: %s", e)
            _markitdown_instance = None  # remember the failure
            return None


def reset_markitdown_instance():
    """Reset the cached MarkItDown instance so the next call retries initialization."""
    global _markitdown_instance
    with _markitdown_lock:
        _markitdown_instance = _MARKITDOWN_UNSET

def convert_with_markitdown(file_path: Path) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Convert a file using MarkItDown.

    Args:
        file_path: Path to file to convert

    Returns:
        Tuple of (success, markdown_content, error_message)
    """
    # Enforce file size limit
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    if file_size_mb > config.MARKITDOWN_MAX_FILE_SIZE_MB:
        return False, None, (
            f"File too large ({file_size_mb:.1f} MB). "
            f"Maximum allowed: {config.MARKITDOWN_MAX_FILE_SIZE_MB} MB"
        )

    md = get_markitdown_instance()
    if md is None:
        return False, None, "MarkItDown not available"

    try:
        logger.info("Converting with MarkItDown: %s", file_path.name)

        # Convert the file
        result = md.convert(str(file_path))

        if result and (hasattr(result, 'markdown') or hasattr(result, 'text_content')):
            markdown_content = getattr(result, 'markdown', None) or getattr(result, 'text_content', '')

            # Extract document metadata if available
            doc_metadata = {
                "file_size_bytes": file_path.stat().st_size,
                "file_extension": file_path.suffix.lower(),
            }

            # Extract title from MarkItDown result (DocumentConverterResult.title)
            doc_title = getattr(result, 'title', None) or file_path.stem
            doc_metadata['doc_title'] = doc_title

            # Add YAML frontmatter with enriched metadata
            frontmatter = utils.generate_yaml_frontmatter(
                title=doc_metadata.get('doc_title', file_path.stem),
                file_name=file_path.name,
                conversion_method="MarkItDown",
                additional_fields=doc_metadata
            )

            full_content = frontmatter + markdown_content

            # Save output
            output_path = config.OUTPUT_MD_DIR / f"{utils.safe_output_stem(file_path)}.md"
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


def convert_stream_with_markitdown(
    stream: Any,
    filename: str = "document",
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Convert a binary stream to Markdown using MarkItDown's ``convert_stream()``.

    This avoids writing temporary files when data is already in memory
    (e.g. from network streams, ZIP archives, or database BLOBs).

    Args:
        stream: A binary file-like object (``io.BytesIO``, open file in ``"rb"`` mode, etc.).
        filename: Original filename used for extension-based format detection.

    Returns:
        Tuple of (success, markdown_content, error_message)
    """
    md = get_markitdown_instance()
    if md is None:
        return False, None, "MarkItDown not available"

    if not hasattr(md, "convert_stream"):
        return False, None, "convert_stream() not available; upgrade markitdown to >=0.1.5"

    try:
        logger.info("Converting stream with MarkItDown: %s", filename)
        result = md.convert_stream(stream, file_extension=Path(filename).suffix)

        if result and (hasattr(result, "markdown") or hasattr(result, "text_content")):
            markdown_content = getattr(result, "markdown", None) or getattr(result, "text_content", "")
            return True, markdown_content, None

        return False, None, "No content returned from MarkItDown stream conversion"

    except Exception as e:
        logger.error("Error converting stream with MarkItDown: %s", e)
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
            # NOTE: split_text is critical for wide financial tables where PDFMiner
            # merges adjacent column values into a single string. column_tol=0 and
            # row_tol=2 are the camelot defaults; previous values (5, 5) were causing
            # column pairs to merge on tight-spaced tables.
            table_list = camelot.read_pdf(
                str(pdf_path),
                pages='all',
                flavor='stream',
                suppress_stdout=True,
                split_text=config.CAMELOT_STREAM_SPLIT_TEXT,
                edge_tol=config.CAMELOT_STREAM_EDGE_TOL,
                row_tol=config.CAMELOT_STREAM_ROW_TOL,
                column_tol=config.CAMELOT_STREAM_COLUMN_TOL,
            )

        for table in table_list:
            # Quality filtering - skip low-accuracy tables
            # Guard against None values to prevent TypeError
            table_accuracy = getattr(table, 'accuracy', None)
            if table_accuracy is not None and table_accuracy < config.CAMELOT_MIN_ACCURACY:
                logger.debug(
                    f"Skipping low-accuracy table: {table_accuracy:.1f}% "
                    f"(threshold: {config.CAMELOT_MIN_ACCURACY}%)"
                )
                continue

            # Whitespace filtering - skip tables with too much empty space
            # Guard against None values to prevent TypeError
            table_whitespace = getattr(table, 'whitespace', None)
            if table_whitespace is not None and table_whitespace > config.CAMELOT_MAX_WHITESPACE:
                logger.debug(
                    f"Skipping high-whitespace table: {table_whitespace:.1f}% "
                    f"(threshold: {config.CAMELOT_MAX_WHITESPACE}%)"
                )
                continue
            
            # Convert DataFrame to list of lists
            table_data = table.df.values.tolist()

            if table_data and len(table_data) > 0:
                # Post-process: fix merged currency cells
                table_data = _fix_merged_currency_cells(table_data)
                table_data = _fix_split_headers(table_data)
                tables.append(table_data)

                # Log quality metrics (using already-fetched values)
                quality_info = ""
                if table_accuracy is not None:
                    quality_info += f" (accuracy: {table_accuracy:.1f}%"
                if table_whitespace is not None:
                    quality_info += f", whitespace: {table_whitespace:.1f}%)"
                elif quality_info:
                    quality_info += ")"

                logger.debug(f"Camelot extracted table with {len(table_data)} rows{quality_info}")

    except Exception as e:
        logger.error(f"Error extracting tables with camelot ({flavor}): {e}")

    return tables

def _fix_split_headers(table: List[List[str]], max_header_rows: int = 3) -> List[List[str]]:
    """
    Rejoin header text that split_text=True split across column boundaries.

    Example: ['Be', 'ginning', 'January', ...] → ['', 'Beginning', 'January', ...]
    Example: ['Acct Account Title B', 'alance'] → ['Acct Account Title', 'Balance']

    Only applies to the first few rows (headers), never touches data rows.
    """
    for row_idx in range(min(max_header_rows, len(table))):
        row = table[row_idx]
        col = 0
        while col < len(row) - 1:
            cell = str(row[col]).strip()
            next_cell = str(row[col + 1]).strip()

            # Skip if next cell is empty, numeric, or starts uppercase (likely a real column)
            if not next_cell or not next_cell[0].islower():
                col += 1
                continue

            # Check if current cell ends with a fragment (partial word)
            if cell and cell[-1].isalpha():
                # Find the trailing fragment in current cell
                parts = cell.rsplit(' ', 1)
                if len(parts) == 2:
                    # "Acct Account Title B" + "alance" → "Acct Account Title" + "Balance"
                    row[col] = parts[0]
                    row[col + 1] = parts[1] + next_cell
                else:
                    # "Be" + "ginning" → "" + "Beginning"
                    row[col] = ''
                    row[col + 1] = cell + next_cell
            col += 1
        table[row_idx] = row

    return table


def _fix_merged_currency_cells(table: List[List[str]]) -> List[List[str]]:
    """
    Fix cells where multiple numeric/currency values are merged into one cell.

    Handles two scenarios:
    1. Dollar-sign pairs: "$ 1,234.56 $ 5,678.90" → two cells
    2. Bare number pairs: "153,990.37 (235,497.83)" → two cells
       (only when the cell contains no letters, to avoid splitting account names)

    This commonly happens when Camelot misses a column boundary between
    adjacent columns in wide financial tables (e.g., January+February,
    November+December, or Beginning Balance + Account Title).

    Args:
        table: Table as list of rows

    Returns:
        Fixed table with merged value cells properly split
    """
    # Pattern 1: Two dollar-sign values in one cell
    # Matches: "$ 1,234.56 $ 5,678.90" or "$ (1,234.56) $ (5,678.90)"
    double_currency_pattern = re.compile(
        r'(\$\s*[\(\-]?[\d,]+\.?\d*[\)]?)\s+(\$\s*[\(\-]?[\d,]+\.?\d*[\)]?)'
    )

    # Pattern 2: Two bare numbers in one cell (no $ sign)
    # Matches pairs like:
    #   "153,990.37 (235,497.83)"  — positive + parenthetical negative
    #   "55,653.50 55,653.50"     — two positive numbers
    #   "(18,954.54) (31,090.86)" — two parenthetical negatives
    #   "1,456.33 .00"            — number + zero shorthand
    #   ".00 .00"                 — two zero shorthands
    # Each number: optional leading paren/minus, digits with optional commas,
    # optional decimal portion, optional closing paren.
    _NUM = r'[\(\-]?\.?\d[\d,]*\.?\d*\)?'
    double_bare_number_pattern = re.compile(
        rf'({_NUM})\s+({_NUM})'
    )

    fixed_table = []

    for row in table:
        fixed_row = []
        for cell in row:
            if not cell or not isinstance(cell, str):
                fixed_row.append(cell)
                continue

            # Strategy 1: Check for dollar-sign pairs (unambiguous)
            match = double_currency_pattern.search(cell)
            if match:
                parts = cell.split('$')
                if len(parts) >= 3:
                    first_value = '$' + parts[1].strip()
                    second_value = '$' + parts[2].strip()
                    fixed_row.append(first_value)
                    fixed_row.append(second_value)
                    logger.debug(f"Split merged currency cell: '{cell}' → '{first_value}' + '{second_value}'")
                    continue

            # Strategy 2: Check for bare number pairs (only in numeric-only cells)
            # Safety: skip cells containing letters to avoid splitting things like
            # "10201 Cash - Operating 1" or "Fund 5151 E Broadway"
            cell_stripped = cell.strip()
            if cell_stripped and not re.search(r'[a-zA-Z]', cell_stripped):
                bare_match = double_bare_number_pattern.search(cell_stripped)
                if bare_match:
                    first_value = bare_match.group(1).strip()
                    second_value = bare_match.group(2).strip()
                    # Validate both parts look like real numbers (not just a stray digit)
                    if (len(first_value) >= 2 or first_value == '.00') and \
                       (len(second_value) >= 2 or second_value == '.00'):
                        fixed_row.append(first_value)
                        fixed_row.append(second_value)
                        logger.debug(f"Split merged bare number cell: '{cell_stripped}' → '{first_value}' + '{second_value}'")
                        continue

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
    logger.info("Extracting tables from: %s", pdf_path.name)

    result = {
        "tables": [],
        "table_count": 0,
        "methods_used": [],
    }

    # Try pdfplumber first (fastest, most reliable for well-structured PDFs)
    pdfplumber_tables = extract_tables_pdfplumber(pdf_path)
    if pdfplumber_tables:
        result["tables"].extend(pdfplumber_tables)
        result["methods_used"].append("pdfplumber")

    # Try camelot lattice mode (requires Ghostscript, good for grid-line tables)
    camelot_lattice_tables = extract_tables_camelot(pdf_path, flavor="lattice")
    if camelot_lattice_tables:
        result["tables"].extend(camelot_lattice_tables)
        result["methods_used"].append("camelot-lattice")

    # Only run camelot stream if previous methods found few tables.
    # Stream mode is the slowest and most prone to false positives;
    # skip it when we already have good coverage from pdfplumber + lattice.
    if len(result["tables"]) < 2:
        camelot_stream_tables = extract_tables_camelot(pdf_path, flavor="stream")
        if camelot_stream_tables:
            result["tables"].extend(camelot_stream_tables)
            result["methods_used"].append("camelot-stream")
    else:
        logger.debug(
            "Skipping camelot-stream: already found %d tables via faster methods",
            len(result["tables"]),
        )

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
    Remove duplicate tables based on content hash.

    Uses the first row, last row, row count, and column count to build a
    more robust signature that avoids false deduplication of tables that
    happen to share the same header but contain different data.

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

        # Build a robust signature: row count + column count + first row + last row
        col_count = max((len(row) for row in table), default=0)
        first_row = str(table[0]) if table else ""
        last_row = str(table[-1]) if table else ""
        signature = (len(table), col_count, first_row, last_row)

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
        poppler_path = (config.POPPLER_PATH or None) if sys.platform == "win32" else None

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
