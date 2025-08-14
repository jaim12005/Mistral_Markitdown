import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path
import re

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
    MARKITDOWN_USE_LLM, MARKITDOWN_LLM_MODEL, MARKITDOWN_LLM_KEY,
    AZURE_DOC_INTEL_ENDPOINT, AZURE_DOC_INTEL_KEY, MAX_RETRIES,
    RETRY_DELAY, MONTHS, M_SHORT, OUT_MD, OUT_IMG, POPPLER_PATH, LOG_DIR
)
from utils import logline, run, write_text, md_table, have

def run_markitdown_enhanced(inp: Path, out_md: Path) -> bool:
    """Enhanced Markitdown with full feature utilization and advanced capabilities."""

    # Try Python API first (more control and features)
    if MarkItDown is not None:
        try:
            logline(f"  -> Using Markitdown Python API with enhanced features...")

            # Initialize with comprehensive configuration
            kwargs = {}
            
            # LLM support for image descriptions
            if MARKITDOWN_USE_LLM and MARKITDOWN_LLM_KEY:
                from openai import OpenAI
                kwargs['llm_client'] = OpenAI(api_key=MARKITDOWN_LLM_KEY)
                kwargs['llm_model'] = MARKITDOWN_LLM_MODEL
                logline(f"  -> LLM image description enabled ({MARKITDOWN_LLM_MODEL})")

            # Azure Document Intelligence integration
            if AZURE_DOC_INTEL_ENDPOINT and AZURE_DOC_INTEL_KEY:
                kwargs['docintel_endpoint'] = AZURE_DOC_INTEL_ENDPOINT
                kwargs['docintel_key'] = AZURE_DOC_INTEL_KEY
                logline(f"  -> Azure Document Intelligence enabled")

            # Enhanced configuration for better output
            md = MarkItDown(**kwargs)

            # Determine file type and apply specific optimizations
            file_ext = inp.suffix.lower()
            file_size_mb = inp.stat().st_size / (1024 * 1024)
            
            # Convert with retry logic and enhanced processing
            for attempt in range(MAX_RETRIES):
                try:
                    # Use stream-based conversion for better memory efficiency
                    with open(inp, 'rb') as file_stream:
                        result = md.convert_stream(file_stream, file_extension=file_ext)

                    # Enhanced content structure with metadata
                    content = create_enhanced_markitdown_output(inp, result, file_size_mb)

                    write_text(out_md, content)
                    logline(f"  -> Success: {out_md.relative_to(OUT_MD.parent)}")
                    
                    # Log processing insights
                    log_processing_insights(inp, result, file_ext)
                    
                    return True

                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        logline(f"  -> Attempt {attempt+1} failed: {e}. Retrying...")
                        time.sleep(RETRY_DELAY)
                    else:
                        raise

        except ImportError:
            logline("  -> Markitdown or dependencies not found. Falling back to CLI...")
        except Exception as e:
            logline(f"  -> Markitdown API failed: {e}. Falling back to CLI...")

    # Enhanced CLI fallback with better options
    return run_markitdown_cli_enhanced(inp, out_md)

def create_enhanced_markitdown_output(inp: Path, result, file_size_mb: float) -> str:
    """Create enhanced markdown output with comprehensive metadata and structure."""
    
    content = f"# {inp.name}\n\n"
    
    # Enhanced metadata section
    content += "## 📄 Document Information\n\n"
    content += f"**Source File**: `{inp.name}`\n"
    content += f"**File Type**: {inp.suffix.upper()[1:]} Document\n"
    content += f"**File Size**: {file_size_mb:.2f} MB\n"
    content += f"**Processed**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    content += f"**Processing Method**: Markitdown Enhanced\n"
    
    # Add document complexity analysis
    text_length = len(result.text_content)
    content += f"**Content Length**: {text_length:,} characters\n"
    content += f"**Estimated Reading Time**: {max(1, text_length // 1000)} minutes\n"
    
    # Document structure analysis
    structure_info = analyze_document_structure(result.text_content)
    if structure_info:
        content += f"\n**Document Structure**:\n"
        for key, value in structure_info.items():
            content += f"- {key}: {value}\n"
    
    content += "\n---\n\n"
    
    # Enhanced content processing
    processed_content = enhance_markdown_content(result.text_content, inp.suffix.lower())
    content += processed_content
    
    # Add processing metadata if available
    if hasattr(result, 'metadata') and result.metadata:
        content += "\n\n---\n\n"
        content += "## 🔍 Processing Metadata\n\n"
        for key, value in result.metadata.items():
            content += f"**{key.replace('_', ' ').title()}**: {value}\n"
    
    return content

