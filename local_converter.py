import os
import sys
import time
import json
import base64
from datetime import datetime
from pathlib import Path
from collections import Counter
import re
from typing import List, Any

# Optional libs
try:
    import pandas as pd
except Exception:
    pd = None
try:
    import pdfplumber
except Exception:
    pdfplumber = None
try:
    import camelot  # type: ignore
except Exception:
    camelot = None
try:
    from markitdown import MarkItDown
except Exception:
    MarkItDown = None
try:
    from pdf2image import convert_from_path
except Exception:
    convert_from_path = None

from config import (
    MARKITDOWN_USE_LLM,
    MARKITDOWN_LLM_MODEL,
    MARKITDOWN_LLM_KEY,
    MARKITDOWN_TABLE_STRATEGY,
    MARKITDOWN_IMAGE_STRATEGY,
    MARKITDOWN_PDF_MODE,
    AZURE_DOC_INTEL_ENDPOINT,
    AZURE_DOC_INTEL_KEY,
    MAX_RETRIES,
    RETRY_DELAY,
    MONTHS,
    M_SHORT,
    OUT_MD,
    OUT_IMG,
    POPPLER_PATH,
    LOG_DIR,
    MARKITDOWN_EXPERIMENTAL,
    MARKITDOWN_CUSTOM_OPTIONS,
    MARKITDOWN_USE_CACHE,
    MARKITDOWN_MAX_FILE_SIZE_MB,
    MARKITDOWN_ADVANCED_TABLES,
    MARKITDOWN_ENHANCED_IMAGES,
    MARKITDOWN_IMAGE_QUALITY,
    MARKITDOWN_PARALLEL_PROCESSING,
    MARKITDOWN_WORKERS,
    MISTRAL_API_KEY,
    MISTRAL_MODEL,
    MISTRAL_INCLUDE_IMAGES,
    MISTRAL_INCLUDE_IMAGE_ANNOTATIONS,
    SAVE_MISTRAL_JSON,
    LARGE_FILE_THRESHOLD_MB,
    MISTRAL_TIMEOUT,
    CACHE_DIR,
)
from utils import (
    logline,
    run,
    write_text,
    md_table,
    have,
    ErrorRecoveryManager,
    normalize_amount,
    _normalize_amount_column,
    get_mime_type,
)
from mistral_converter import (
    select_optimal_model,
    _ensure_mistral_client,
    mistral_client,
)


def run_markitdown_enhanced(inp: Path, out_md: Path) -> bool:
    """Enhanced Markitdown with full feature utilization and advanced capabilities."""
    if MarkItDown is not None:
        try:
            logline(f"  -> Using Markitdown Python API with enhanced features...")

            img_out_dir_name = f"{inp.stem}_markitdown"
            img_out_dir_abs = OUT_IMG / img_out_dir_name

            # Define file metadata early for consistent access throughout function
            file_ext = inp.suffix.lower()
            file_size_mb = inp.stat().st_size / (1024 * 1024)

            kwargs = {
                "table_strategy": MARKITDOWN_TABLE_STRATEGY,
                "image_strategy": MARKITDOWN_IMAGE_STRATEGY,
                "output_dir": str(img_out_dir_abs),
            }
            logline(
                f"    -> Strategies: Table={MARKITDOWN_TABLE_STRATEGY}, Image={MARKITDOWN_IMAGE_STRATEGY}"
            )

            # Enhanced Markitdown options
            if MARKITDOWN_EXPERIMENTAL:
                kwargs["experimental"] = True
                logline(f"    -> Experimental features enabled")

            if MARKITDOWN_CUSTOM_OPTIONS:
                # Add custom options based on file type
                if file_ext == ".pdf":
                    kwargs["pdf_options"] = {
                        "max_file_size": MARKITDOWN_MAX_FILE_SIZE_MB * 1024 * 1024,
                        "advanced_tables": MARKITDOWN_ADVANCED_TABLES,
                        "enhanced_images": MARKITDOWN_ENHANCED_IMAGES,
                    }
                elif file_ext in [".docx", ".xlsx", ".pptx"]:
                    kwargs["office_options"] = {
                        "parallel_processing": MARKITDOWN_PARALLEL_PROCESSING,
                        "workers": MARKITDOWN_WORKERS,
                    }

            if MARKITDOWN_USE_CACHE:
                kwargs["use_cache"] = True
                logline(f"    -> Built-in caching enabled")

            if MARKITDOWN_IMAGE_QUALITY != 90:  # Only set if different from default
                kwargs["image_quality"] = MARKITDOWN_IMAGE_QUALITY
                logline(f"    -> Custom image quality: {MARKITDOWN_IMAGE_QUALITY}")

            if MARKITDOWN_USE_LLM and MARKITDOWN_LLM_KEY:
                try:
                    from openai import OpenAI

                    kwargs["llm_client"] = OpenAI(api_key=MARKITDOWN_LLM_KEY)
                    kwargs["llm_model"] = MARKITDOWN_LLM_MODEL
                    logline(
                        f"    -> LLM image description enabled ({MARKITDOWN_LLM_MODEL})"
                    )
                except Exception as e:
                    logline(f"    -> LLM disabled (openai not available): {e}")

            if AZURE_DOC_INTEL_ENDPOINT and AZURE_DOC_INTEL_KEY:
                kwargs["docintel_endpoint"] = AZURE_DOC_INTEL_ENDPOINT
                kwargs["docintel_key"] = AZURE_DOC_INTEL_KEY
                logline(f"    -> Azure Document Intelligence enabled")

            # Enable MarkItDown plugins if configured
            try:
                from config import MARKITDOWN_ENABLE_PLUGINS
            except Exception:
                MARKITDOWN_ENABLE_PLUGINS = False

            md = MarkItDown(enable_plugins=MARKITDOWN_ENABLE_PLUGINS, **kwargs)

            error_manager = ErrorRecoveryManager(
                max_retries=MAX_RETRIES, backoff_factor=max(1.5, RETRY_DELAY / 3.0)
            )

            def conversion_attempt():
                with open(inp, "rb") as file_stream:
                    options = {}
                    if file_ext == ".pdf" and not (
                        AZURE_DOC_INTEL_ENDPOINT and AZURE_DOC_INTEL_KEY
                    ):
                        options["pdf_mode"] = MARKITDOWN_PDF_MODE
                    result = md.convert_stream(
                        file_stream,
                        file_extension=file_ext.lstrip("."),
                        options=options,
                    )
                return result

            try:
                result = error_manager.retry_with_backoff(conversion_attempt)

                content = create_enhanced_markitdown_output(inp, result, file_size_mb)

                img_dir_rel = f"../output_images/{img_out_dir_name}"
                content = rewrite_markitdown_image_links(content, img_dir_rel)

                write_text(out_md, content)
                logline(f"  -> Success: {out_md.relative_to(OUT_MD.parent)}")
                log_processing_insights(inp, result, file_ext)
                return True

            except Exception as e:
                logline(
                    f"  -> Markitdown API failed after {MAX_RETRIES} attempts: {e}. Falling back to CLI..."
                )

        except ImportError as e:
            logline(
                f"  -> Markitdown or dependencies (like OpenAI/Azure SDKs) not found: {e}. Falling back to CLI..."
            )
        except Exception as e:
            logline(
                f"  -> Markitdown initialization failed: {e}. Falling back to CLI..."
            )

    return run_markitdown_cli_enhanced(inp, out_md)


