import subprocess
import shutil
from pathlib import Path
import re
import time
import json
import os
import random
import uuid
from datetime import datetime

# Optional libs
try:
    import pandas as pd
except Exception:
    pd = None
try:
    from tabulate import tabulate
except Exception:
    tabulate = None

from config import OUT_TXT

def logline(s: str) -> None:
    print(s, flush=True)

def run(cmd: list[str] | str, timeout: int | None = None) -> tuple[int, str, str]:
    shell = isinstance(cmd, str)
    try:
        proc = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or "", e.stderr or "TIMEOUT"
    except Exception as e:
        return 1, "", str(e)

def have(exe: str) -> bool:
    return shutil.which(exe) is not None

def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def md_table(df: "pd.DataFrame") -> str:
    if df is None or df.empty:
        return ""
    if tabulate is None:
        headers = list(df.columns)
        lines = []
        lines.append("| " + " | ".join(map(str, headers)) + " |")
        lines.append("| " + " | ".join(["---"]*len(headers)) + " |")
        for _, row in df.iterrows():
            lines.append("| " + " | ".join("" if x is None else str(x) for x in row.tolist()) + " |")
        return "\n".join(lines)
    return tabulate(df.fillna(""), headers="keys", tablefmt="github", showindex=False)

def md_to_txt(md_path: Path, txt_path: Path) -> None:
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            md = f.read()
        md = md.replace("```", "")
        out_lines = []
        for line in md.splitlines():
            if line.strip().startswith("|") and "|" in line:
                row = [c.strip() for c in line.strip().strip("|").split("|")]
                if all(re.fullmatch(r":?-{3,}:?", c) for c in row):
                    continue
                out_lines.append("\t".join(row))
            else:
                # Skip image links in TXT output
                if re.search(r"!\[.*?\]\(.*?\)", line):
                    continue
                line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)
                line = re.sub(r"^\s{0,3}[-*+]\s+", "", line)
                out_lines.append(line)
        write_text(txt_path, "\n".join(out_lines))
    except Exception as e:
        logline(f"  -> WARN: MD->TXT failed for {md_path.name}: {e}")

def get_mime_type(file_path: Path) -> str:
    """Helper to get MIME type from file extension."""
    suffix = file_path.suffix.lower()
    mime_types = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }
    return mime_types.get(suffix, "application/octet-stream")

class ProcessingStrategy:
    """Represents a file processing strategy with priority and capabilities."""
    def __init__(self, use_markitdown: bool, use_ocr: bool, priority: int, 
                 description: str, benefits: list[str]):
        self.use_markitdown = use_markitdown
        self.use_ocr = use_ocr
        self.priority = priority  # Lower = higher priority
        self.description = description
        self.benefits = benefits

