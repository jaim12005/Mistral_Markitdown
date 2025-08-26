# Code Style and Conventions

## Python Code Style

### Type Hints
- **Modern Python**: Uses Python 3.10+ features including `list[Type]` syntax instead of `List[Type]`
- **Comprehensive typing**: All functions have type hints for parameters and return values
- **Path objects**: Uses `pathlib.Path` consistently instead of string paths
- **Optional parameters**: Uses `Union` or `|` for optional types

Examples:
```python
def convert_hybrid_pipeline() -> None:
    files: list[Path] = [p for p in sorted(INPUT_DIR.iterdir()) if p.is_file()]

def _combine_hybrid_results(
    base: str, 
    md_main_path: Path, 
    table_files: list[Path], 
    ocr_md_path: Path | None,
    strategy: ProcessingStrategy, 
    complexity: dict
) -> Path | None:
```

### Dataclasses and Enums
- Uses `@dataclass` for structured data with `__post_init__` when needed
- Type-safe configuration with dataclasses
- Clear separation of concerns between data structures and logic

```python
@dataclass
class ProcessingResult:
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
```

### Error Handling
- **Graceful imports**: Uses try/except for optional dependencies
- **Comprehensive exception handling**: Catches specific exceptions with proper logging
- **Traceback preservation**: Uses `traceback.print_exc()` for debugging

```python
try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    # Processing logic
except Exception as e:
    print(f"   ❌ Exception during processing: {e}")
    error_msg = str(e)
    traceback.print_exc()
```

### Naming Conventions
- **Functions**: Snake_case with descriptive names (`convert_hybrid_pipeline`, `_run_hybrid_markitdown`)
- **Private functions**: Leading underscore for internal helpers (`_should_gate_markitdown`)
- **Constants**: UPPER_SNAKE_CASE in config.py (`INPUT_DIR`, `MISTRAL_API_KEY`)
- **Variables**: Snake_case with descriptive names (`processing_time`, `metadata_tracker`)

### Documentation
- **Docstrings**: Functions have clear docstrings explaining purpose and parameters
- **Inline comments**: Strategic comments explaining complex logic
- **User-facing messages**: Rich console output with emojis and formatting

### File Organization
- **Modular architecture**: Clear separation of concerns across modules
- **Configuration centralized**: All env vars and constants in config.py
- **Utilities separated**: Common functions in utils.py
- **Domain-specific modules**: local_converter.py vs mistral_converter.py

## Console Output Style

### User Interface
- **Rich formatting**: Uses emojis and Unicode symbols for visual clarity
- **Progress indicators**: Clear progress reporting with time estimates
- **Status messages**: Consistent ✅/❌/⚠️ status indicators
- **Structured output**: Organized with headers, separators, and indentation

```python
print(f"📄 Processing: {f.name}")
print(f"   📊 Size: {complexity['size_mb']:.1f}MB ({complexity['size_category']})")
print(f"   🎯 Strategy: {strategy.description}")
print(f"   ⏱️  Estimated time: {complexity['estimated_processing_time']}")
```

### Error Reporting
- **Clear error messages**: Descriptive error reporting with context
- **Troubleshooting guidance**: Helpful suggestions for common issues
- **Log file references**: Points users to detailed logs when needed

## Configuration Management

### Environment Variables
- **`.env` file**: Centralized configuration with .env.example template
- **Type conversion**: Helper functions for bool/int conversion from strings
- **Sensible defaults**: Fallback values for optional configuration
- **Documentation**: Comprehensive comments in .env.example

```python
def get_env_bool(key: str, default: bool = False) -> bool:
    return os.environ.get(key, "").lower() in ("true", "1", "yes", "on")

def get_env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except ValueError:
        return default
```

## Testing and Quality

### Testing Approach
- **Smoke tests**: Built-in `--test` flag for installation verification
- **Error recovery**: Graceful handling of missing dependencies
- **Performance monitoring**: Built-in timing and metrics collection

### Code Quality
- **Import organization**: Grouped imports (standard library, third-party, local)
- **Exception specificity**: Catches appropriate exception types
- **Resource cleanup**: Proper handling of files and network resources