def create_enhanced_markitdown_output(inp: Path, result, file_size_mb: float) -> str:
    """Create enhanced markdown output with YAML frontmatter and structure."""
    # Be defensive about MarkItDown return types
    text_content = getattr(result, "text_content", None)
    if text_content is None:
        text_content = result if isinstance(result, str) else ""

    text_length = len(text_content)
    structure_info = analyze_document_structure(text_content)

    content = "---\n"
    content += f'title: "{inp.name}"\n'
    content += f'source_file: "{inp.name}"\n'
    content += f"file_type: {inp.suffix.upper()[1:]}\n"
    content += f"file_size_mb: {file_size_mb:.2f}\n"
    content += f"processed_at: {datetime.now().isoformat()}\n"
    content += f"processing_method: Markitdown Enhanced\n"
    content += f"content_length_chars: {text_length}\n"

    # Calculate reading time based on actual words (letters only, not numbers)
    import math

    words = len(re.findall(r"\b[a-zA-Z]+\b", text_content or ""))
    wpm = 200  # Average reading speed: 200 words per minute
    content += f"estimated_reading_time_min: {max(1, math.ceil(words / wpm))}\n"

    if structure_info:
        content += "document_structure:\n"
        for key, value in structure_info.items():
            yaml_key = key.lower().replace(" ", "_")
            content += f"  {yaml_key}: {value}\n"
    content += "---\n\n"
    content += f"# {inp.name}\n\n"
    processed_content = enhance_markdown_content(text_content, inp.suffix.lower())
    content += processed_content
    if hasattr(result, "metadata") and result.metadata:
        content += "\n\n---\n\n"
        content += "## 🔍 Processing Metadata (Appendix)\n\n"
        for key, value in result.metadata.items():
            content += f"**{key.replace('_', ' ').title()}**: {value}\n"
    return content


def rewrite_markitdown_image_links(content: str, img_dir_rel: str) -> str:
    """Rewrite Markitdown-generated image links to standardized relative path."""
    IMG_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp", ".gif")

    def replacer(match):
        url = match.group(1)
        if url.startswith(("http://", "https://", "data:")):
            return match.group(0)
        if not any(url.lower().endswith(ext) for ext in IMG_EXT):
            return match.group(0)
        return f"]({img_dir_rel}/{Path(url).name})"

    return re.sub(r"\]\(([^)]+)\)", replacer, content)


def analyze_document_structure(text: str) -> dict:
    lines = text.split("\n")
    structure = {
        "Total Lines": len(lines),
        "Headers": len([l for l in lines if l.strip().startswith("#")]),
        "Tables": text.count("|"),
        "Lists": len(
            [l for l in lines if l.strip().startswith(("-", "*", "1.", "2."))]
        ),
        "Links": text.count("[") + text.count("]("),
        "Code Blocks": text.count("```"),
        "Emphasis": text.count("**"),
    }
    return {k: v for k, v in structure.items() if v > 0}


