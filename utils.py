"""
Enhanced Document Converter v2.1.1 - Utility Functions

This module provides helper functions for logging, caching, file operations,
and metadata tracking.

Documentation references:
- MarkItDown: https://github.com/microsoft/markitdown
- Mistral OCR: https://docs.mistral.ai/capabilities/document_ai/basic_ocr/
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import sys
import itertools

import config

# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging(log_file: Optional[str] = None) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        log_file: Optional path to log file

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("document_converter")
    logger.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler with formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))
    console_format = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler if requested
    if log_file and config.SAVE_PROCESSING_LOGS:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger

# Default logger
logger = setup_logging()

# ============================================================================
# Intelligent Caching System
# ============================================================================

class IntelligentCache:
    """
    Hash-based caching system for OCR results to avoid reprocessing.

    Uses file content hashing to detect changes and cache invalidation.
    Statistics are tracked at class level to persist across instances.
    """

    # Class-level statistics (shared across all instances)
    _total_hits = 0
    _total_misses = 0

    def __init__(self, cache_dir: Path = config.CACHE_DIR):
        """
        Initialize the cache system.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_hash(self, file_path: Path) -> str:
        """
        Generate SHA-256 hash of file contents.

        Args:
            file_path: Path to file

        Returns:
            Hexadecimal hash string
        """
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            # Read in chunks for memory efficiency
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _get_cache_path(self, file_hash: str) -> Path:
        """Get cache file path for a given hash."""
        return self.cache_dir / f"{file_hash}.json"

    def get(self, file_path: Path, cache_type: str = "ocr") -> Optional[Dict[str, Any]]:
        """
        Retrieve cached result for a file.

        Args:
            file_path: Path to the file
            cache_type: Type of cache (ocr, table, etc.)

        Returns:
            Cached data if valid, None otherwise
        """
        try:
            file_hash = self._get_file_hash(file_path)
            cache_path = self._get_cache_path(file_hash)

            if not cache_path.exists():
                IntelligentCache._total_misses += 1
                return None

            # Load cache data
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Check cache age
            cached_time = datetime.fromisoformat(cache_data.get("timestamp", ""))
            max_age = timedelta(hours=config.CACHE_DURATION_HOURS)

            if datetime.now() - cached_time > max_age:
                logger.debug(f"Cache expired for {file_path.name}")
                cache_path.unlink()  # Remove expired cache
                IntelligentCache._total_misses += 1
                return None

            # Check cache type
            if cache_data.get("type") != cache_type:
                IntelligentCache._total_misses += 1
                return None

            IntelligentCache._total_hits += 1
            logger.info(f"Cache hit for {file_path.name}")
            return cache_data.get("data")

        except Exception as e:
            logger.warning(f"Error reading cache for {file_path.name}: {e}")
            IntelligentCache._total_misses += 1
            return None

    def set(
        self,
        file_path: Path,
        data: Dict[str, Any],
        cache_type: str = "ocr",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Store data in cache.

        Args:
            file_path: Path to the file
            data: Data to cache
            cache_type: Type of cache
            metadata: Optional metadata to store
        """
        try:
            file_hash = self._get_file_hash(file_path)
            cache_path = self._get_cache_path(file_hash)

            cache_entry = {
                "timestamp": datetime.now().isoformat(),
                "file_name": file_path.name,
                "file_size": file_path.stat().st_size,
                "type": cache_type,
                "data": data,
                "metadata": metadata or {},
            }

            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_entry, f, indent=2, ensure_ascii=False)

            logger.debug(f"Cached result for {file_path.name}")

        except Exception as e:
            logger.warning(f"Error writing cache for {file_path.name}: {e}")

    def clear_old_entries(self) -> int:
        """
        Remove cache entries older than CACHE_DURATION_HOURS.

        Returns:
            Number of entries removed
        """
        removed = 0
        max_age = timedelta(hours=config.CACHE_DURATION_HOURS)

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)

                cached_time = datetime.fromisoformat(cache_data.get("timestamp", ""))

                if datetime.now() - cached_time > max_age:
                    cache_file.unlink()
                    removed += 1

            except Exception as e:
                logger.debug(f"Error processing cache file {cache_file.name}: {e}")

        return removed

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        cache_files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)

        total_requests = IntelligentCache._total_hits + IntelligentCache._total_misses

        return {
            "total_entries": len(cache_files),
            "total_size_mb": total_size / (1024 * 1024),
            "cache_hits": IntelligentCache._total_hits,
            "cache_misses": IntelligentCache._total_misses,
            "hit_rate": (IntelligentCache._total_hits / total_requests * 100) if total_requests > 0 else 0,
        }

# Global cache instance
cache = IntelligentCache()

# ============================================================================
# Markdown Table Formatting
# ============================================================================

def format_table_to_markdown(
    data: List[List[str]],
    headers: Optional[List[str]] = None
) -> str:
    """
    Convert table data to Markdown format.

    Args:
        data: List of rows (each row is a list of cells)
        headers: Optional list of column headers

    Returns:
        Markdown-formatted table string
    """
    if not data:
        return ""

    # Use first row as headers if not provided
    if headers is None and data:
        headers = data[0]
        data = data[1:]

    if not headers:
        return ""

    # Build markdown table
    lines = []

    # Header row
    lines.append("| " + " | ".join(str(h) for h in headers) + " |")

    # Separator row
    lines.append("| " + " | ".join("---" for _ in headers) + " |")

    # Data rows
    for row in data:
        # Pad row to match header length
        padded_row = list(row) + [""] * (len(headers) - len(row))
        lines.append("| " + " | ".join(str(cell) for cell in padded_row[:len(headers)]) + " |")

    return "\n".join(lines)

# ============================================================================
# Table Header Normalization & Cleanup
# ============================================================================

# Common month headers found in financial documents
MONTH_HEADERS = [
    "Beginning", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December", "Current"
]

def detect_month_header_row(table: List[List[str]]) -> Optional[int]:
    """
    Detect which row contains month headers (for financial documents).

    Args:
        table: List of table rows

    Returns:
        Row index containing month headers, or None if not found
    """
    if not table:
        return None

    for row_idx, row in enumerate(table):
        # Join all cells in the row
        row_text = " ".join(str(cell or "") for cell in row).strip()

        # Check if this row contains multiple month names
        month_count = sum(1 for month in MONTH_HEADERS if month in row_text)

        # If we find at least 3 month names (or Beginning/Current), likely a header
        if month_count >= 3:
            return row_idx

    return None

def clean_table_cell(cell: str) -> str:
    """
    Clean individual table cell.

    - Removes extra whitespace and newlines within cells
    - Normalizes "Acct\nAccount Title" to "Acct Account Title"
    - Strips leading/trailing whitespace

    Args:
        cell: Cell content string

    Returns:
        Cleaned cell content
    """
    if not cell:
        return ""

    # Replace newlines with spaces
    cell = cell.replace('\n', ' ').replace('\r', ' ')

    # Collapse multiple spaces
    cell = ' '.join(cell.split())

    return cell.strip()

def is_page_artifact_row(row: List[str]) -> bool:
    """
    Detect if a row is a page artifact (page numbers, repeated headers, etc.).

    Common artifacts:
    - "Page 1", "Page 2", etc.
    - Date stamps like "December 31, 2010"
    - Repeated document headers

    Args:
        row: Table row

    Returns:
        True if row appears to be a page artifact
    """
    if not row:
        return False

    # Join all cells
    row_text = " ".join(str(cell or "") for cell in row).strip()

    # Check for common page artifacts
    artifacts = [
        "Page 1", "Page 2", "Page 3", "Page 4", "Page 5",
        "Page 6", "Page 7", "Page 8", "Page 9", "Page 10",
    ]

    for artifact in artifacts:
        if row_text == artifact:
            return True

    # Check if the row is just a date (e.g., "December 31, 2010")
    # Pattern: single cell or cells that form a date
    if len(row_text) < 30 and any(month in row_text for month in MONTH_HEADERS):
        # Check if it looks like "Month DD, YYYY"
        import re
        date_pattern = r'^[A-Za-z]+\s+\d{1,2},?\s+\d{4}$'
        if re.match(date_pattern, row_text.replace(',', '')):
            return True

    # Empty or near-empty rows
    if len(row_text.strip()) < 3:
        return True

    return False

def clean_table(table: List[List[str]]) -> List[List[str]]:
    """
    Clean a table by:
    - Removing newlines in cells
    - Removing page artifact rows
    - Normalizing cell content

    Args:
        table: List of table rows

    Returns:
        Cleaned table
    """
    if not table:
        return []

    cleaned = []

    for row in table:
        # Skip page artifact rows
        if is_page_artifact_row(row):
            continue

        # Clean each cell
        cleaned_row = [clean_table_cell(cell) for cell in row]

        # Only add non-empty rows
        if any(cell.strip() for cell in cleaned_row):
            cleaned.append(cleaned_row)

    return cleaned

def normalize_table_headers(table: List[List[str]]) -> Tuple[List[str], List[List[str]]]:
    """
    Normalize table headers by detecting month headers and cleaning cells.

    Args:
        table: List of table rows

    Returns:
        Tuple of (headers, data_rows)
    """
    if not table or len(table) < 1:
        return [], []

    # First, clean the table
    table = clean_table(table)

    if not table:
        return [], []

    # Detect month header row
    header_idx = detect_month_header_row(table)

    if header_idx is not None:
        # Use detected month header
        headers = table[header_idx]
        data_rows = table[:header_idx] + table[header_idx + 1:]
    else:
        # Fall back to first row as header
        headers = table[0]
        data_rows = table[1:]

    return headers, data_rows

# ============================================================================
# Text Export Functions
# ============================================================================

def clean_consecutive_duplicates(text: str) -> str:
    """
    Clean text by collapsing consecutive identical lines into a single occurrence.

    This helps remove artifacts from OCR output where headers, footers, or
    other elements are mistakenly recognized multiple times in sequence.
    It compares lines exactly as they appear (including whitespace and Markdown).

    Args:
        text: The input text (e.g., OCR output for a page).
    Returns:
        Cleaned text with consecutive duplicates collapsed.
    """
    if not text:
        return ""

    # Use splitlines() to handle different line endings correctly
    lines = text.splitlines()

    # Use itertools.groupby to group consecutive identical lines.
    # The 'key' represents the unique line content for each group.
    # By taking only the key, we effectively collapse the group into one line.
    cleaned_lines = [key for key, group in itertools.groupby(lines)]

    # Rejoin the lines
    return "\n".join(cleaned_lines)

def markdown_to_text(markdown_content: str) -> str:
    """
    Convert Markdown to plain text by removing formatting.

    Args:
        markdown_content: Markdown string

    Returns:
        Plain text string
    """
    import re

    text = markdown_content

    # Remove YAML frontmatter
    text = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.DOTALL)

    # Remove images
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)

    # Remove links but keep text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # Remove headers #
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)

    # Remove bold/italic
    text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^\*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)

    # Remove code blocks
    text = re.sub(r'```[^\n]*\n.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # Clean up multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()

def save_text_output(markdown_path: Path, markdown_content: str) -> Optional[Path]:
    """
    Save plain text version of markdown content.

    Args:
        markdown_path: Path to markdown file
        markdown_content: Markdown content

    Returns:
        Path to text file if successful, None otherwise
    """
    if not config.GENERATE_TXT_OUTPUT:
        return None

    try:
        text_path = config.OUTPUT_TXT_DIR / f"{markdown_path.stem}.txt"
        text_content = markdown_to_text(markdown_content)

        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text_content)

        logger.debug(f"Saved text output: {text_path.name}")
        return text_path

    except Exception as e:
        logger.error(f"Error saving text output: {e}")
        return None

# ============================================================================
# Metadata Tracking
# ============================================================================

class MetadataTracker:
    """Track metadata for batch operations."""

    def __init__(self):
        """Initialize metadata tracker."""
        self.metadata = {
            "session_start": datetime.now().isoformat(),
            "files_processed": [],
            "total_files": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "total_time_seconds": 0,
        }
        self.start_time = time.time()

    def add_file(
        self,
        file_name: str,
        status: str,
        processing_time: float,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add file processing metadata.

        Args:
            file_name: Name of the file
            status: Processing status (success, failed, skipped)
            processing_time: Time taken to process
            error: Optional error message
            details: Optional additional details
        """
        file_entry = {
            "file_name": file_name,
            "status": status,
            "processing_time_seconds": processing_time,
            "timestamp": datetime.now().isoformat(),
        }

        if error:
            file_entry["error"] = error

        if details:
            file_entry["details"] = details

        self.metadata["files_processed"].append(file_entry)
        self.metadata["total_files"] += 1

        if status == "success":
            self.metadata["successful"] += 1
        elif status == "failed":
            self.metadata["failed"] += 1
        elif status == "skipped":
            self.metadata["skipped"] += 1

    def save(self, output_name: str = "batch_metadata.json") -> Path:
        """
        Save metadata to file.

        Args:
            output_name: Name of metadata file

        Returns:
            Path to saved metadata file
        """
        self.metadata["session_end"] = datetime.now().isoformat()
        self.metadata["total_time_seconds"] = time.time() - self.start_time

        metadata_path = config.METADATA_DIR / output_name

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)

        return metadata_path