def analyze_document_structure(text: str) -> dict:
    """Analyze document structure to provide insights."""
    lines = text.split('\n')
    
    structure = {
        'Total Lines': len(lines),
        'Headers': len([l for l in lines if l.strip().startswith('#')]),
        'Tables': text.count('|') // 2,  # Rough table count
        'Lists': len([l for l in lines if l.strip().startswith(('-', '*', '1.', '2.'))]),
        'Links': text.count('[') + text.count(']('),
        'Code Blocks': text.count('```') // 2,
        'Emphasis': text.count('**') // 2 + text.count('*') // 2
    }
    
    # Filter out zero values for cleaner output
    return {k: v for k, v in structure.items() if v > 0}

def enhance_markdown_content(content: str, file_ext: str) -> str:
    """Apply file-type specific enhancements to markdown content."""
    
    # General enhancements
    enhanced = content
    
    # For Excel files, improve table formatting
    if file_ext in {'.xlsx', '.xls', '.csv'}:
        enhanced = improve_table_formatting(enhanced)
    
    # For presentations, add slide indicators
    if file_ext in {'.pptx', '.ppt'}:
        enhanced = add_slide_indicators(enhanced)
    
    # For Word documents, preserve document structure better
    if file_ext in {'.docx', '.doc'}:
        enhanced = enhance_document_structure(enhanced)
    
    # For web content, clean up HTML artifacts
    if file_ext in {'.html', '.htm'}:
        enhanced = clean_web_content(enhanced)
    
    return enhanced

def improve_table_formatting(content: str) -> str:
    """Improve table formatting in markdown content."""
    lines = content.split('\n')
    enhanced_lines = []
    
    for line in lines:
        # Detect and enhance table rows
        if '|' in line and line.count('|') >= 2:
            # Clean up table formatting
            cells = [cell.strip() for cell in line.split('|')]
            if cells[0] == '':  # Remove leading empty cell
                cells = cells[1:]
            if cells[-1] == '':  # Remove trailing empty cell
                cells = cells[:-1]
            enhanced_line = '| ' + ' | '.join(cells) + ' |'
            enhanced_lines.append(enhanced_line)
        else:
            enhanced_lines.append(line)
    
    return '\n'.join(enhanced_lines)

def add_slide_indicators(content: str) -> str:
    """Add slide indicators for presentation content."""
    # Look for slide breaks (common in PowerPoint conversions)
    enhanced = content.replace('\n\n\n', '\n\n---\n\n**Slide Break**\n\n')
    return enhanced

def enhance_document_structure(content: str) -> str:
    """Enhance document structure for Word documents."""
    lines = content.split('\n')
    enhanced_lines = []
    
    for line in lines:
        # Enhance headings detection
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            # Check if line looks like a heading (all caps, short, etc.)
            if (len(stripped) < 60 and 
                stripped.isupper() and 
                not any(char in stripped for char in '.,;:')):
                enhanced_lines.append(f"## {stripped}")
            else:
                enhanced_lines.append(line)
        else:
            enhanced_lines.append(line)
    
    return '\n'.join(enhanced_lines)

def clean_web_content(content: str) -> str:
    """Clean up HTML conversion artifacts."""
    import re
    
    # Remove common HTML artifacts
    enhanced = content
    enhanced = re.sub(r'\n+', '\n\n', enhanced)  # Normalize line breaks
    enhanced = re.sub(r'&nbsp;', ' ', enhanced)  # Replace non-breaking spaces
    enhanced = re.sub(r'&[a-zA-Z]+;', '', enhanced)  # Remove HTML entities
    
    return enhanced