def enhance_markdown_content(content: str, file_ext: str) -> str:
    enhanced = content
    if file_ext in {".xlsx", ".xls", ".csv"}:
        enhanced = improve_table_formatting(enhanced)
    if file_ext in {".pptx", ".ppt"}:
        enhanced = add_slide_indicators(enhanced)
    if file_ext in {".docx", ".doc"}:
        enhanced = enhance_document_structure(enhanced)
    if file_ext in {".html", ".htm"}:
        enhanced = clean_web_content(enhanced)
    return enhanced


def improve_table_formatting(content: str) -> str:
    lines = content.split("\n")
    enhanced_lines = []
    for line in lines:
        if "|" in line and line.count("|") >= 2:
            cells = [cell.strip() for cell in line.split("|")]
            if cells[0] == "":
                cells = cells[1:]
            if cells[-1] == "":
                cells = cells[:-1]
            enhanced_line = "| " + " | ".join(cells) + " |"
            enhanced_lines.append(enhanced_line)
        else:
            enhanced_lines.append(line)
    return "\n".join(enhanced_lines)


def add_slide_indicators(content: str) -> str:
    enhanced = content.replace("\n\n\n", "\n\n---\n\n**Slide Break**\n\n")
    return enhanced


def enhance_document_structure(content: str) -> str:
    lines = content.split("\n")
    enhanced_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            if (
                len(stripped) < 60
                and stripped.isupper()
                and not any(char in stripped for char in ".,;:")
            ):
                enhanced_lines.append(f"## {stripped}")
            else:
                enhanced_lines.append(line)
        else:
            enhanced_lines.append(line)
    return "\n".join(enhanced_lines)


def clean_web_content(content: str) -> str:
    import re as _re

    enhanced = content
    enhanced = _re.sub(r"\n+", "\n\n", enhanced)
    enhanced = _re.sub(r"&nbsp;", " ", enhanced)
    enhanced = _re.sub(r"&[a-zA-Z]+;", "", enhanced)
    return enhanced


def run_markitdown_cli_enhanced(inp: Path, out_md: Path) -> bool:
    """Enhanced CLI fallback with better options and error handling."""
    args = [sys.executable, "-m", "markitdown"]

    # Only use supported CLI arguments
    # Markitdown CLI v0.1.3 supports basic arguments only
    args.extend([str(inp), "-o", str(out_md)])

    rc, so, se = run(args, timeout=300)
    if rc != 0:
        logline(f"  -> markitdown CLI failed (rc={rc}). stderr: {se.strip()}")
        return False

    try:
        if out_md.exists():
            original_content = out_md.read_text(encoding="utf-8")
            mock_result = type(
                "Result",
                (),
                {"text_content": original_content, "metadata": {"source": "CLI"}},
            )()
            enhanced_content = create_enhanced_markitdown_output(
                inp, mock_result, inp.stat().st_size / (1024 * 1024)
            )
            write_text(out_md, enhanced_content)
    except Exception as e:
        logline(f"  -> Warning: Could not enhance CLI output: {e}")
    logline(f"  -> wrote: {out_md.relative_to(OUT_MD.parent)}")
    return True


def log_processing_insights(inp: Path, result, file_ext: str):
    try:
        insights = {
            "file_type": file_ext,
            "content_length": len(result.text_content),
            "processing_time": datetime.now().isoformat(),
            "has_tables": "|" in result.text_content,
            "has_headers": "#" in result.text_content,
            "has_links": "[" in result.text_content and "](" in result.text_content,
        }
        debug_file = LOG_DIR / "markitdown_insights.jsonl"
        with open(debug_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(insights) + "\n")
    except Exception:
        pass


def looks_like_tb_header(cells: list[str]) -> bool:
    """Enhanced header detection for Trial Balance tables."""
    # Validate input: return False for empty or all-None cells
    if not cells:
        return False

    HEADER_TOKENS = {
        "acct",
        "account",
        "account title",
        "beginning balance",
        "current balance",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    }

    s = " ".join(str(c).lower().strip() for c in cells if c and str(c).strip())
    # Return False if all cells were empty/None
    if not s.strip():
        return False

    # must contain at least 3 header signals or both "beginning/current"
    hits = sum(tok in s for tok in HEADER_TOKENS)
    return hits >= 3 or ("beginning balance" in s and "current balance" in s)


def try_pdfplumber_tables(pdf_path: Path) -> List[Any]:
    out = []
    if pdfplumber is None or pd is None:
        return out
    settings = dict(
        vertical_strategy="lines",
        horizontal_strategy="lines",
        snap_tolerance=6,
        join_tolerance=4,
        edge_min_length=24,
        intersection_tolerance=6,
        text_tolerance=2,
        keep_blank_chars=True,
        min_words_vertical=1,
        min_words_horizontal=1,
    )
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                try:
                    for t in page.extract_tables(settings):
                        raw = pd.DataFrame(t).dropna(axis=1, how="all")
                        if raw.shape[0] >= 2:
                            candidate = raw.iloc[0].astype(str).tolist()
                            if looks_like_tb_header(candidate):
                                df = raw.copy()
                                df.columns = candidate
                                df = df.iloc[1:].reset_index(drop=True)
                            else:
                                df = (
                                    raw.copy()
                                )  # keep rows; let reshaper build headers later
                            out.append(df)
                except Exception:
                    continue
    except Exception as e:
        logline(f"  -> pdfplumber error: {e}")
    return out


