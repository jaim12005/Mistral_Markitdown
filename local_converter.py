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
    MARKITDOWN_TABLE_STRATEGY, MARKITDOWN_IMAGE_STRATEGY, MARKITDOWN_PDF_MODE,
    AZURE_DOC_INTEL_ENDPOINT, AZURE_DOC_INTEL_KEY, MAX_RETRIES,
    RETRY_DELAY, MONTHS, M_SHORT, OUT_MD, OUT_IMG, POPPLER_PATH, LOG_DIR
)
from utils import logline, run, write_text, md_table, have, ErrorRecoveryManager


def run_markitdown_enhanced(inp: Path, out_md: Path) -> bool:
    """Enhanced Markitdown with full feature utilization and advanced capabilities."""
    if MarkItDown is not None:
        try:
            logline(f"  -> Using Markitdown Python API with enhanced features...")

            img_out_dir_name = f"{inp.stem}_markitdown"
            img_out_dir_abs = OUT_IMG / img_out_dir_name

            kwargs = {
                'table_strategy': MARKITDOWN_TABLE_STRATEGY,
                'image_strategy': MARKITDOWN_IMAGE_STRATEGY,
                'output_dir': str(img_out_dir_abs),
            }
            logline(f"    -> Strategies: Table={MARKITDOWN_TABLE_STRATEGY}, Image={MARKITDOWN_IMAGE_STRATEGY}")

            if MARKITDOWN_USE_LLM and MARKITDOWN_LLM_KEY:
                from openai import OpenAI
                kwargs['llm_client'] = OpenAI(api_key=MARKITDOWN_LLM_KEY)
                kwargs['llm_model'] = MARKITDOWN_LLM_MODEL
                logline(f"    -> LLM image description enabled ({MARKITDOWN_LLM_MODEL})")

            if AZURE_DOC_INTEL_ENDPOINT and AZURE_DOC_INTEL_KEY:
                kwargs['docintel_endpoint'] = AZURE_DOC_INTEL_ENDPOINT
                kwargs['docintel_key'] = AZURE_DOC_INTEL_KEY
                logline(f"    -> Azure Document Intelligence enabled")

            md = MarkItDown(**kwargs)

            file_ext = inp.suffix.lower()
            file_size_mb = inp.stat().st_size / (1024 * 1024)

            error_manager = ErrorRecoveryManager(max_retries=MAX_RETRIES, backoff_factor=max(1.5, RETRY_DELAY / 3.0))

            def conversion_attempt():
                with open(inp, 'rb') as file_stream:
                    options = {}
                    if file_ext == '.pdf' and not (AZURE_DOC_INTEL_ENDPOINT and AZURE_DOC_INTEL_KEY):
                        options['pdf_mode'] = MARKITDOWN_PDF_MODE
                    result = md.convert_stream(
                        file_stream,
                        file_extension=file_ext.lstrip('.'),
                        options=options
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
                logline(f"  -> Markitdown API failed after {MAX_RETRIES} attempts: {e}. Falling back to CLI...")

        except ImportError as e:
            logline(f"  -> Markitdown or dependencies (like OpenAI/Azure SDKs) not found: {e}. Falling back to CLI...")
        except Exception as e:
            logline(f"  -> Markitdown initialization failed: {e}. Falling back to CLI...")

    return run_markitdown_cli_enhanced(inp, out_md)


def create_enhanced_markitdown_output(inp: Path, result, file_size_mb: float) -> str:
    """Create enhanced markdown output with YAML frontmatter and structure."""
    text_content = getattr(result, 'text_content', '')
    text_length = len(text_content)
    structure_info = analyze_document_structure(text_content)

    content = "---\n"
    content += f"title: \"{inp.name}\"\n"
    content += f"source_file: \"{inp.name}\"\n"
    content += f"file_type: {inp.suffix.upper()[1:]}\n"
    content += f"file_size_mb: {file_size_mb:.2f}\n"
    content += f"processed_at: {datetime.now().isoformat()}\n"
    content += f"processing_method: Markitdown Enhanced\n"
    content += f"content_length_chars: {text_length}\n"
    content += f"estimated_reading_time_min: {max(1, text_length // 1500)}\n"
    if structure_info:
        content += "document_structure:\n"
        for key, value in structure_info.items():
            yaml_key = key.lower().replace(' ', '_')
            content += f"  {yaml_key}: {value}\n"
    content += "---\n\n"
    content += f"# {inp.name}\n\n"
    processed_content = enhance_markdown_content(text_content, inp.suffix.lower())
    content += processed_content
    if hasattr(result, 'metadata') and result.metadata:
        content += "\n\n---\n\n"
        content += "## 🔍 Processing Metadata (Appendix)\n\n"
        for key, value in result.metadata.items():
            content += f"**{key.replace('_', ' ').title()}**: {value}\n"
    return content


def rewrite_markitdown_image_links(content: str, img_dir_rel: str) -> str:
    """Rewrite Markitdown-generated image links to standardized relative path."""
    def replacer(match):
        original_path = match.group(1)
        if original_path.startswith(('http://', 'https://', 'data:')):
            return match.group(0)
        image_name = Path(original_path).name
        return f"]({img_dir_rel}/{image_name})"
    return re.sub(r"\]\((.*?)\)", replacer, content)


def analyze_document_structure(text: str) -> dict:
    lines = text.split('\n')
    structure = {
        'Total Lines': len(lines),
        'Headers': len([l for l in lines if l.strip().startswith('#')]),
        'Tables': text.count('|'),
        'Lists': len([l for l in lines if l.strip().startswith(('-', '*', '1.', '2.'))]),
        'Links': text.count('[') + text.count(']('),
        'Code Blocks': text.count('```'),
        'Emphasis': text.count('**'),
    }
    return {k: v for k, v in structure.items() if v > 0}


def enhance_markdown_content(content: str, file_ext: str) -> str:
    enhanced = content
    if file_ext in {'.xlsx', '.xls', '.csv'}:
        enhanced = improve_table_formatting(enhanced)
    if file_ext in {'.pptx', '.ppt'}:
        enhanced = add_slide_indicators(enhanced)
    if file_ext in {'.docx', '.doc'}:
        enhanced = enhance_document_structure(enhanced)
    if file_ext in {'.html', '.htm'}:
        enhanced = clean_web_content(enhanced)
    return enhanced


def improve_table_formatting(content: str) -> str:
    lines = content.split('\n')
    enhanced_lines = []
    for line in lines:
        if '|' in line and line.count('|') >= 2:
            cells = [cell.strip() for cell in line.split('|')]
            if cells[0] == '':
                cells = cells[1:]
            if cells[-1] == '':
                cells = cells[:-1]
            enhanced_line = '| ' + ' | '.join(cells) + ' |'
            enhanced_lines.append(enhanced_line)
        else:
            enhanced_lines.append(line)
    return '\n'.join(enhanced_lines)


def add_slide_indicators(content: str) -> str:
    enhanced = content.replace('\n\n\n', '\n\n---\n\n**Slide Break**\n\n')
    return enhanced


def enhance_document_structure(content: str) -> str:
    lines = content.split('\n')
    enhanced_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
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
    import re as _re
    enhanced = content
    enhanced = _re.sub(r'\n+', '\n\n', enhanced)
    enhanced = _re.sub(r'&nbsp;', ' ', enhanced)
    enhanced = _re.sub(r'&[a-zA-Z]+;', '', enhanced)
    return enhanced


def run_markitdown_cli_enhanced(inp: Path, out_md: Path) -> bool:
    """Enhanced CLI fallback with better options and error handling."""
    args = [sys.executable, "-m", "markitdown"]

    img_out_dir_name = f"{inp.stem}_markitdown"
    img_out_dir_abs = OUT_IMG / img_out_dir_name
    args.extend(["--output-dir", str(img_out_dir_abs)])

    args.extend(["--table-strategy", MARKITDOWN_TABLE_STRATEGY])
    args.extend(["--image-strategy", MARKITDOWN_IMAGE_STRATEGY])

    file_ext = inp.suffix.lower()
    if file_ext == '.pdf':
        if not (AZURE_DOC_INTEL_ENDPOINT and AZURE_DOC_INTEL_KEY):
            args.extend(["--pdf-mode", MARKITDOWN_PDF_MODE])

    args.extend([str(inp), "-o", str(out_md)])
    rc, so, se = run(args, timeout=300)
    if rc != 0:
        logline(f"  -> markitdown CLI failed (rc={rc}). stderr: {se.strip()}")
        return False
    try:
        if out_md.exists():
            original_content = out_md.read_text(encoding='utf-8')
            mock_result = type('Result', (), {'text_content': original_content, 'metadata': {'source': 'CLI'}})()
            enhanced_content = create_enhanced_markitdown_output(
                inp,
                mock_result,
                inp.stat().st_size / (1024 * 1024)
            )
            img_dir_rel = f"../output_images/{img_out_dir_name}"
            enhanced_content = rewrite_markitdown_image_links(enhanced_content, img_dir_rel)
            write_text(out_md, enhanced_content)
    except Exception as e:
        logline(f"  -> Warning: Could not enhance CLI output: {e}")
    logline(f"  -> wrote: {out_md.relative_to(OUT_MD.parent)}")
    return True


def log_processing_insights(inp: Path, result, file_ext: str):
    try:
        insights = {
            'file_type': file_ext,
            'content_length': len(result.text_content),
            'processing_time': datetime.now().isoformat(),
            'has_tables': '|' in result.text_content,
            'has_headers': '#' in result.text_content,
            'has_links': '[' in result.text_content and '](' in result.text_content
        }
        debug_file = LOG_DIR / "markitdown_insights.jsonl"
        with open(debug_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(insights) + '\n')
    except Exception:
        pass


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
    if acct_col is None:
        return df
    title_col_idx = 1 if len(left_cols) > 1 else (1 if len(df.columns) > 1 else 0)
    title_col = df.columns[title_col_idx]
    try:
        ser = df[acct_col].astype(str)
        split = ser.str.extract(r"^\s*(?P<_code>\d{4,7})[ \-]+(?P<_title>.+)$")
        if split["_title"].notna().mean() >= 0.6:
            df.insert(0, "Acct", split["_code"].str.strip().fillna(""))
            df.insert(1, "Account Title", split["_title"].str.strip().fillna(""))
            acct_col, title_col = "Acct", "Account Title"

            def _mostly_zero(s):
                s = s.astype(str).str.strip()
                return ((s == "") | (s == "0") | (s == "0.0") | s.isna()).mean() > 0.8

            original_title_col = left_cols[1] if len(left_cols) > 1 else None
            if original_title_col and original_title_col in df.columns and _mostly_zero(df[original_title_col]):
                df.drop(columns=[original_title_col], inplace=True, errors="ignore")
    except Exception:
        pass
    colmap = {}
    for col in df.columns:
        cl = str(col).strip()
        for m in MONTHS + M_SHORT:
            if cl.lower().startswith(m.lower()[:3]):
                colmap[col] = m
                break
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
    parts = []
    for i, tbl in enumerate(reshaped, start=1):
        parts.append(f"### Table {i}\n\n{md_table(tbl)}\n")
    all_path = OUT_MD / f"{base_name}_tables_all.md"
    write_text(all_path, f"# Tables (all): {base_name}\n\n" + "\n".join(parts))
    written.append(all_path)
    best = max(reshaped, key=lambda x: x.shape[1])
    wide_path = OUT_MD / f"{base_name}_tables_wide.md"
    write_text(wide_path, f"# Tables (wide): {base_name}\n\n{md_table(best)}\n")
    written.append(wide_path)
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