def run_markitdown_cli_enhanced(inp: Path, out_md: Path) -> bool:
    """Enhanced CLI fallback with better options and error handling."""
    
    # Build enhanced CLI command
    args = [sys.executable, "-m", "markitdown"]
    
    # Add specific options based on file type
    file_ext = inp.suffix.lower()
    if file_ext == '.pdf':
        # For PDFs, we might want specific options
        pass
    elif file_ext in {'.xlsx', '.xls'}:
        # For Excel files, ensure table preservation
        pass
    
    args.extend([str(inp), "-o", str(out_md)])
    
    rc, so, se = run(args, timeout=300)  # Increased timeout
    
    if rc != 0:
        logline(f"  -> markitdown CLI failed (rc={rc}). stderr: {se.strip()}")
        return False
    
    # Post-process CLI output for enhancements
    try:
        if out_md.exists():
            original_content = out_md.read_text(encoding='utf-8')
            enhanced_content = create_enhanced_markitdown_output(
                inp, 
                type('Result', (), {'text_content': original_content, 'metadata': {}})(),
                inp.stat().st_size / (1024 * 1024)
            )
            write_text(out_md, enhanced_content)
    except Exception as e:
        logline(f"  -> Warning: Could not enhance CLI output: {e}")
    
    logline(f"  -> wrote: {out_md.relative_to(OUT_MD.parent)}")
    return True

def log_processing_insights(inp: Path, result, file_ext: str):
    """Log insights about the processing for debugging and optimization."""
    try:
        insights = {
            'file_type': file_ext,
            'content_length': len(result.text_content),
            'processing_time': datetime.now().isoformat(),
            'has_tables': '|' in result.text_content,
            'has_headers': '#' in result.text_content,
            'has_links': '[' in result.text_content and '](' in result.text_content
        }
        
        # Log to debug file if configured
        debug_file = LOG_DIR / "markitdown_insights.jsonl"
        with open(debug_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(insights) + '\n')
            
    except Exception:
        pass  # Silent fail for logging

def try_pdfplumber_tables(pdf_path: Path) -> list["pd.DataFrame"]:
    out = []
    if pdfplumber is None or pd is None:
        return out
    settings = dict(
        vertical_strategy="lines", horizontal_strategy="lines",
        snap_tolerance=6, join_tolerance=4, edge_min_length=24,
        intersection_tolerance=6, text_tolerance=2,
        keep_blank_chars=True, min_words_vertical=1, min_words_horizontal=1,
    )
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                try:
                    for t in page.extract_tables(settings):
                        df = pd.DataFrame(t).dropna(axis=1, how="all")
                        if df.shape[0] >= 2:
                            hdr = df.iloc[0].astype(str).tolist()
                            if any(h.strip() for h in hdr):
                                df.columns = hdr
                                df = df.iloc[1:].reset_index(drop=True)
                            out.append(df)
                except Exception:
                    continue
    except Exception as e:
        logline(f"  -> pdfplumber error: {e}")
    return out

def try_camelot_tables(pdf_path: Path) -> list["pd.DataFrame"]:
    out = []
    if camelot is None or pd is None:
        return out
    flavor = "lattice" if have("gswin64c.exe") or have("gswin32c.exe") or have("gs") else "stream"
    try:
        tables = camelot.read_pdf(str(pdf_path), flavor=flavor, pages="all")
        for t in tables:
            df = t.df
            if df.shape[0] > 1:
                df.columns = df.iloc[0]
                df = df.iloc[1:].reset_index(drop=True)
            out.append(df)
    except Exception:
        pass
    if not out and flavor == "lattice":
        try:
            tables = camelot.read_pdf(str(pdf_path), flavor="stream", pages="all", edge_tol=200, row_tol=12)
            for t in tables:
                out.append(t.df)
        except Exception:
            pass
    return out

def is_month_header(s: str) -> bool:
    s = (s or "").strip().lower()
    return s in [m.lower() for m in MONTHS] or s in [m.lower() for m in M_SHORT]