def try_camelot_tables(pdf_path: Path) -> List[Any]:
    out = []
    if camelot is None or pd is None:
        return out

    # Prefer lattice mode if Ghostscript is available
    flavor = (
        "lattice"
        if have("gswin64c.exe") or have("gswin32c.exe") or have("gs")
        else "stream"
    )
    flavor_used = flavor

    try:
        # Prefer lattice with sturdier params when available
        if flavor == "lattice":
            # Try progressively stronger line detection before giving up
            tables = None
            for ls in (40, 60, 80, 100):
                try:
                    t = camelot.read_pdf(
                        str(pdf_path),
                        flavor="lattice",
                        pages="all",
                        line_scale=ls,
                        process_background=True,
                    )
                    if t and len(t) > 0:
                        tables = t
                        break
                except Exception:
                    continue
            if tables is None:
                raise RuntimeError("No lattice tables detected")
        else:
            tables = camelot.read_pdf(str(pdf_path), flavor=flavor, pages="all")
        for t in tables:
            raw = t.df
            if raw.shape[0] > 1:
                candidate = raw.iloc[0].astype(str).tolist()
                if looks_like_tb_header(candidate):
                    df = raw.copy()
                    df.columns = candidate
                    df = df.iloc[1:].reset_index(drop=True)
                else:
                    df = raw.copy()  # keep rows; let reshaper build headers later
            else:
                df = raw.copy()
            out.append(df)
        if out:
            logline(
                f"  -> Camelot extracted {len(out)} tables using {flavor_used} mode"
            )
    except Exception as e:
        logline(f"  -> Camelot {flavor_used} mode failed: {e}")

    # Fallback with generous tolerances for messy tables
    if not out and flavor == "lattice":
        try:
            flavor_used = "stream (fallback)"
            tables = camelot.read_pdf(
                str(pdf_path),
                flavor="stream",
                pages="all",
                edge_tol=80,
                row_tol=6,
                column_tol=18,
                strip_text="",
            )
            for t in tables:
                raw = t.df
                if raw.shape[0] > 1:
                    candidate = raw.iloc[0].astype(str).tolist()
                    if looks_like_tb_header(candidate):
                        df = raw.copy()
                        df.columns = candidate
                        df = df.iloc[1:].reset_index(drop=True)
                    else:
                        df = raw.copy()  # keep rows; let reshaper build headers later
                else:
                    df = raw.copy()
                out.append(df)
            if out:
                logline(f"  -> Camelot extracted {len(out)} tables using {flavor_used}")
        except Exception as e:
            logline(f"  -> Camelot {flavor_used} failed: {e}")

    # Try both flavors for tabular-looking PDFs
    if not out and flavor == "stream":
        try:
            flavor_used = "lattice (retry)"
            tables = camelot.read_pdf(
                str(pdf_path),
                flavor="lattice",
                pages="all",
                line_scale=40,
                process_background=True,
            )
            for t in tables:
                raw = t.df
                if raw.shape[0] > 1:
                    candidate = raw.iloc[0].astype(str).tolist()
                    if looks_like_tb_header(candidate):
                        df = raw.copy()
                        df.columns = candidate
                        df = df.iloc[1:].reset_index(drop=True)
                    else:
                        df = raw.copy()  # keep rows; let reshaper build headers later
                else:
                    df = raw.copy()
                out.append(df)
            if out:
                logline(f"  -> Camelot extracted {len(out)} tables using {flavor_used}")
        except Exception as e:
            logline(f"  -> Camelot {flavor_used} failed: {e}")

    return out


def is_month_header(s: str) -> bool:
    s = (s or "").strip().lower()
    return s in [m.lower() for m in MONTHS] or s in [m.lower() for m in M_SHORT]


def _get_series_from_df(df: Any, col: str) -> Any:
    """Safely retrieve a column as a Series, even with duplicate column names."""
    if pd is None or col not in df.columns:
        return pd.Series([], dtype="object") if pd is not None else None
    s = df[col]
    return s.iloc[:, 0] if isinstance(s, pd.DataFrame) else s


def _looks_like_month_header(h: str) -> bool:
    """Check if a header value looks like a month name - tolerant to OCR glitches."""
    MONTHS_SET = {
        "beginning balance",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "current balance",
    }
    # Remove non-alphabetic characters for fuzzy matching
    hs = re.sub(r"[^a-z]", "", (h or "").lower())
    for m in MONTHS_SET:
        m_clean = re.sub(r"[^a-z]", "", m)
        if m_clean in hs or hs in m_clean:  # bidirectional fuzzy match
            return True
    return False