# ============================================================================
# Progress Indicators
# ============================================================================

def print_progress(current: int, total: int, prefix: str = "Progress") -> None:
    """
    Print progress bar to console.

    Args:
        current: Current item number
        total: Total number of items
        prefix: Prefix text
    """
    if not config.VERBOSE_PROGRESS:
        return

    percent = (current / total) * 100 if total > 0 else 0
    bar_length = 40
    filled = int(bar_length * current // total) if total > 0 else 0
    bar = '=' * filled + '-' * (bar_length - filled)

    # Use ASCII characters for better Windows console compatibility
    print(f'\r{prefix}: [{bar}] {percent:.1f}% ({current}/{total})', end='', flush=True)

    if current == total:
        print()  # New line when complete

# ============================================================================
# File Validation
# ============================================================================

def validate_file(file_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Validate if a file can be processed.

    Args:
        file_path: Path to file

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path.exists():
        return False, f"File does not exist: {file_path}"

    if not file_path.is_file():
        return False, f"Not a file: {file_path}"

    if file_path.stat().st_size == 0:
        return False, f"File is empty: {file_path.name}"

    # Check file extension
    ext = file_path.suffix.lower().lstrip('.')
    supported = config.MARKITDOWN_SUPPORTED | config.MISTRAL_OCR_SUPPORTED

    if ext not in supported:
        return False, f"Unsupported file type: .{ext}"

    return True, None

# ============================================================================
# YAML Frontmatter Generation
# ============================================================================

def generate_yaml_frontmatter(
    title: str,
    file_name: str,
    conversion_method: str,
    additional_fields: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate YAML frontmatter for markdown files.

    Args:
        title: Document title
        file_name: Original file name
        conversion_method: Method used for conversion
        additional_fields: Optional additional metadata fields

    Returns:
        YAML frontmatter string
    """
    if not config.INCLUDE_METADATA:
        return ""

    metadata = {
        "title": title,
        "source_file": file_name,
        "conversion_method": conversion_method,
        "converted_at": datetime.now().isoformat(),
        "converter_version": "2.1.1",
    }

    if additional_fields:
        metadata.update(additional_fields)

    # Build YAML
    lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, str):
            lines.append(f'{key}: "{value}"')
        else:
            lines.append(f'{key}: {value}')
    lines.append("---\n")

    return "\n".join(lines)

def strip_yaml_frontmatter(content: str) -> str:
    """
    Remove YAML frontmatter from markdown content.

    Frontmatter is detected as content between two '---' markers at the start.

    Args:
        content: Markdown content that may contain frontmatter

    Returns:
        Content without frontmatter
    """
    import re

    # Pattern to match YAML frontmatter at the start of content
    # Matches: ---\n...anything...\n---\n
    pattern = r'^---\s*\n.*?\n---\s*\n'

    # Remove frontmatter if found
    cleaned = re.sub(pattern, '', content, count=1, flags=re.DOTALL)

    return cleaned.strip()