def reshape_financial_table(df: "pd.DataFrame") -> "pd.DataFrame":
    if pd is None or df is None or df.empty:
        return df
    df = df.copy()

    df.columns = [str(c) for c in df.columns]

    head_row = df.iloc[0].astype(str).str.strip().tolist() if len(df) > 0 else []
    if sum(is_month_header(x) for x in head_row) >= 4:
        df.columns = [c if c else f"col{i}" for i, c in enumerate(head_row)]
        df = df.iloc[1:].reset_index(drop=True)

    left_cols = list(df.columns)[:3]
    acct_col = None
    for c in left_cols:
        sample = " ".join(df[c].astype(str).head(20).tolist())
        if re.search(r"\b\d{4,7}\b", sample):
            acct_col = c
            break

    if acct_col is None:
        acct_col = left_cols[0] if left_cols else (df.columns[0] if len(df.columns) > 0 else None)

    if acct_col is None: return df

    title_col_idx = 1 if len(left_cols) > 1 else (1 if len(df.columns) > 1 else 0)
    title_col = df.columns[title_col_idx]

    # FIX: Split combined "code + title" (e.g., "50113 Cleaning - Other")
    try:
        ser = df[acct_col].astype(str)
        split = ser.str.extract(r"^\s*(?P<_code>\d{4,7})[ \-]+(?P<_title>.+)$")

        if split["_title"].notna().mean() >= 0.6:
            df.insert(0, "Acct", split["_code"].fillna("").str.strip())
            df.insert(1, "Account Title", split["_title"].fillna("").str.strip())
            acct_col, title_col = "Acct", "Account Title"

            def _mostly_zero(s):
                s = s.astype(str).str.strip()
                return ((s == "") | (s == "0") | (s == "0.0") | s.isna()).mean() > 0.8

            original_title_col = left_cols[1] if len(left_cols) > 1 else None
            if original_title_col and original_title_col in df.columns and _mostly_zero(df[original_title_col]):
                 df.drop(columns=[original_title_col], inplace=True, errors="ignore")

    except Exception:
        pass

    # Map month columns
    colmap = {}
    for col in df.columns:
        cl = str(col).strip()
        for m in MONTHS + M_SHORT:
            if cl.lower().startswith(m.lower()[:3]):
                colmap[col] = m
                break

    # Assemble the final DataFrame
    out_cols = [("Acct", acct_col), ("Account Title", title_col)]
    for m in MONTHS:
        src = next((k for k, v in colmap.items() if v == m), None)
        if src is None:
            src = next((k for k in df.columns if str(k).strip().lower().startswith(m.split()[0].lower()[:3])), None)
        out_cols.append((m, src))

    data = {}
    for out_name, src in out_cols:
        if src in df.columns:
            data[out_name] = df[src].astype(str)
        else:
            data[out_name] = [""] * len(df)

    out_df = pd.DataFrame(data)
    keep = out_df["Account Title"].astype(str).str.strip() != ""
    if keep.any():
        out_df = out_df[keep]
    return out_df

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

    # A. Write "All Tables" file (_tables_all.md)
    parts = []
    for i, tbl in enumerate(reshaped, start=1):
        parts.append(f"### Table {i}\n\n{md_table(tbl)}\n")
    all_path = OUT_MD / f"{base_name}_tables_all.md"
    write_text(all_path, f"# Tables (all): {base_name}\n\n" + "\n".join(parts))
    written.append(all_path)

    # B. Write "Wide" (best/widest table)
    best = max(reshaped, key=lambda x: x.shape[1])
    wide_path = OUT_MD / f"{base_name}_tables_wide.md"
    write_text(wide_path, f"# Tables (wide): {base_name}\n\n{md_table(best)}\n")
    written.append(wide_path)

    # C. Write "Compact"
    small = best.copy()
    if small.shape[1] > 16:
        keep = [c for c in ["Acct", "Account Title", "Current Balance"] if c in small.columns]
        if keep:
            small = small[keep]
    small_path = OUT_MD / f"{base_name}_tables.md"
    write_text(small_path, f"## Extracted Tables (local)\n\n{md_table(small)}\n")
    written.append(small_path)

    return written

def pdfs_to_images():
    if convert_from_path is None:
        print(f"pdf2image not available. Ensure 'pdf2image' and 'Pillow' are installed.")
        return

    if not POPPLER_PATH and not have("pdftoppm"):
        print("Poppler not found. Set POPPLER_PATH in .env to your Poppler 'bin' folder or ensure 'pdftoppm' is on PATH.")
        return

    print("\n=== PDF->Image conversion ===")
    # Save page images under the images output directory
    print(f"Pages will render to PNG in {OUT_IMG}/<pdfname>_pages")
    from config import INPUT_DIR
    for p in sorted(INPUT_DIR.glob("*.pdf")):
        try:
            print(f"Processing: {p.name}")
            pages = convert_from_path(str(p), dpi=200, poppler_path=POPPLER_PATH if POPPLER_PATH else None)
            out_dir = OUT_IMG / f"{p.stem}_pages"
            out_dir.mkdir(parents=True, exist_ok=True)
            for i, img in enumerate(pages, start=1):
                outp = out_dir / f"page_{i:03d}.png"
                img.save(outp)
            print(f" -> wrote {len(pages)} images.")
        except Exception as e:
            print(f" -> Failed to convert {p.name}: {e}")