def reshape_financial_table(df: Any) -> Any:
    if pd is None or not isinstance(df, pd.DataFrame) or df.empty:
        return df

    try:
        df = df.copy()
        df.columns = [str(c) for c in df.columns]

        # Build robust headers from the first N rows
        header_rows_to_scan = min(
            6, len(df)
        )  # Increased from 4 to 6 for better tolerance
        col_headers = []
        for c in df.columns:
            tokens = []
            for r in range(header_rows_to_scan):
                val = str(df.iloc[r, df.columns.get_loc(c)]).strip()
                if val and val.lower() not in {"---", "nan", "none"}:
                    tokens.append(val)
            header = " ".join(tokens)
            col_headers.append(header if _looks_like_month_header(header) else "")

        # If we found at least 6 month-bearing headers, use them; otherwise keep raw
        month_header_count = sum(bool(h) for h in col_headers)
        if month_header_count >= 6:
            # Standard month labels (consolidated from duplicate lists)
            months = [
                "Beginning Balance",
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
                "Current Balance",
            ]
            mapped = []
            for h in col_headers:
                best = next((m for m in months if m.lower() in h.lower()), None)
                mapped.append(best or h or "Unlabeled")
            df.columns = mapped
            df = df.iloc[header_rows_to_scan:].reset_index(drop=True)
        else:
            # No reliable header; do not reshape here (fallback to raw)
            logline(
                f"  -> Only {month_header_count} month headers found, keeping original table format"
            )
            return df

        # Normalize function for fuzzy matching
        def norm(s):
            return re.sub(r"\s+", "", s.lower())

        # Function to check if a value looks like an amount
        def is_amount(x):
            return bool(re.search(r"^\s*\$?\(?-?[\d,]+(\.\d{1,2})?\)?\s*$", str(x)))

        # Choose best source per month by numeric fill rate
        best_src_for = {}
        for m in months:
            candidates = [c for c in df.columns if norm(m) in norm(str(c))]
            if not candidates:
                continue
            best = max(candidates, key=lambda c: df[c].apply(is_amount).mean())
            best_src_for[m] = best

        # If too few months resolved with data, try positional fallback or bail out
        resolved_months = sum(1 for m in months if m in best_src_for)
        if resolved_months < 5:  # Lowered threshold from 6 to 5
            # Try positional fallback for accounting tables
            if len(df.columns) >= 12:  # Likely has account info + 10+ numeric columns
                logline(
                    f"  -> Only {resolved_months} months resolved, trying positional fallback"
                )
                # Assume first 2 columns are Acct/Title, rest are months in order
                fallback_months = months[: len(df.columns) - 2]
                fallback_cols = ["Acct", "Account Title"] + fallback_months
                if len(fallback_cols) == len(df.columns):
                    df.columns = fallback_cols
                    logline(
                        f"  -> Applied positional fallback with {len(fallback_months)} month columns"
                    )
                else:
                    logline(
                        f"  -> Positional fallback failed, keeping original table format"
                    )
                    return df
            else:
                logline(
                    f"  -> Only {resolved_months} months resolved with data, keeping original table format"
                )
                return df

        # Find account and title columns
        left_cols = list(df.columns)[:3]
        acct_col = None
        for c in left_cols:
            items = _get_series_from_df(df, c).head(20).tolist()
            sample = " ".join(map(str, items))
            if re.search(r"\b\d{4,7}\b", sample):
                acct_col = c
                break

        if acct_col is None:
            acct_col = (
                left_cols[0]
                if left_cols
                else (df.columns[0] if len(df.columns) > 0 else None)
            )

        if acct_col is None:
            return df

        title_col_idx = 1 if len(left_cols) > 1 else (1 if len(df.columns) > 1 else 0)
        title_col = df.columns[title_col_idx]

        # Identify non-month columns first; that's where acct/title lives
        def _is_month_col(name: str) -> bool:
            nm = re.sub(r"[^a-z]", "", str(name).lower())
            return any(re.sub(r"[^a-z]", "", m.lower()) in nm for m in months)

        non_month_cols = [c for c in list(df.columns) if not _is_month_col(c)]
        left_candidates = non_month_cols[
            : max(8, len(non_month_cols))
        ]  # look wider than 4

        best_col, best_ratio = None, 0.0
        for c in left_candidates:
            s = _get_series_from_df(df, c).astype(str)
            # non-empty only
            nonempty = s.str.strip().ne("")
            if not nonempty.any():
                continue
            # looks like: digits (3–10), optional dash, then some letters
            pattern = r"^\s*\(?\d{3,10}\)?(?:\s*[-–—]?\s+|\s+)(?=[A-Za-z]).+"
            m = s.str.match(pattern, na=False)
            ratio = (m & nonempty).sum() / nonempty.sum()
            if ratio > best_ratio:
                best_ratio, best_col = ratio, c

        if (
            best_col and best_ratio >= 0.15
        ):  # lower threshold; measured over non-empty only
            ser = _get_series_from_df(df, best_col).astype(str)
            split = ser.str.extract(
                r"^\s*\(?(?P<_code>\d{3,10})\)?(?:\s*[-–—]?\s+|\s+)(?P<_title>.+?)\s*$"
            )
            # Guard before insert to prevent "already exists" errors
            code_series = split["_code"].fillna("").astype(str).str.strip()
            title_series = split["_title"].fillna("").astype(str).str.strip()

            if "Acct" in df.columns:
                df["Acct"] = code_series
            else:
                df.insert(0, "Acct", code_series)

            if "Account Title" in df.columns:
                df["Account Title"] = title_series
            else:
                try:
                    pos = list(df.columns).index("Acct") + 1
                except ValueError:
                    pos = 1
                df.insert(pos, "Account Title", title_series)
            # Drop the original combined column and any near-duplicates
            try:
                df.drop(columns=[best_col], inplace=True, errors="ignore")
            except Exception:
                pass
            for c in list(df.columns):
                nm = re.sub(r"[^a-z]", "", str(c).lower())
                if nm in {"acct", "account", "accounttitle"} and c not in (
                    "Acct",
                    "Account Title",
                ):
                    df.drop(columns=[c], inplace=True, errors="ignore")
            acct_col, title_col = "Acct", "Account Title"
        else:
            # Fallback to your previous per-column split, but measure over non-empty rows
            ser = _get_series_from_df(df, acct_col).astype(str)
            nonempty = ser.str.strip().ne("")
            split = ser.str.extract(
                r"^\s*(?P<_code>\d{3,10})\s*(?:-|–|—)?\s*(?P<_title>.+?)\s*$"
            )
            title_series = split["_title"] if "_title" in split else ser.copy()
            code_series = split["_code"] if "_code" in split else ser.copy()
            title_hit = (title_series.notna() & nonempty).sum() / max(1, nonempty.sum())
            code_hit = (code_series.notna() & nonempty).sum() / max(1, nonempty.sum())
            if (title_hit >= 0.30) or (code_hit >= 0.30):
                # Guard before insert to prevent "already exists" errors
                code_series = split["_code"].fillna("").astype(str).str.strip()
                title_series = split["_title"].fillna("").astype(str).str.strip()

                if "Acct" in df.columns:
                    df["Acct"] = code_series
                else:
                    df.insert(0, "Acct", code_series)

                if "Account Title" in df.columns:
                    df["Account Title"] = title_series
                else:
                    try:
                        pos = list(df.columns).index("Acct") + 1
                    except ValueError:
                        pos = 1
                    df.insert(pos, "Account Title", title_series)

                if acct_col in df.columns and acct_col not in ("Acct", "Account Title"):
                    try:
                        df.drop(columns=[acct_col], inplace=True, errors="ignore")
                    except Exception:
                        pass
                acct_col, title_col = "Acct", "Account Title"
        # (continue with out_cols construction as in your code)

        # Build output columns using the best month mappings
        out_cols = [("Acct", acct_col), ("Account Title", title_col)]
        for m in months:
            src = best_src_for.get(m)
            out_cols.append((m, src))

        # Create the output dataframe with normalized amounts
        data = {}
        for out_name, src in out_cols:
            if src and src in df.columns:
                if out_name in ["Acct", "Account Title"]:
                    # Don't normalize account codes or titles
                    data[out_name] = _get_series_from_df(df, src).astype(str)
                else:
                    # Normalize amount columns (column-aware)
                    data[out_name] = _normalize_amount_column(
                        _get_series_from_df(df, src)
                    )
            else:
                data[out_name] = [""] * len(df)

        out_df = pd.DataFrame(data)

        # Filter out empty rows
        keep = (
            _get_series_from_df(out_df, "Account Title").astype(str).str.strip() != ""
        )
        if keep.any():
            out_df = out_df[keep]

        # Also drop rows where all month values are empty to reduce junk totals/section headers
        month_cols = [c for c in out_df.columns if c in months]
        if month_cols:
            numeric_blank = (
                out_df[month_cols].astype(str).apply(lambda s: s.str.strip() == "")
            )
            out_df = out_df[~numeric_blank.all(axis=1)]

        logline(
            f"  -> Reshaped table with {resolved_months} month columns successfully"
        )
        return out_df

    except AttributeError as e:
        if "tolist" in str(e):
            logline(
                f"  -> WARN: Reshape failed due to '.tolist' call on a non-Series object. Type was {type(df)}."
            )
            return df
        raise e
    except Exception as e:
        logline(f"  -> WARN: Unexpected exception in reshape_financial_table: {e}")
        return df