def get_enhanced_file_strategy(file_path: Path) -> ProcessingStrategy:
    """
    Enhanced file type detection with optimal processing strategy.
    
    Returns ProcessingStrategy based on:
    - File type analysis
    - Content complexity estimation  
    - Available API keys
    - Performance optimization
    """
    ext = file_path.suffix.lower()
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    # Import here to avoid circular dependency
    from config import MISTRAL_API_KEY
    
    # Markitdown-optimized formats - use native capabilities first
    if ext in {'.docx', '.pptx', '.xlsx', '.xls'}:
        return ProcessingStrategy(
            use_markitdown=True,
            use_ocr=False,  # Office docs handled best by MarkItDown
            priority=1,
            description="Office document with structured content",
            benefits=["Native text extraction", "Preserves formatting", "Table structure"]
        )
    
    # Text-based formats - Markitdown excels here
    if ext in {'.html', '.xml', '.csv', '.json', '.txt', '.md', '.rtf'}:
        return ProcessingStrategy(
            use_markitdown=True,
            use_ocr=False,
            priority=1,
            description="Structured text format",
            benefits=["Fast processing", "Perfect text preservation", "No API costs"]
        )
    
    # Image formats - OCR primary
    if ext in {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp'}:
        if not MISTRAL_API_KEY:
            return ProcessingStrategy(
                use_markitdown=True,  # May extract EXIF
                use_ocr=False,
                priority=3,
                description="Image without OCR capability",
                benefits=["EXIF metadata extraction"]
            )
        return ProcessingStrategy(
            use_markitdown=False,
            use_ocr=True,
            priority=1,
            description="Image requiring OCR",
            benefits=["High-accuracy text extraction", "Layout preservation"]
        )
    
    # PDF files - complex hybrid strategy
    if ext == '.pdf':
        if file_size_mb > 50:  # Large PDFs
            if MISTRAL_API_KEY:
                return ProcessingStrategy(
                    use_markitdown=True,
                    use_ocr=True,
                    priority=2,
                    description="Large PDF requiring hybrid processing",
                    benefits=["Text + OCR coverage", "Table extraction", "Image analysis"]
                )
            else:
                return ProcessingStrategy(
                    use_markitdown=True,
                    use_ocr=False,
                    priority=2,
                    description="Large PDF with text extraction only",
                    benefits=["Fast text extraction", "Table detection"]
                )
        else:  # Standard PDFs
            return ProcessingStrategy(
                use_markitdown=True,
                use_ocr=bool(MISTRAL_API_KEY),
                priority=1,
                description="Standard PDF with optimal processing",
                benefits=["Complete text extraction", "Enhanced OCR analysis", "Table processing"]
            )
    
    # Archive formats - Markitdown can handle
    if ext in {'.zip', '.epub'}:
        return ProcessingStrategy(
            use_markitdown=True,
            use_ocr=False,
            priority=2,
            description="Archive format with nested content",
            benefits=["Content extraction", "Structure preservation"]
        )
    
    # Audio/Video - Markitdown has transcription capabilities
    if ext in {'.mp3', '.wav', '.m4a', '.flac', '.mp4', '.avi', '.mov'}:
        return ProcessingStrategy(
            use_markitdown=True,
            use_ocr=False,
            priority=2,
            description="Media file with potential transcription",
            benefits=["Metadata extraction", "Transcription capability"]
        )
    
    # Unknown formats - try both if available
    if MISTRAL_API_KEY:
        return ProcessingStrategy(
            use_markitdown=True,
            use_ocr=True,
            priority=3,
            description="Unknown format - attempting both methods",
            benefits=["Maximum coverage", "Fallback options"]
        )
    else:
        return ProcessingStrategy(
            use_markitdown=True,
            use_ocr=False,
            priority=3,
            description="Unknown format - text extraction only",
            benefits=["Basic text extraction"]
        )

def analyze_file_complexity(file_path: Path) -> dict:
    """
    Analyze file characteristics to inform processing decisions.
    
    Returns metrics about file complexity, size, and estimated processing time.
    """
    try:
        stat_info = file_path.stat()
        file_size_mb = stat_info.st_size / (1024 * 1024)
        
        complexity = {
            'size_mb': file_size_mb,
            'size_category': 'small' if file_size_mb < 1 else 'medium' if file_size_mb < 10 else 'large',
            'estimated_processing_time': estimate_processing_time(file_path),
            'recommended_method': 'hybrid' if file_size_mb > 5 else 'standard',
            'memory_usage_estimate': estimate_memory_usage(file_path)
        }
        
        return complexity
    except Exception as e:
        return {
            'size_mb': 0,
            'size_category': 'unknown',
            'estimated_processing_time': 'unknown',
            'recommended_method': 'standard',
            'memory_usage_estimate': 'low',
            'error': str(e)
        }

def estimate_processing_time(file_path: Path) -> str:
    """Estimate processing time based on file type and size."""
    ext = file_path.suffix.lower()
    size_mb = file_path.stat().st_size / (1024 * 1024)
    
    # Time estimates in seconds
    if ext in {'.txt', '.md', '.csv', '.json'}:
        return f"{max(1, int(size_mb * 0.1))}s"
    elif ext in {'.docx', '.xlsx', '.pptx'}:
        return f"{max(2, int(size_mb * 0.5))}s"
    elif ext == '.pdf':
        return f"{max(5, int(size_mb * 2))}s"
    elif ext in {'.jpg', '.png', '.tiff'}:
        return f"{max(3, int(size_mb * 1.5))}s"
    else:
        return f"{max(2, int(size_mb * 1))}s"

def estimate_memory_usage(file_path: Path) -> str:
    """Estimate memory usage during processing."""
    size_mb = file_path.stat().st_size / (1024 * 1024)
    
    if size_mb < 1:
        return "low"
    elif size_mb < 10:
        return "medium"
    elif size_mb < 50:
        return "high"
    else:
        return "very_high"

# Concurrent Processing and Error Handling
import concurrent.futures
import threading
from typing import Callable, Any
from dataclasses import dataclass

@dataclass
class ProcessingResult:
    """Result of file processing operation."""
    file_path: Path
    success: bool
    output_files: list[Path]
    error_message: str = ""
    processing_time: float = 0.0
    strategy_used: str = ""
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class ConcurrentProcessor:
    """Enhanced concurrent file processor with intelligent load balancing."""
    
    def __init__(self, max_workers: int = None, rate_limit_delay: float = 1.0):
        self.max_workers = max_workers or min(4, (os.cpu_count() or 1) + 1)
        self.rate_limit_delay = rate_limit_delay
        self.processing_stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'total_time': 0.0,
            'api_calls': 0
        }
        self._rate_limiter = threading.Semaphore(1)
        
    def process_files_concurrent(self, files: list[Path], 
                               processing_func: Callable[[Path], ProcessingResult],
                               progress_callback: Callable[[int, int], None] = None) -> list[ProcessingResult]:
        """
        Process files concurrently with rate limiting and error handling.
        
        Args:
            files: List of file paths to process
            processing_func: Function to process each file
            progress_callback: Optional callback for progress updates
        
        Returns:
            List of ProcessingResult objects
        """
        results = []
        completed = 0
        
        # Separate files by processing requirements
        api_files, local_files = self._categorize_files(files)
        
        logline(f"  -> Concurrent processing: {len(api_files)} API files, {len(local_files)} local files")
        
        # Process local files concurrently (no API limits)
        if local_files:
            local_results = self._process_local_files_concurrent(local_files, processing_func)
            results.extend(local_results)
            completed += len(local_results)
            if progress_callback:
                progress_callback(completed, len(files))
        
        # Process API files with rate limiting
        if api_files:
            api_results = self._process_api_files_sequential(api_files, processing_func, progress_callback, completed, len(files))
            results.extend(api_results)
        
        # Update stats
        self.processing_stats['total_processed'] += len(results)
        self.processing_stats['successful'] += sum(1 for r in results if r.success)
        self.processing_stats['failed'] += sum(1 for r in results if not r.success)
        self.processing_stats['total_time'] += sum(r.processing_time for r in results)
        
        return results
    
    def _categorize_files(self, files: list[Path]) -> tuple[list[Path], list[Path]]:
        """Categorize files by whether they require API calls."""
        from config import MISTRAL_API_KEY
        
        api_files = []
        local_files = []
        
        for file_path in files:
            ext = file_path.suffix.lower()
            
            # Files that typically need API calls
            if ext in {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif'} and MISTRAL_API_KEY:
                api_files.append(file_path)
            elif ext == '.pdf' and MISTRAL_API_KEY:
                # Large PDFs might benefit from OCR
                file_size_mb = file_path.stat().st_size / (1024 * 1024)
                if file_size_mb > 5:  # Threshold for OCR benefit
                    api_files.append(file_path)
                else:
                    local_files.append(file_path)
            else:
                local_files.append(file_path)
        
        return api_files, local_files
    
    def _process_local_files_concurrent(self, files: list[Path], 
                                      processing_func: Callable[[Path], ProcessingResult]) -> list[ProcessingResult]:
        """Process local files concurrently without rate limits."""
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {executor.submit(self._safe_process_file, f, processing_func): f for f in files}
            
            for future in concurrent.futures.as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    error_result = ProcessingResult(
                        file_path=file_path,
                        success=False,
                        output_files=[],
                        error_message=f"Concurrent processing error: {e}"
                    )
                    results.append(error_result)
                    logline(f"  -> Error processing {file_path.name}: {e}")
        
        return results
    
    def _process_api_files_sequential(self, files: list[Path], 
                                    processing_func: Callable[[Path], ProcessingResult],
                                    progress_callback: Callable[[int, int], None],
                                    initial_completed: int, total_files: int) -> list[ProcessingResult]:
        """Process API files sequentially with rate limiting."""
        results = []
        completed = initial_completed
        
        for file_path in files:
            # Rate limiting for API calls
            with self._rate_limiter:
                result = self._safe_process_file(file_path, processing_func)
                results.append(result)
                
                if result.success and 'ocr' in result.strategy_used.lower():
                    self.processing_stats['api_calls'] += 1
                    time.sleep(self.rate_limit_delay)  # Respect API rate limits
                
                completed += 1
                if progress_callback:
                    progress_callback(completed, total_files)
        
        return results
    
    def _safe_process_file(self, file_path: Path, 
                          processing_func: Callable[[Path], ProcessingResult]) -> ProcessingResult:
        """Safely process a single file with comprehensive error handling."""
        start_time = time.time()
        
        try:
            result = processing_func(file_path)
            result.processing_time = time.time() - start_time
            return result
            
        except FileNotFoundError:
            return ProcessingResult(
                file_path=file_path,
                success=False,
                output_files=[],
                error_message="File not found",
                processing_time=time.time() - start_time
            )
        except PermissionError:
            return ProcessingResult(
                file_path=file_path,
                success=False,
                output_files=[],
                error_message="Permission denied",
                processing_time=time.time() - start_time
            )
        except Exception as e:
            return ProcessingResult(
                file_path=file_path,
                success=False,
                output_files=[],
                error_message=str(e),
                processing_time=time.time() - start_time
            )
    
    def get_processing_stats(self) -> dict:
        """Get processing statistics."""
        stats = self.processing_stats.copy()
        if stats['total_processed'] > 0:
            stats['success_rate'] = stats['successful'] / stats['total_processed']
            stats['average_time'] = stats['total_time'] / stats['total_processed']
        else:
            stats['success_rate'] = 0.0
            stats['average_time'] = 0.0
        
        return stats

class ErrorRecoveryManager:
    """Manages error recovery and retry strategies."""
    
    def __init__(self, max_retries: int = 3, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.error_history = []
    
    def retry_with_backoff(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with exponential backoff retry."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                self.error_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'function': func.__name__,
                    'attempt': attempt + 1,
                    'error': str(e)
                })
                
                if attempt < self.max_retries:
                    delay = (self.backoff_factor ** attempt) + random.uniform(0, 1)
                    logline(f"  -> Retry {attempt + 1}/{self.max_retries} after {delay:.1f}s: {e}")
                    time.sleep(delay)
                else:
                    logline(f"  -> All retries exhausted: {e}")
        
        raise last_exception
    
    def get_error_summary(self) -> dict:
        """Get summary of errors encountered."""
        if not self.error_history:
            return {'total_errors': 0}
        
        error_types = {}
        for error in self.error_history:
            error_type = type(error['error']).__name__
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        return {
            'total_errors': len(self.error_history),
            'error_types': error_types,
            'recent_errors': self.error_history[-5:] if len(self.error_history) > 5 else self.error_history
        }

def create_file_processor_function(use_enhanced_strategy: bool = True) -> Callable[[Path], ProcessingResult]:
    """
    Create a file processing function that can be used with concurrent processing.
    
    Args:
        use_enhanced_strategy: Whether to use the enhanced file type detection
    
    Returns:
        Function that processes a single file and returns ProcessingResult
    """
    def process_single_file(file_path: Path) -> ProcessingResult:
        """Process a single file and return results."""
        from config import OUT_MD, OUT_TXT
        
        base_name = file_path.stem
        output_files = []
        
        try:
            if use_enhanced_strategy:
                strategy = get_enhanced_file_strategy(file_path)
                strategy_description = strategy.description
                
                # Use Markitdown if recommended
                if strategy.use_markitdown:
                    from local_converter import run_markitdown_enhanced
                    md_path = OUT_MD / f"{base_name}.md"
                    success = run_markitdown_enhanced(file_path, md_path)
                    if success and md_path.exists():
                        output_files.append(md_path)
                
                # Use OCR if recommended and available
                if strategy.use_ocr:
                    from mistral_converter import mistral_ocr_file_enhanced, process_mistral_response_enhanced
                    from config import MISTRAL_API_KEY
                    
                    if MISTRAL_API_KEY:
                        resp = mistral_ocr_file_enhanced(file_path, base_name, use_cache=True)
                        if resp:
                            ocr_path = process_mistral_response_enhanced(resp, base_name)
                            if ocr_path and ocr_path.exists():
                                output_files.append(ocr_path)
            else:
                # Fallback to simple processing
                from local_converter import run_markitdown_enhanced
                md_path = OUT_MD / f"{base_name}.md"
                success = run_markitdown_enhanced(file_path, md_path)
                if success and md_path.exists():
                    output_files.append(md_path)
                strategy_description = "Simple Markitdown processing"
            
            # Convert to text
            from utils import md_to_txt
            for md_file in output_files[:]:  # Copy list to avoid modification during iteration
                if md_file.suffix == '.md':
                    txt_path = OUT_TXT / f"{md_file.stem}.txt"
                    md_to_txt(md_file, txt_path)
                    if txt_path.exists():
                        output_files.append(txt_path)
            
            return ProcessingResult(
                file_path=file_path,
                success=len(output_files) > 0,
                output_files=output_files,
                strategy_used=strategy_description,
                metadata={'file_size_mb': file_path.stat().st_size / (1024 * 1024)}
            )
            
        except Exception as e:
            return ProcessingResult(
                file_path=file_path,
                success=False,
                output_files=[],
                error_message=str(e)
            )
    
    return process_single_file

# Intelligent Caching and Metadata Tracking
import hashlib
import pickle
from typing import Dict, Any, Optional

class IntelligentCache:
    """Advanced caching system with content-based invalidation and metadata tracking."""
    
    def __init__(self, cache_dir: Path, max_age_hours: int = 24):
        self.cache_dir = cache_dir
        self.max_age_seconds = max_age_hours * 3600
        self.metadata_file = cache_dir / "cache_metadata.json"
        self.cache_dir.mkdir(exist_ok=True)
        self._load_metadata()
    
    def _load_metadata(self):
        """Load cache metadata."""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            else:
                self.metadata = {
                    'created': datetime.now().isoformat(),
                    'entries': {},
                    'stats': {
                        'total_entries': 0,
                        'cache_hits': 0,
                        'cache_misses': 0,
                        'total_size_bytes': 0
                    }
                }
        except Exception as e:
            logline(f"Warning: Could not load cache metadata: {e}")
            self.metadata = {'entries': {}, 'stats': {}}
    
    def _save_metadata(self):
        """Save cache metadata."""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logline(f"Warning: Could not save cache metadata: {e}")
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Generate content-based hash for file."""
        hasher = hashlib.sha256()
        
        # Include file size and modification time for quick checks
        stat_info = file_path.stat()
        hasher.update(str(stat_info.st_size).encode())
        hasher.update(str(stat_info.st_mtime).encode())
        
        # For small files, include content hash
        if stat_info.st_size < 10 * 1024 * 1024:  # 10MB threshold
            try:
                with open(file_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hasher.update(chunk)
            except Exception:
                pass  # Fall back to metadata-only hash
        
        return hasher.hexdigest()
    
    def get_cache_key(self, file_path: Path, processing_method: str, parameters: Dict[str, Any] = None) -> str:
        """Generate cache key for file and processing method."""
        file_hash = self._get_file_hash(file_path)
        param_hash = hashlib.sha256(str(sorted((parameters or {}).items())).encode()).hexdigest()[:16]
        return f"{file_hash}_{processing_method}_{param_hash}"
    
    def is_cached(self, cache_key: str) -> bool:
        """Check if result is cached and valid."""
        if cache_key not in self.metadata['entries']:
            return False
        
        entry = self.metadata['entries'][cache_key]
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        # Check if cache file exists
        if not cache_file.exists():
            del self.metadata['entries'][cache_key]
            self._save_metadata()
            return False
        
        # Check age
        cached_time = datetime.fromisoformat(entry['timestamp'])
        age_seconds = (datetime.now() - cached_time).total_seconds()
        
        if age_seconds > self.max_age_seconds:
            # Remove expired cache
            try:
                cache_file.unlink()
                del self.metadata['entries'][cache_key]
                self._save_metadata()
            except Exception:
                pass
            return False
        
        return True
    
    def get_cached_result(self, cache_key: str) -> Optional[Any]:
        """Retrieve cached result."""
        if not self.is_cached(cache_key):
            self.metadata['stats']['cache_misses'] = self.metadata['stats'].get('cache_misses', 0) + 1
            return None
        
        try:
            cache_file = self.cache_dir / f"{cache_key}.pkl"
            with open(cache_file, 'rb') as f:
                result = pickle.load(f)
            
            self.metadata['stats']['cache_hits'] = self.metadata['stats'].get('cache_hits', 0) + 1
            self._save_metadata()
            
            return result
        except Exception as e:
            logline(f"Warning: Could not load cached result: {e}")
            self.metadata['stats']['cache_misses'] = self.metadata['stats'].get('cache_misses', 0) + 1
            return None
    
    def store_result(self, cache_key: str, result: Any, source_file: Path, processing_info: Dict[str, Any]):
        """Store result in cache with metadata."""
        try:
            cache_file = self.cache_dir / f"{cache_key}.pkl"
            
            with open(cache_file, 'wb') as f:
                pickle.dump(result, f)
            
            # Store metadata
            self.metadata['entries'][cache_key] = {
                'timestamp': datetime.now().isoformat(),
                'source_file': str(source_file),
                'file_size': source_file.stat().st_size,
                'processing_info': processing_info,
                'cache_size': cache_file.stat().st_size
            }
            
            # Update stats
            self.metadata['stats']['total_entries'] = len(self.metadata['entries'])
            self.metadata['stats']['total_size_bytes'] = sum(
                entry.get('cache_size', 0) for entry in self.metadata['entries'].values()
            )
            
            self._save_metadata()
            
        except Exception as e:
            logline(f"Warning: Could not store cache result: {e}")
    
    def cleanup_old_entries(self, max_entries: int = 1000):
        """Clean up old cache entries to maintain performance."""
        if len(self.metadata['entries']) <= max_entries:
            return
        
        # Sort by timestamp and remove oldest
        entries_by_time = sorted(
            self.metadata['entries'].items(),
            key=lambda x: x[1]['timestamp']
        )
        
        entries_to_remove = entries_by_time[:-max_entries]
        
        for cache_key, _ in entries_to_remove:
            try:
                cache_file = self.cache_dir / f"{cache_key}.pkl"
                if cache_file.exists():
                    cache_file.unlink()
                del self.metadata['entries'][cache_key]
            except Exception:
                pass
        
        self._save_metadata()
        logline(f"Cache cleanup: Removed {len(entries_to_remove)} old entries")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        stats = self.metadata['stats'].copy()
        
        total_requests = stats.get('cache_hits', 0) + stats.get('cache_misses', 0)
        if total_requests > 0:
            stats['hit_rate'] = stats.get('cache_hits', 0) / total_requests
        else:
            stats['hit_rate'] = 0.0
        
        stats['size_mb'] = stats.get('total_size_bytes', 0) / (1024 * 1024)
        
        return stats

class MetadataTracker:
    """Comprehensive metadata tracking for processing operations."""
    
    def __init__(self, metadata_dir: Path):
        self.metadata_dir = metadata_dir
        self.metadata_dir.mkdir(exist_ok=True)
        self.session_file = metadata_dir / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.global_stats_file = metadata_dir / "global_stats.json"
        
        self.session_data = {
            'session_id': str(uuid.uuid4())[:8],
            'start_time': datetime.now().isoformat(),
            'files_processed': [],
            'performance_metrics': {},
            'error_log': []
        }
        
        self._load_global_stats()
    
    def _load_global_stats(self):
        """Load global processing statistics."""
        try:
            if self.global_stats_file.exists():
                with open(self.global_stats_file, 'r', encoding='utf-8') as f:
                    self.global_stats = json.load(f)
            else:
                self.global_stats = {
                    'total_files_processed': 0,
                    'total_processing_time': 0.0,
                    'file_type_stats': {},
                    'processing_method_stats': {},
                    'average_file_sizes': {},
                    'error_patterns': {}
                }
        except Exception as e:
            logline(f"Warning: Could not load global stats: {e}")
            self.global_stats = {}
    
    def track_file_processing(self, file_path: Path, result: ProcessingResult):
        """Track processing of a single file."""
        file_info = {
            'file_path': str(file_path),
            'file_name': file_path.name,
            'file_extension': file_path.suffix.lower(),
            'file_size_mb': file_path.stat().st_size / (1024 * 1024),
            'processing_time': result.processing_time,
            'success': result.success,
            'strategy_used': result.strategy_used,
            'output_files': [str(p) for p in result.output_files],
            'error_message': result.error_message,
            'timestamp': datetime.now().isoformat(),
            'metadata': result.metadata or {}
        }
        
        self.session_data['files_processed'].append(file_info)
        
        # Update global stats
        self._update_global_stats(file_info)
    
    def _update_global_stats(self, file_info: Dict[str, Any]):
        """Update global processing statistics."""
        ext = file_info['file_extension']
        strategy = file_info['strategy_used']
        
        # File type statistics
        if ext not in self.global_stats.get('file_type_stats', {}):
            self.global_stats.setdefault('file_type_stats', {})[ext] = {
                'count': 0,
                'total_time': 0.0,
                'success_rate': 0.0,
                'average_size_mb': 0.0
            }
        
        type_stats = self.global_stats['file_type_stats'][ext]
        type_stats['count'] += 1
        type_stats['total_time'] += file_info['processing_time']
        
        # Processing method statistics
        if strategy not in self.global_stats.get('processing_method_stats', {}):
            self.global_stats.setdefault('processing_method_stats', {})[strategy] = {
                'count': 0,
                'total_time': 0.0,
                'success_rate': 0.0
            }
        
        method_stats = self.global_stats['processing_method_stats'][strategy]
        method_stats['count'] += 1
        method_stats['total_time'] += file_info['processing_time']
        
        # Error tracking
        if not file_info['success'] and file_info['error_message']:
            error_type = type(Exception(file_info['error_message'])).__name__
            self.global_stats.setdefault('error_patterns', {})[error_type] = \
                self.global_stats.get('error_patterns', {}).get(error_type, 0) + 1
        
        # Update totals
        self.global_stats['total_files_processed'] = \
            self.global_stats.get('total_files_processed', 0) + 1
        self.global_stats['total_processing_time'] = \
            self.global_stats.get('total_processing_time', 0.0) + file_info['processing_time']
    
    def add_performance_metric(self, metric_name: str, value: Any):
        """Add a performance metric to the session."""
        self.session_data['performance_metrics'][metric_name] = value
    
    def log_error(self, error_message: str, context: Dict[str, Any] = None):
        """Log an error with context."""
        error_entry = {
            'timestamp': datetime.now().isoformat(),
            'message': error_message,
            'context': context or {}
        }
        self.session_data['error_log'].append(error_entry)
    
    def finalize_session(self):
        """Finalize and save session data."""
        self.session_data['end_time'] = datetime.now().isoformat()
        
        # Calculate session statistics
        processed_files = self.session_data['files_processed']
        if processed_files:
            total_time = sum(f['processing_time'] for f in processed_files)
            successful = sum(1 for f in processed_files if f['success'])
            
            self.session_data['session_stats'] = {
                'total_files': len(processed_files),
                'successful_files': successful,
                'failed_files': len(processed_files) - successful,
                'success_rate': successful / len(processed_files),
                'total_processing_time': total_time,
                'average_time_per_file': total_time / len(processed_files),
                'files_per_second': len(processed_files) / max(total_time, 0.1)
            }
        
        # Save session data
        try:
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(self.session_data, f, indent=2)
        except Exception as e:
            logline(f"Warning: Could not save session data: {e}")
        
        # Save global stats
        try:
            with open(self.global_stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.global_stats, f, indent=2)
        except Exception as e:
            logline(f"Warning: Could not save global stats: {e}")
    
    def get_recommendations(self) -> Dict[str, str]:
        """Get processing recommendations based on historical data."""
        recommendations = {}
        
        if not self.global_stats.get('file_type_stats'):
            return recommendations
        
        # Analyze file type performance
        for ext, stats in self.global_stats['file_type_stats'].items():
            if stats['count'] >= 5:  # Enough data for analysis
                avg_time = stats['total_time'] / stats['count']
                if avg_time > 30:  # Slow processing
                    recommendations[f"slow_processing_{ext}"] = \
                        f"Consider using concurrent processing for {ext} files (avg: {avg_time:.1f}s)"
        
        # Analyze error patterns
        error_patterns = self.global_stats.get('error_patterns', {})
        if error_patterns:
            most_common_error = max(error_patterns.items(), key=lambda x: x[1])
            if most_common_error[1] >= 3:
                recommendations['common_error'] = \
                    f"Common error pattern: {most_common_error[0]} ({most_common_error[1]} occurrences)"
        
        return recommendations

# Global instances for easy access
_cache_instance = None
_metadata_tracker = None

def get_cache() -> IntelligentCache:
    """Get global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        from config import CACHE_DIR
        _cache_instance = IntelligentCache(CACHE_DIR)
    return _cache_instance

def get_metadata_tracker() -> MetadataTracker:
    """Get global metadata tracker instance."""
    global _metadata_tracker
    if _metadata_tracker is None:
        from config import LOG_DIR
        metadata_dir = LOG_DIR / "metadata"
        _metadata_tracker = MetadataTracker(metadata_dir)
    return _metadata_tracker