def extract_tables_to_markdown(pdf_path: Path, base_name: str) -> list[Path]:
    written: list[Path] = []
    if pd is None:
        return written
    dfs = []
    dfs += try_pdfplumber_tables(pdf_path)
    dfs += try_camelot_tables(pdf_path)
    reshaped = []
    for d in dfs:
        if d is None or d.empty:
            continue
        try:
            r = reshape_financial_table(d)
            if r is not None and not r.empty and len(r.columns) >= 6:
                reshaped.append(r)
        except Exception as e:
            logline(f"  -> WARN: Failed to reshape a table: {e}")
    if not reshaped and dfs:
        reshaped = dfs
    if not reshaped:
        return written
    parts = []
    for i, tbl in enumerate(reshaped, start=1):
        parts.append(f"### Table {i}\n\n{md_table(tbl)}\n")
    all_path = OUT_MD / f"{base_name}_tables_all.md"
    write_text(all_path, f"# Tables (all): {base_name}\n\n" + "\n".join(parts))
    written.append(all_path)

    # Write CSV for all tables
    csv_path = OUT_MD / f"{base_name}_tables_all.csv"
    try:
        pd.concat(reshaped, ignore_index=True).to_csv(csv_path, index=False)
        written.append(csv_path)
    except Exception as e:
        logline(f"  -> WARN: Failed to write CSV for all tables: {e}")

    # Coalesce tables by normalized header signature, then pick best preferring clean Acct/Title
    def _norm_cols(cols):
        import re

        return tuple(re.sub(r"[^a-z]", "", str(c).lower()) for c in cols)

    groups = {}
    for d in reshaped:
        key = _norm_cols(d.columns)
        groups.setdefault(key, []).append(d)

    merged_tables = [pd.concat(g, ignore_index=True) for g in groups.values()]

    # Cross-group normalization: normalize all tables to canonical column set and merge
    canonical = [
        "Acct",
        "Account Title",
        "Beginning Balance",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
        "Current Balance",
    ]

    def normalize_cols(df):
        import re

        renamed = {}
        for c in df.columns:
            nm = re.sub(r"[^a-z]", "", str(c).lower())
            # fuzzy map to canonical
            if "beginning" in nm and "balance" in nm:
                renamed[c] = "Beginning Balance"
            elif "currentbalance" in nm or ("current" in nm and "balance" in nm):
                renamed[c] = "Current Balance"
            elif nm in {"acct", "account", "accountid"}:
                renamed[c] = "Acct"
            elif "accounttitle" in nm or ("account" in nm and "title" in nm):
                renamed[c] = "Account Title"
            else:
                # months - match against canonical
                for m in canonical:
                    mm = re.sub(r"[^a-z]", "", m.lower())
                    if mm in nm:
                        renamed[c] = m
                        break

        df2 = df.rename(columns=renamed)
        # Add missing canonical columns
        for col in canonical:
            if col not in df2.columns:
                df2[col] = ""
        # reorder to canonical
        return df2[canonical]

    normalized = [normalize_cols(d) for d in merged_tables]
    all_merged = pd.concat(normalized, ignore_index=True)
    best = all_merged.sort_values(["Acct", "Account Title"]).drop_duplicates(
        subset=["Acct", "Account Title"], keep="last"
    )

    # Log the cross-group merge and deduplication
    total_before = sum(len(d) for d in merged_tables)
    logline(
        f"  -> Cross-group merge: {len(merged_tables)} groups ({total_before} rows) -> {len(best)} unique rows"
    )

    # Drop fully blank rows (no title and no numbers)
    months = [
        "Beginning Balance",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
        "Current Balance",
    ]

    def _drop_blank_rows(df, months):
        tmp = df.copy().replace({None: "", "nan": "", "NaN": ""})
        blank_months = (
            tmp[months].astype(str).apply(lambda s: s.str.strip().eq("")).all(axis=1)
        )
        blank_title = tmp["Account Title"].astype(str).str.strip().eq("")
        return df[~(blank_title & blank_months)]

    best = _drop_blank_rows(best, months)
    if best.empty:
        logline(
            "  -> No usable rows after normalization; skipping tables_full/wide write."
        )
        return written

    # Write a full (coalesced) table for convenience
    full_path = OUT_MD / f"{base_name}_tables_full.md"
    write_text(
        full_path, f"# Table (full/coalesced): {base_name}\n\n{md_table(best)}\n"
    )
    written.append(full_path)
    # CSV for full table
    full_csv_path = OUT_MD / f"{base_name}_tables_full.csv"
    try:
        best.to_csv(full_csv_path, index=False)
        written.append(full_csv_path)
    except Exception as e:
        logline(f"  -> WARN: Failed to write CSV for full table: {e}")

    # Keep wide.md alias to the same best table (for backward compatibility)
    wide_path = OUT_MD / f"{base_name}_tables_wide.md"
    write_text(wide_path, f"# Tables (wide): {base_name}\n\n{md_table(best)}\n")
    written.append(wide_path)
    # CSV for wide table
    wide_csv_path = OUT_MD / f"{base_name}_tables_wide.csv"
    try:
        best.to_csv(wide_csv_path, index=False)
        written.append(wide_csv_path)
    except Exception as e:
        logline(f"  -> WARN: Failed to write CSV for wide table: {e}")

    small = best.copy()
    if small.shape[1] > 16:
        keep = [
            c
            for c in ["Acct", "Account Title", "Current Balance"]
            if c in small.columns
        ]
        if keep:
            small = small[keep]
    small_path = OUT_MD / f"{base_name}_tables.md"
    write_text(small_path, f"## Extracted Tables (local)\n\n{md_table(small)}\n")
    written.append(small_path)

    # Write CSV for small table
    small_csv_path = OUT_MD / f"{base_name}_tables.csv"
    try:
        small.to_csv(small_csv_path, index=False)
        written.append(small_csv_path)
    except Exception as e:
        logline(f"  -> WARN: Failed to write CSV for small table: {e}")

    return written


def pdfs_to_images():
    if convert_from_path is None:
        print(
            f"pdf2image not available. Ensure 'pdf2image' and 'Pillow' are installed."
        )
        return
    if not POPPLER_PATH and not have("pdftoppm"):
        print(
            "Poppler not found. Set POPPLER_PATH in .env to your Poppler 'bin' folder or ensure 'pdftoppm' is on PATH."
        )
        return
    print("\n=== PDF->Image conversion ===")
    print(f"Pages will render to PNG in {OUT_IMG}/<pdfname>_pages")
    from config import INPUT_DIR

    for p in sorted(INPUT_DIR.glob("*.pdf")):
        try:
            print(f"Processing: {p.name}")
            pages = convert_from_path(
                str(p), dpi=200, poppler_path=POPPLER_PATH if POPPLER_PATH else None
            )
            out_dir = OUT_IMG / f"{p.stem}_pages"
            out_dir.mkdir(parents=True, exist_ok=True)
            for i, img in enumerate(pages, start=1):
                outp = out_dir / f"page_{i:03d}.png"
                img.save(outp)
            print(f" -> wrote {len(pages)} images.")
        except Exception as e:
            print(f" -> Failed to convert {p.name}: {e}")


# Function moved to mistral_converter.py
def extract_structured_data_with_schema(
    file_path: Path, base_name: str, schema_type: str = "auto"
) -> dict | None:
    """
    Advanced Mistral processing using structured outputs with JSON schema.
    This provides more predictable and structured output formats.
    """
    if not _ensure_mistral_client():
        return None

    # Define schemas for different document types
    schemas = {
        "financial_statement": {
            "type": "object",
            "properties": {
                "statement_type": {
                    "type": "string",
                    "enum": [
                        "trial_balance",
                        "income_statement",
                        "balance_sheet",
                        "cash_flow",
                    ],
                },
                "period": {"type": "string"},
                "currency": {"type": "string"},
                "accounts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "name": {"type": "string"},
                            "category": {"type": "string"},
                            "balances": {
                                "type": "object",
                                "properties": {
                                    "beginning": {"type": "number"},
                                    "ending": {"type": "number"},
                                    "monthly_changes": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                    },
                                },
                            },
                        },
                        "required": ["code", "name"],
                    },
                },
                "totals": {
                    "type": "object",
                    "properties": {
                        "total_assets": {"type": "number"},
                        "total_liabilities": {"type": "number"},
                        "net_income": {"type": "number"},
                    },
                },
            },
            "required": ["statement_type", "accounts"],
        },
        "document_analysis": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "key_points": {"type": "array", "items": {"type": "string"}},
                "structure": {
                    "type": "object",
                    "properties": {
                        "sections": {"type": "array", "items": {"type": "string"}},
                        "page_count": {"type": "integer"},
                        "has_tables": {"type": "boolean"},
                        "has_images": {"type": "boolean"},
                    },
                },
                "metadata": {
                    "type": "object",
                    "properties": {
                        "author": {"type": "string"},
                        "creation_date": {"type": "string"},
                        "language": {"type": "string"},
                        "confidence_score": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                        },
                    },
                },
            },
            "required": ["title", "summary"],
        },
        "image_description": {
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "objects_detected": {"type": "array", "items": {"type": "string"}},
                "text_content": {"type": "array", "items": {"type": "string"}},
                "visual_elements": {"type": "array", "items": {"type": "string"}},
                "quality_assessment": {
                    "type": "object",
                    "properties": {
                        "clarity": {
                            "type": "string",
                            "enum": ["poor", "fair", "good", "excellent"],
                        },
                        "resolution": {"type": "string"},
                        "artifacts": {"type": "boolean"},
                    },
                },
            },
            "required": ["description"],
        },
    }

    # Auto-detect schema type based on file characteristics
    if schema_type == "auto":
        file_ext = file_path.suffix.lower()
        file_name = file_path.name.lower()

        if any(
            keyword in file_name
            for keyword in ["trial", "balance", "financial", "statement", "ledger"]
        ):
            schema_type = "financial_statement"
        elif file_ext in [".jpg", ".jpeg", ".png", ".tiff"]:
            schema_type = "image_description"
        else:
            schema_type = "document_analysis"

    schema = schemas.get(schema_type)
    if not schema:
        logline(f"  -> ERROR: Unknown schema type: {schema_type}")
        return None

    try:
        # Prepare document for processing
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        selected_model = select_optimal_model(file_path, file_size_mb)

        # Get mistral client (ensure initialized, then use global mistral_client)
        if not _ensure_mistral_client():
            return None

        # Prepare document payload
        if file_path.suffix.lower() == ".pdf" or file_size_mb > LARGE_FILE_THRESHOLD_MB:
            with open(file_path, "rb") as f:
                uploaded_file = mistral_client.files.upload(
                    file={"file_name": file_path.name, "content": f},
                    purpose="ocr",
                )
            document_payload = {
                "type": "file",
                "file_id": uploaded_file.id,
            }
        else:
            with open(file_path, "rb") as f:
                b64_content = base64.b64encode(f.read()).decode("utf-8")
            mime_type = get_mime_type(file_path)
            doc_url = f"data:{mime_type};base64,{b64_content}"
            document_payload = {
                "type": "document_url",
                "document_url": doc_url,
                "document_name": file_path.name,
            }

        # Create structured prompt based on schema type
        prompts = {
            "financial_statement": f"""Extract the financial statement data from this document.
Please identify the statement type, period, and all account information.
Structure the output according to the provided schema.""",
            "document_analysis": f"""Analyze this document and provide a structured summary.
Extract key information including title, summary, main points, and document structure.""",
            "image_description": f"""Describe this image in detail.
Identify objects, text content, visual elements, and assess image quality.""",
        }

        messages = [
            {
                "role": "user",
                "content": prompts.get(
                    schema_type,
                    "Analyze this document and extract structured information.",
                ),
            }
        ]

        # Make API call with structured output
        response = mistral_client.chat(
            model=selected_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and choice.message:
                content = choice.message.content
                try:
                    # Parse the JSON response
                    structured_data = json.loads(content)
                    return {
                        "schema_type": schema_type,
                        "data": structured_data,
                        "metadata": {
                            "model_used": selected_model,
                            "processing_time": datetime.now().isoformat(),
                            "file_name": file_path.name,
                            "file_size_mb": file_size_mb,
                        },
                    }
                except json.JSONDecodeError as e:
                    logline(
                        f"  -> ERROR: Failed to parse structured JSON response: {e}"
                    )
                    return None

        return None

    except Exception as e:
        logline(f"  -> ERROR: Structured output extraction failed: {e}")
        return None
