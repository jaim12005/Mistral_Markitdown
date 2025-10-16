import base64
import json
import time
import traceback
import threading
from pathlib import Path
from collections import Counter
import re
from datetime import datetime
from config import (
    MISTRAL_API_KEY,
    MISTRAL_MODEL,
    MISTRAL_INCLUDE_IMAGES,
    MISTRAL_INCLUDE_IMAGE_ANNOTATIONS,
    SAVE_MISTRAL_JSON,
    LARGE_FILE_THRESHOLD_MB,
    MAX_RETRIES,
    MISTRAL_TIMEOUT,
    CACHE_DIR,
    LOG_DIR,
    OUT_IMG,
    OUT_MD,
    MISTRAL_AUTO_MODEL_SELECTION,
    MISTRAL_PREFERRED_MODELS,
)
from utils import logline, write_text, get_mime_type, get_cache
import os
from typing import Any
from io import BytesIO

# Optional: render PDF pages to images for per-page OCR fallback
try:
    from pdf2image import convert_from_path  # type: ignore
except Exception:
    convert_from_path = None

mistral_client: Any = None
MistralException: Any = Exception  # Fallback-safe
_mistral_lock = threading.Lock()  # Thread safety for client initialization


def _ensure_mistral_client() -> bool:
    """Initialize a Mistral client compatible with multiple SDK layouts (thread-safe)."""
    global mistral_client, MistralException

    # Quick check without lock
    if mistral_client is not None:
        return True

    # Double-checked locking pattern for thread safety
    with _mistral_lock:
        # Check again inside the lock (another thread might have initialized it)
        if mistral_client is not None:
            return True

        api_key = (MISTRAL_API_KEY or os.environ.get("MISTRAL_API_KEY", "")).strip()
        if not api_key:
            logline(
                "  -> ERROR: Mistral client not initialized. Check MISTRAL_API_KEY."
            )
            return False

        # Best effort import of the exception type (optional)
        try:
            from mistralai.exceptions import (
                MistralAPIException as _Exc,
            )  # SDKs where exceptions module exists

            MistralException = _Exc
        except Exception:
            try:
                from mistralai._exceptions import (
                    MistralAPIException as _Exc,
                )  # some older layouts

                MistralException = _Exc
            except Exception:
                MistralException = Exception  # generic fallback

        # Try top-level Mistral (common in v1)
        try:
            from mistralai import Mistral as _SDK

            try:
                mistral_client = _SDK(api_key=api_key, timeout=MISTRAL_TIMEOUT)
            except TypeError:
                mistral_client = _SDK(api_key=api_key)
            return True
        except Exception:
            pass

        # Try client class path (alternate layouts)
        try:
            from mistralai.client import MistralClient as _SDK

            try:
                mistral_client = _SDK(api_key=api_key, timeout=MISTRAL_TIMEOUT)
            except TypeError:
                mistral_client = _SDK(api_key=api_key)
            return True
        except Exception as e_client:
            logline(f"  -> ERROR: Could not import Mistral client class: {e_client}")
            return False


def mistral_ocr_file_enhanced(
    file_path: Path, base_name: str, use_cache: bool = True
) -> dict | None:
    """
    Enhanced Mistral OCR using the official Python SDK and IntelligentCache.
    - Utilizes image annotation and extraction.
    - Now includes intelligent model selection based on file characteristics.
    """
    if not _ensure_mistral_client():
        return None

    # Perform content analysis for intelligent model selection
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    content_analysis = analyze_file_content(file_path)

    # Select optimal model based on file characteristics
    selected_model = select_optimal_model(file_path, file_size_mb, content_analysis)

    logline(
        f"  -> Selected model: {selected_model} (auto-selection: {MISTRAL_AUTO_MODEL_SELECTION})"
    )

    cache = get_cache()
    cache_params = {
        "model": selected_model,
        "include_images": MISTRAL_INCLUDE_IMAGES,
        "image_annotation": MISTRAL_INCLUDE_IMAGE_ANNOTATIONS,
        "sdk_version": "v1+",
    }
    cache_key = cache.get_cache_key(file_path, "mistral_ocr", cache_params)
    if use_cache:
        cached_result = cache.get_cached_result(cache_key)
        if cached_result:
            logline(f"  -> Using cached OCR result (Cache ID: {cache_key[:8]}...)")
            return cached_result

    logline(f"  -> Processing with Mistral OCR (Model: {selected_model})")
    logline(
        f"     Features: Images={MISTRAL_INCLUDE_IMAGES}, Annotation={MISTRAL_INCLUDE_IMAGE_ANNOTATIONS}, Cache={use_cache}"
    )
    logline(
        f"     File analysis: Size={file_size_mb:.1f}MB, Tables={content_analysis.get('has_tables', False)}, Images={content_analysis.get('has_images', False)}"
    )

    try:
        suffix = file_path.suffix.lower()
        is_image = suffix in {
            ".jpg",
            ".jpeg",
            ".png",
            ".tif",
            ".tiff",
            ".bmp",
            ".gif",
            ".webp",
        }
        is_office_doc = suffix in {".docx", ".pptx"}
        doc_url = ""

        # Strategy:
        # - PDFs: always upload via Files API (purpose="ocr")
        # - Large files (> threshold): upload regardless of type
        # - Images (small): send as type=image_url with data URL
        # - Office docs (small): send as type=document_url with data URL
        uploaded_file = None
        if (suffix == ".pdf") or (file_size_mb > LARGE_FILE_THRESHOLD_MB):
            logline(f"  -> Uploading file for OCR ({file_size_mb:.1f} MB)...")
            for attempt in range(MAX_RETRIES):
                try:
                    with open(file_path, "rb") as f:
                        uploaded_file = mistral_client.files.upload(
                            file={"file_name": file_path.name, "content": f},
                            purpose="ocr",
                        )
                    break
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        delay = 5 * (attempt + 1)
                        logline(
                            f"  -> Upload attempt {attempt + 1} failed: {e}. Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                    else:
                        raise Exception(
                            f"File upload failed after {MAX_RETRIES} attempts: {e}"
                        )
            logline(f"  -> File uploaded (ID: {uploaded_file.id}). Processing OCR...")
        else:
            with open(file_path, "rb") as f:
                b64_content = base64.b64encode(f.read()).decode("utf-8")
            mime_type = get_mime_type(file_path)
            doc_url = f"data:{mime_type};base64,{b64_content}"

        # Ensure OCR-compatible model when using the OCR endpoint
        def _coerce_ocr_model(model_name: str) -> str:
            try:
                name = (model_name or "").lower()
            except Exception:
                name = ""
            # Accept any model id that clearly denotes the OCR service
            if "ocr" in name:
                return model_name
            coerced = "mistral-ocr-latest"
            logline(
                f"  -> Note: Coercing model '{model_name}' to '{coerced}' for OCR endpoint compatibility"
            )
            return coerced

        if uploaded_file is not None:
            payload = {
                "type": "file",
                "file_id": uploaded_file.id,
            }
        else:
            if is_image:
                payload = {
                    "type": "image_url",
                    "image_url": {"url": doc_url},
                }
            else:
                payload = {
                    "type": "document_url",
                    "document_url": doc_url,
                    "document_name": file_path.name,
                }

        # OCR call (handle SDK variants) - now using selected_model
        try:
            ocr_response = mistral_client.ocr.process(
                model=_coerce_ocr_model(selected_model),
                document=payload,
                include_image_base64=MISTRAL_INCLUDE_IMAGES,
                include_image_annotation=MISTRAL_INCLUDE_IMAGE_ANNOTATIONS,
            )
        except TypeError:
            ocr_response = mistral_client.ocr.process(
                model=_coerce_ocr_model(selected_model),
                document=payload,
                include_image_base64=MISTRAL_INCLUDE_IMAGES,
            )
        except Exception:
            try:
                ocr_response = mistral_client.ocr.process(
                    model=_coerce_ocr_model(selected_model),
                    document=payload,
                    include_image_base64=MISTRAL_INCLUDE_IMAGES,
                )
            except Exception as e:
                logline(f"  -> ERROR: OCR request failed: {e}")
                return None

        src_doc_type = (
            "file"
            if uploaded_file is not None
            else ("image_url" if is_image else "document_url")
        )
        response_json = ocr_response.model_dump()
        response_json["_source"] = {
            "doc_type": src_doc_type,
            "doc_url": doc_url if uploaded_file is None else None,
            "file_id": getattr(uploaded_file, "id", None),
            "file_path": str(file_path),
            "selected_model": selected_model,
            "auto_selection": MISTRAL_AUTO_MODEL_SELECTION,
        }
        if not response_json.get("pages"):
            logline("  -> Warning: Empty response from Mistral OCR")
            return None

        if use_cache:
            processing_info = {
                "method": "mistral_ocr",
                "parameters": cache_params,
                "file_size_mb": file_size_mb,
                "selected_model": selected_model,
                "content_analysis": content_analysis,
            }
            cache.store_result(cache_key, response_json, file_path, processing_info)
            logline(f"  -> Cached OCR result (Cache ID: {cache_key[:8]}...)")

        if SAVE_MISTRAL_JSON:
            try:
                json_path = (
                    LOG_DIR
                    / f"{base_name}_mistral_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )
                write_text(json_path, json.dumps(response_json, indent=2))
                logline(f"  -> Saved debug JSON to logs/")
            except Exception as e:
                logline(f"  -> WARN: Failed to save debug JSON: {e}")

        return response_json

    except MistralException as e:
        status_code = getattr(e, "status_code", "N/A")
        message = getattr(e, "message", str(e))
        logline(f"  -> FATAL: Mistral API Error (Status: {status_code}): {message}")
        if status_code == 401:
            logline("     -> Please check your MISTRAL_API_KEY.")
        elif status_code == 429:
            logline("     -> Rate limit exceeded. The SDK's retry logic was exhausted.")
        elif isinstance(status_code, int) and status_code >= 500:
            logline("     -> Server error occurred on Mistral's side.")
        return None
    except IOError as e:
        logline(f"  -> FATAL: File I/O error for {file_path.name}: {e}")
        return None
    except Exception as e:
        logline(
            f"  -> FATAL: An unexpected error occurred in Mistral OCR for {file_path.name}: {e}"
        )
        traceback.print_exc()
        return None


def process_mistral_response(resp: dict, base_name: str) -> Path | None:
    try:
        pages = resp.get("pages", [])
        if not pages:
            logline("  -> Mistral OCR returned no pages.")
            return None

        img_dir = OUT_IMG / f"{base_name}_ocr"
        img_dir.mkdir(parents=True, exist_ok=True)
        img_dir_rel = f"../output_images/{img_dir.name}"

        parts = [f"# OCR (Mistral): {base_name}"]
        pages_sorted = sorted(pages, key=lambda p: p.get("index", 0))
        for p in pages_sorted:
            idx = p.get("index", 0) + 1
            parts.append(f"\n\n---\n\n## Page {idx}\n")
            saved_imgs = []
            if MISTRAL_INCLUDE_IMAGES:
                for i, img in enumerate(p.get("images", []) or [], start=1):
                    raw = img.get("image_base64")
                    if not raw:
                        continue
                    fname = img.get("id") or f"page_{idx:03d}_{i:02d}.jpg"
                    try:
                        (img_dir / fname).write_bytes(base64.b64decode(raw))
                        saved_imgs.append(fname)
                    except Exception:
                        continue

            md = (p.get("markdown") or "").strip()
            txt = (p.get("text") or "").strip()
            is_md_poor = False
            if md:
                lines = [
                    line
                    for line in md.split("\n")
                    if line.strip() and not line.strip().startswith("---")
                ]
                if len(lines) > 5:
                    counts = Counter(lines)
                    if counts:
                        most_common_line, count = counts.most_common(1)[0]
                        if count > len(lines) * 0.5:
                            is_md_poor = True

            if md and not is_md_poor:
                content = re.sub(
                    r"\]\(([^)]+\.(jpe?g|png|tiff?))\)",
                    lambda m: f"]({img_dir_rel}/{Path(m.group(1)).name})",
                    md,
                    flags=re.IGNORECASE,
                )
                parts.append(content)
            elif txt:
                logline(
                    f"  -> Page {idx}: Markdown quality poor. Falling back to raw text."
                )
                parts.append(f"*(OCR Text Fallback)*\n\n```text\n{txt}\n```")
            elif saved_imgs:
                logline(f"  -> Page {idx}: No text extracted. Falling back to image.")
                parts.append(
                    f"*(Image Fallback)*\n\n![Page {idx}]({img_dir_rel}/{saved_imgs[0]})"
                )
            else:
                parts.append("*(No content extracted)*")

        out_md = OUT_MD / f"{base_name}_ocr.md"
        write_text(out_md, "\n".join(parts).rstrip() + "\n")
        return out_md

    except Exception as e:
        logline(f"  -> Failed to process Mistral response: {e}")
        traceback.print_exc()
        return None


def _extract_md_tables(md: str, min_columns: int = 3, min_rows: int = 2):
    """Extract markdown tables as structured data and filter spurious tiny tables.

    min_columns: drop tables with fewer than this many columns (often header artifacts)
    min_rows: drop tables with fewer than this many rows
    """
    tables: list[dict] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        if (
            lines[i].lstrip().startswith("|")
            and i + 1 < len(lines)
            and set(lines[i + 1].strip()) <= {"|", "-", " ", ":"}
        ):
            header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if len(row) == len(header):
                    rows.append(row)
                i += 1
            if len(header) >= min_columns and len(rows) >= min_rows:
                tables.append({"columns": header, "rows": rows})
        else:
            i += 1
    return tables


def _clean_repeated_lines(
    page_texts: list[str], max_len: int = 60, min_pages_ratio: float = 0.6
) -> tuple[list[str], set[str]]:
    """Remove header/footer lines that repeat across many pages and collapse duplicates."""
    from collections import Counter

    line_pages = Counter()
    total_pages = len(page_texts)
    for t in page_texts:
        unique_lines = set(l.strip() for l in t.split("\n") if l.strip())
        for l in unique_lines:
            if len(l) <= max_len and "|" not in l:
                line_pages[l] += 1
    common = {
        l
        for l, c in line_pages.items()
        if c >= max(2, int(total_pages * min_pages_ratio))
    }
    cleaned = []
    for t in page_texts:
        out_lines = []
        prev = None
        for l in t.split("\n"):
            s = l.strip()
            if not s:
                continue
            if s in common:
                continue
            if prev is not None and s == prev:
                continue
            out_lines.append(s)
            prev = s
        cleaned.append("\n".join(out_lines))
    return cleaned, common


def extract_structured_content(response_json: dict) -> dict:
    structured = {
        "text_blocks": [],
        "tables": [],
        "images": [],
        "metadata": {
            "total_pages": len(response_json.get("pages", [])),
            "processing_model": response_json.get("model", "unknown"),
            "total_text_length": 0,
            "detected_languages": [],
            "document_structure": {
                "has_headers": False,
                "has_tables": False,
                "has_images": False,
                "has_lists": False,
            },
        },
    }
    try:
        raw_pages: list[str] = []
        pages = response_json.get("pages", [])
        for page_idx, page in enumerate(pages):
            page_md = (page.get("markdown") or "").strip()
            page_txt = (page.get("text") or "").strip()
            if (
                _is_page_md_poor(page_md)
                and page_txt
                and len(page_txt) > len(page_md) * 0.5
            ):
                raw_pages.append(page_txt)
                logline(
                    f"  -> Using raw text for page {page_idx + 1} (markdown quality poor)"
                )
            else:
                raw_pages.append(page_md)

        # Remove common header/footer noise and collapse dupes
        cleaned_pages, common_lines = _clean_repeated_lines(raw_pages)

        for page_idx, page_text in enumerate(cleaned_pages):
            structured["metadata"]["total_text_length"] += len(page_text)
            lines = [l.strip() for l in page_text.split("\n") if l.strip()]

            # Detect structure
            has_md_headers = any(l.startswith("#") for l in lines)
            has_text_headers = any(
                len(l) <= 60 and l.isupper() and not re.search(r"[.,;:]", l)
                for l in lines
            )
            if has_md_headers or has_text_headers:
                structured["metadata"]["document_structure"]["has_headers"] = True
            if "|" in page_text and "-" in page_text:
                structured["metadata"]["document_structure"]["has_tables"] = True
            if any(
                line.strip().startswith(("-", "*", "1."))
                for line in page_text.split("\n")
            ):
                structured["metadata"]["document_structure"]["has_lists"] = True

            text_block = {
                "page": page_idx + 1,
                "content": page_text,
                "length": len(page_text),
                "line_count": len(page_text.split("\n")),
            }
            structured["text_blocks"].append(text_block)

            # Extract structured table data from this page
            # SWE Review Fix: Relaxed min_columns from 4 to 2 for OCR pages
            page_tables = _extract_md_tables(page_text, min_columns=2, min_rows=2)
            if page_tables:
                structured["tables"].extend(
                    [{"page": page_idx + 1, **t} for t in page_tables]
                )

            if page.get("images"):
                structured["metadata"]["document_structure"]["has_images"] = True
                for img_idx, image in enumerate(page.get("images", [])):
                    image_info = {
                        "page": page_idx + 1,
                        "image_index": img_idx,
                        "bbox": {
                            "top_left_x": image.get("top_left_x"),
                            "top_left_y": image.get("top_left_y"),
                            "bottom_right_x": image.get("bottom_right_x"),
                            "bottom_right_y": image.get("bottom_right_y"),
                        },
                        "has_base64": bool(image.get("image_base64")),
                        "description": image.get("image_annotation", ""),
                        "filename": image.get("id")
                        or f"page_{page_idx + 1}_image_{img_idx + 1}.png",
                    }
                    if not Path(image_info["filename"]).suffix:
                        image_info["filename"] += ".png"
                    structured["images"].append(image_info)

        all_text = "\n".join(block["content"] for block in structured["text_blocks"])
        table_indicators = all_text.count("|") + all_text.count("---")
        if table_indicators > 10:
            structured["metadata"]["document_structure"]["has_tables"] = True
    except Exception as e:
        logline(f"Warning: Error extracting structured content: {e}")
    return structured


def create_enhanced_markdown_output(
    response_json: dict, base_name: str, img_dir_rel: str = None
) -> str:
    """
    Create enhanced markdown output with better structure, metadata, and image annotations as captions.
    img_dir_rel: Relative path to saved images for link rewriting.
    """
    structured = extract_structured_content(response_json)

    output = f"# OCR Results: {base_name}\n\n"
    output += f"**Processing Model**: {structured['metadata']['processing_model']}\n"
    output += f"**Total Pages**: {structured['metadata']['total_pages']}\n"
    output += (
        f"**Text Length**: {structured['metadata']['total_text_length']:,} characters\n"
    )
    output += f"**Processing Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    structure = structured["metadata"]["document_structure"]
    output += "**Document Analysis**:\n"
    output += f"- Headers detected: {'✓' if structure['has_headers'] else '✗'}\n"
    output += f"- Tables detected: {'✓' if structure['has_tables'] else '✗'}\n"
    output += f"- Lists detected: {'✓' if structure['has_lists'] else '✗'}\n"
    output += f"- Images detected: {'✓' if structure['has_images'] else '✗'}\n\n"

    if structured["images"]:
        output += f"**Images Found**: {len(structured['images'])} images across {structured['metadata']['total_pages']} pages\n\n"

    output += "---\n\n"

    image_map = {img["filename"]: img for img in structured["images"]}

    if structured["metadata"]["total_pages"] > 1:
        output += "## 📄 Multi-Page Content\n\n"
    else:
        output += "## 📄 Content\n\n"

    def _strip_small_tables(
        md_text: str, min_columns: int = 2, min_rows: int = 2
    ) -> str:
        """Strip small tables that are likely noise.

        SWE Review Fix: Keep wide tables even with just a couple rows; they are likely real.
        Relaxed from min_columns=4 to min_columns=2 to allow OCR header fragments.
        """
        lines = md_text.splitlines()
        out = []
        i = 0
        while i < len(lines):
            if (
                lines[i].lstrip().startswith("|")
                and i + 1 < len(lines)
                and set(lines[i + 1].strip()) <= {"|", "-", " ", ":"}
            ):
                header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                j = i + 2
                rows = []
                while j < len(lines) and lines[j].lstrip().startswith("|"):
                    row = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                    if len(row) == len(header):
                        rows.append(row)
                    j += 1
                # Keep wide tables even with just a couple rows; they are likely real
                if len(header) < min_columns or (len(rows) < min_rows and len(header) < 10):
                    i = j
                    continue
            out.append(lines[i])
            i += 1
        return "\n".join(out)

    for block in structured["text_blocks"]:
        if block["content"].strip():
            if structured["metadata"]["total_pages"] > 1:
                output += f"### Page {block['page']}\n\n"
            # SWE Review Fix: Relaxed min_columns from 4 to 2 for OCR pages
            # This preserves header fragments that help with table reconstruction
            content = _strip_small_tables(block["content"], min_columns=2, min_rows=2)
            if img_dir_rel:

                def rewrite_image_link(match):
                    img_name = Path(match.group(1)).name
                    rel_path = f"{img_dir_rel}/{img_name}"
                    if img_name in image_map and image_map[img_name].get("description"):
                        annotation = image_map[img_name]["description"]
                        return f"]({rel_path})\n\n*Caption (AI): {annotation}*\n\n"
                    return f"]({rel_path})"

                content = re.sub(
                    r"\]\(([^)]+\.(jpe?g|png|tiff?|webp))\)",
                    rewrite_image_link,
                    content,
                    flags=re.IGNORECASE,
                )
            output += content + "\n\n"

    if structured["images"] and not img_dir_rel:
        output += "\n\n---\n\n"
        output += "## 🖼️ Detected Images (Metadata Only)\n\n"
        for img in structured["images"]:
            output += f"### {img['filename']}\n"
            output += f"- **Page**: {img['page']}\n"
            if img["bbox"]:
                output += f"- **Position**: {img['bbox']}\n"
            if img["description"]:
                output += f"- **Description**: {img['description']}\n"
            output += "\n"

    return output


def write_tables_from_ocr(response_json: dict, base_name: str) -> list[Path]:
    """
    Build canonical tables (md + csv) from OCR 'tables' payload.

    Improvements:
    - Score tables by Trial Balance signals (acct/account title + months + rows).
    - Prefer ~15 columns; penalize far-from-15 widths.
    - If 'Acct' is missing but the first text column contains codes, split it.
    - Skip writing if no usable rows (avoid 25-byte empty file).
    """
    from utils import write_text, md_table, normalize_amount
    import pandas as pd

    written: list[Path] = []
    try:
        structured = extract_structured_content(response_json)
        candidates = structured.get("tables") or []
        if not candidates:
            return written

        def _norm(s: str) -> str:
            return re.sub(r"[^a-z]", "", (s or "").lower())

        canon_cols = [
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
        canon_norm = [_norm(c) for c in canon_cols]

        # SWE Review Fix: Add tolerant aliases for common OCR variations
        header_aliases = {
            "beg": "Beginning Balance",
            "begbal": "Beginning Balance",
            "begbalance": "Beginning Balance",
            "beginning": "Beginning Balance",
            "curr": "Current Balance",
            "currbal": "Current Balance",
            "current": "Current Balance",
            "jan": "January",
            "feb": "February",
            "mar": "March",
            "apr": "April",
            "jun": "June",
            "jul": "July",
            "aug": "August",
            "sep": "September",
            "sept": "September",
            "oct": "October",
            "nov": "November",
            "dec": "December",
        }

        month_norms = set(
            _norm(c) for c in canon_cols if c not in {"Acct", "Account Title"}
        )

        def score_table(t: dict) -> float:
            cols = [c.strip() for c in (t.get("columns") or [])]
            rows = t.get("rows") or []
            ncols = len(cols)
            cols_norm = [_norm(c) for c in cols]

            has_acctish = any(
                n.startswith("acct") or ("account" in n and "title" in n)
                for n in cols_norm
            )
            month_hits = sum(1 for n in cols_norm if n in month_norms)
            row_bonus = min(len(rows), 200) / 200.0
            width_penalty = abs(ncols - 15) * 0.25  # prefer ~15 columns

            # Extra boost if both beginning+current balance present
            bc_boost = (
                1.0
                if ("beginningbalance" in cols_norm and "currentbalance" in cols_norm)
                else 0.0
            )

            return (
                (2.0 * has_acctish)
                + (2.0 * bc_boost)
                + (1.5 * month_hits)
                + row_bonus
                - width_penalty
            )

        # Pick the best-scoring table (not just "widest").
        tb = max(candidates, key=score_table)

        cols = [c.strip() for c in tb.get("columns", [])]
        rows = [[c.strip() for c in r] for r in tb.get("rows", [])]
        if not cols or not rows:
            return written

        df = pd.DataFrame(rows, columns=cols)

        # Map columns to canonical names with tolerant matching
        # SWE Review Fix: Use header_aliases for better OCR tolerance
        remap: dict[str, str] = {}
        for c in df.columns:
            n = _norm(str(c))
            if n.startswith("acct"):
                remap[c] = "Acct"
            elif "account" in n and "title" in n:
                remap[c] = "Account Title"
            elif "beginning" in n and "balance" in n:
                remap[c] = "Beginning Balance"
            elif "current" in n and "balance" in n:
                remap[c] = "Current Balance"
            else:
                # Try exact match with aliases first
                if n in header_aliases:
                    remap[c] = header_aliases[n]
                else:
                    # Fallback to fuzzy match against canonical columns
                    for m in canon_cols:
                        if _norm(m) in n:
                            remap[c] = m
                            break

        if remap:
            df = df.rename(columns=remap)

        # Ensure we at least have one text column to split from if Acct is missing
        text_like_cols = [
            c
            for c in df.columns
            if c not in {"Beginning Balance", "Current Balance"}
            and c not in canon_cols[2:]
        ]

        if (
            "Acct" not in df.columns
            and "Account Title" not in df.columns
            and text_like_cols
        ):
            # Try to split the first text-like column into Acct + Account Title
            src = text_like_cols[0]
            ser = df[src].astype(str)
            split = ser.str.extract(
                r"^\s*\(?(?P<_code>\d{3,10})\)?(?:\s*[-–—]?\s+|\s+)(?P<_title>.+?)\s*$"
            )
            if "_code" in split and "_title" in split:
                df.insert(0, "Acct", split["_code"].fillna("").astype(str).str.strip())
                df.insert(
                    1,
                    "Account Title",
                    split["_title"].fillna("").astype(str).str.strip(),
                )
                # If we split from a combined column, drop it if it isn't a month or amount
                if (
                    src not in {"Beginning Balance", "Current Balance"}
                    and src not in canon_cols[2:]
                ):
                    try:
                        df.drop(columns=[src], inplace=True)
                    except Exception:
                        pass

        # Add missing canonical columns and order them
        for m in canon_cols:
            if m not in df.columns:
                df[m] = ""
        df = df[canon_cols]

        # Normalize amounts (month columns only)
        month_cols = [c for c in canon_cols if c not in ("Acct", "Account Title")]
        for c in month_cols:
            df[c] = df[c].map(normalize_amount)

        # SWE Review Fix: Relax filters - keep rows if they have a plausible code OR any amount anywhere
        def _is_code(v: str) -> bool:
            import re as _re
            return bool(_re.fullmatch(r"\d{3,10}", str(v or "").strip()))

        # Keep rows with a code OR a non-empty title OR any numeric-looking month value
        any_amount_mask = df[month_cols].astype(str).apply(
            lambda s: s.str.match(r"^\s*\$?\(?-?[\d,]+(\.\d{1,2})?\)?\s*$", na=False)
        ).any(axis=1) if month_cols else False
        keep_mask = df["Acct"].map(_is_code) | df["Account Title"].astype(str).str.strip().ne("") | any_amount_mask
        df = df[keep_mask]
        # Do NOT drop rows just because all month values are blank; titles + codes are still useful

        # If still empty, try a last-ditch fallback: use the first text-like column as title
        if df.empty and text_like_cols:
            src = text_like_cols[0]
            df = pd.DataFrame(rows, columns=cols)  # rebuild raw
            df.insert(0, "Acct", "")
            df.insert(1, "Account Title", df[src].astype(str).str.strip())
            for m in canon_cols:
                if m not in df.columns:
                    df[m] = ""
            df = df[canon_cols]

        if df.empty:
            # Avoid writing a useless file
            logline(
                "  -> OCR-derived table normalization produced no rows; skipping write."
            )
            return written

        md_path = OUT_MD / f"{base_name}_tables_from_ocr.md"
        csv_path = OUT_MD / f"{base_name}_tables_from_ocr.csv"
        write_text(md_path, "# Tables (from OCR)\n\n" + md_table(df) + "\n")
        try:
            df.to_csv(csv_path, index=False)
            written += [md_path, csv_path]
        except Exception:
            written += [md_path]
        return written

    except Exception as e:
        logline(f"  -> WARN: write_tables_from_ocr failed: {e}")
        return []


def process_mistral_response_enhanced(
    response_json: dict, base_name: str, original_file: Path | None = None
) -> Path | None:
    """Enhanced processing of Mistral OCR response with structured output and image handling."""
    try:
        if original_file and original_file.suffix.lower() == ".pdf":
            pages = response_json.get("pages") or []
            improved_any = False
            for i, p in enumerate(pages):
                md = (p.get("markdown") or "").strip()
                if _is_page_md_poor(md):
                    new_md = None
                    if convert_from_path is not None:
                        new_md = _reprocess_pdf_page_via_image(original_file, i)
                    if not new_md:
                        src = response_json.get("_source") or {}
                        if src.get("doc_type") == "file" and src.get("file_id"):
                            new_md = _reprocess_pdf_page_via_file_id(src["file_id"], i)
                        elif src.get("doc_type") == "document_url" and src.get(
                            "doc_url"
                        ):
                            new_md = _reprocess_pdf_page_via_document_url(
                                src["doc_url"], original_file.name, i
                            )
                    if new_md and len(new_md) > len(md):
                        p["markdown"] = new_md
                        improved_any = True
            if improved_any:
                logline("  -> Improved one or more pages via image-based OCR fallback")

        img_dir = OUT_IMG / f"{base_name}_ocr"
        img_dir_rel = f"../output_images/{img_dir.name}"
        saved_images = []
        if MISTRAL_INCLUDE_IMAGES:
            saved_images = save_extracted_images(response_json, base_name, img_dir)

        enhanced_md = create_enhanced_markdown_output(
            response_json, base_name, img_dir_rel=img_dir_rel if saved_images else None
        )
        ocr_md_path = OUT_MD / f"{base_name}_mistral_ocr.md"
        write_text(ocr_md_path, enhanced_md)

        structured = extract_structured_content(response_json)
        if structured["text_blocks"] or structured["images"]:
            metadata_path = OUT_MD / f"{base_name}_ocr_metadata.json"
            write_text(metadata_path, json.dumps(structured, indent=2, default=str))
            logline(f"  -> Saved structured metadata: {metadata_path.name}")

        logline(f"  -> Enhanced OCR output: {ocr_md_path.name}")

        # New: write canonical tables from OCR (robust selector)
        try:
            written = write_tables_from_ocr(response_json, base_name)
            if written:
                logline(f"  -> Wrote OCR-derived tables: {[p.name for p in written]}")
        except Exception as e:
            logline(f"  -> WARN: Could not write OCR-derived tables: {e}")

        return ocr_md_path

    except Exception as e:
        logline(f"  -> ERROR: Failed to process enhanced OCR response: {e}")
        return None


def select_optimal_model(
    file_path: Path, file_size_mb: float, content_analysis: dict = None
) -> str:
    """
    Intelligently select the best Mistral model based on file characteristics.

    Args:
        file_path: Path to the file being processed
        file_size_mb: Size of the file in MB
        content_analysis: Optional analysis of file content

    Returns:
        str: The recommended model name
    """
    if not MISTRAL_AUTO_MODEL_SELECTION:
        return MISTRAL_MODEL

    file_ext = file_path.suffix.lower()
    base_name = file_path.name.lower()

    # Analyze file characteristics
    is_image = file_ext in {
        ".jpg",
        ".jpeg",
        ".png",
        ".tiff",
        ".tif",
        ".bmp",
        ".gif",
        ".webp",
    }
    is_code_file = file_ext in {
        ".py",
        ".js",
        ".ts",
        ".java",
        ".cpp",
        ".c",
        ".cs",
        ".php",
        ".rb",
        ".go",
        ".rs",
    }
    is_document = file_ext in {".pdf", ".docx", ".pptx", ".xlsx", ".xls"}
    is_large_file = file_size_mb > 20

    # Check for code-related keywords in filename
    code_indicators = any(
        keyword in base_name
        for keyword in [
            "code",
            "script",
            "program",
            "function",
            "class",
            "module",
            "api",
            "sdk",
        ]
    )

    # CRITICAL FIX (SWE Review): Force OCR model for PDFs with tables
    if file_ext == ".pdf":
        # PDFs should use OCR model, especially those with tables
        if "mistral-ocr-latest" in MISTRAL_PREFERRED_MODELS:
            logline("  -> PDF detected: forcing mistral-ocr-latest for table extraction")
            return "mistral-ocr-latest"

    # Prioritize models based on file characteristics
    if is_code_file or code_indicators:
        # Use Codestral for code-heavy content
        if "codestral-latest" in MISTRAL_PREFERRED_MODELS:
            return "codestral-latest"
    elif is_image:
        # Enhanced image analysis for better model selection
        try:
            image_optimization = optimize_image_for_processing(file_path)
            selected_model = image_optimization["model"]
            if selected_model in MISTRAL_PREFERRED_MODELS:
                logline(
                    f"  -> Image optimization: {', '.join(image_optimization['recommendations'][:2])}"
                )
                return selected_model
        except Exception as e:
            logline(f"  -> Image optimization failed, using fallback: {e}")

        # Fallback to pixtral for images
        if "pixtral-large-latest" in MISTRAL_PREFERRED_MODELS:
            return "pixtral-large-latest"
    elif is_large_file or is_document:
        # Use OCR model for documents (already prioritized for PDFs above)
        if "mistral-ocr-latest" in MISTRAL_PREFERRED_MODELS:
            return "mistral-ocr-latest"

    # Check content analysis if available
    if content_analysis:
        has_tables = content_analysis.get("has_tables", False)
        has_images = content_analysis.get("has_images", False)
        has_code = content_analysis.get("has_code", False)
        complexity_score = content_analysis.get("complexity_score", 0)

        if has_code and "codestral-latest" in MISTRAL_PREFERRED_MODELS:
            return "codestral-latest"
        elif (
            has_images or complexity_score > 0.7
        ) and "pixtral-large-latest" in MISTRAL_PREFERRED_MODELS:
            return "pixtral-large-latest"
        elif has_tables and "mistral-medium-latest" in MISTRAL_PREFERRED_MODELS:
            return "mistral-medium-latest"

    # Return first available preferred model or fallback to default
    for model in MISTRAL_PREFERRED_MODELS:
        return model

    return MISTRAL_MODEL


def analyze_file_content(file_path: Path) -> dict:
    """
    Perform basic content analysis to inform model selection.

    Args:
        file_path: Path to the file to analyze

    Returns:
        dict: Analysis results including content characteristics
    """
    analysis = {
        "has_tables": False,
        "has_images": False,
        "has_code": False,
        "complexity_score": 0.0,
        "text_density": 0.0,
    }

    try:
        file_ext = file_path.suffix.lower()

        if file_ext == ".pdf":
            # Try to get basic PDF info without full processing
            try:
                from pypdf import PdfReader

                with open(file_path, "rb") as f:
                    reader = PdfReader(f)
                    num_pages = len(reader.pages)

                    # Sample first few pages for content analysis
                    text_content = ""
                    for i in range(min(3, num_pages)):
                        page = reader.pages[i]
                        text_content += page.extract_text() or ""

                    # Analyze content
                    analysis["has_tables"] = (
                        "|" in text_content or "table" in text_content.lower()
                    )
                    analysis["text_density"] = len(text_content) / max(1, num_pages)
                    analysis["complexity_score"] = min(
                        1.0, (len(text_content) / 10000) + (num_pages / 50)
                    )

            except Exception:
                pass

        elif file_ext in {".docx", ".pptx"}:
            # Office documents often contain complex formatting
            analysis["complexity_score"] = 0.6
            analysis["has_tables"] = True  # Common in office docs

        elif file_ext in {".jpg", ".jpeg", ".png"}:
            # Images have high complexity for vision models
            analysis["has_images"] = True
            analysis["complexity_score"] = 0.8

    except Exception as e:
        logline(f"Warning: Content analysis failed for {file_path.name}: {e}")

    return analysis


def _is_page_md_poor(md: str) -> bool:
    """Enhanced version that preserves wide markdown tables with month columns.

    SWE Review Fix: Keep markdown tables from being flagged as "poor" when they
    contain wide tables with many pipes and month tokens, even if there are repeated lines.
    """
    if not md:
        return True
    s = md.strip()
    # If we have a wide markdown table with many pipes and month tokens, keep it
    pipe_count = s.count("|")
    has_months = any(m in s for m in ["January","February","March","April","May","June","July","August","September","October","November","December","Beginning Balance","Current Balance"])
    has_table_rule = ("| ---" in s) or (":---" in s)
    if pipe_count >= 50 and has_months and has_table_rule:
        return False
    if len(s) < 120:
        return True
    lines = [l for l in s.split("\n") if l.strip() and not l.strip().startswith("---")]
    if len(lines) <= 2:
        return True
    from collections import Counter as _Counter
    counts = _Counter(lines)
    if counts:
        _, c = counts.most_common(1)[0]
        if c > len(lines) * 0.6:
            return True
    return False


def _reprocess_pdf_page_via_image(pdf_path: Path, page_index: int) -> str | None:
    try:
        from config import POPPLER_PATH, MISTRAL_MODEL, MISTRAL_INCLUDE_IMAGES

        if convert_from_path is None:
            return None
        # SWE Review Fix: Increased DPI from 250 to 300 for better OCR precision on small fonts
        images = convert_from_path(
            str(pdf_path),
            dpi=300,
            first_page=page_index + 1,
            last_page=page_index + 1,
            poppler_path=POPPLER_PATH if POPPLER_PATH else None,
        )
        if not images:
            return None
        img = images[0]
        bio = BytesIO()
        img.save(bio, format="PNG")
        img_b64 = base64.b64encode(bio.getvalue()).decode("utf-8")
        if not _ensure_mistral_client():
            return None
        payload = {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img_b64}"},
        }
        ocr_response = mistral_client.ocr.process(
            model=MISTRAL_MODEL,
            document=payload,
            include_image_base64=MISTRAL_INCLUDE_IMAGES,
        )
        rj = ocr_response.model_dump()
        pages = rj.get("pages") or []
        if not pages:
            return None
        return (pages[0].get("markdown") or "").strip()
    except Exception:
        return None


def _reprocess_pdf_page_via_document_url(
    doc_url: str, file_name: str, page_index: int
) -> str | None:
    try:
        from config import MISTRAL_MODEL, MISTRAL_INCLUDE_IMAGES

        if not _ensure_mistral_client():
            return None
        payload = {
            "type": "document_url",
            "document_url": doc_url,
            "document_name": file_name,
        }
        ocr_response = mistral_client.ocr.process(
            model=MISTRAL_MODEL,
            document=payload,
            pages=[page_index],
            include_image_base64=MISTRAL_INCLUDE_IMAGES,
        )
        rj = ocr_response.model_dump()
        pages = rj.get("pages") or []
        if not pages:
            return None
        return (pages[0].get("markdown") or "").strip()
    except Exception:
        return None


def _reprocess_pdf_page_via_file_id(file_id: str, page_index: int) -> str | None:
    try:
        from config import MISTRAL_MODEL, MISTRAL_INCLUDE_IMAGES

        if not _ensure_mistral_client():
            return None
        payload = {
            "type": "file",
            "file_id": file_id,
        }
        ocr_response = mistral_client.ocr.process(
            model=MISTRAL_MODEL,
            document=payload,
            pages=[page_index],
            include_image_base64=MISTRAL_INCLUDE_IMAGES,
        )
        rj = ocr_response.model_dump()
        pages = rj.get("pages") or []
        if not pages:
            return None
        return (pages[0].get("markdown") or "").strip()
    except Exception:
        return None


def save_extracted_images(
    response_json: dict, base_name: str, output_dir: Path
) -> list[Path]:
    """
    Save extracted images from OCR response with enhanced metadata in the specified directory.
    """
    saved_images = []
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        for page_idx, page in enumerate(response_json.get("pages", [])):
            if page.get("images"):
                for img_idx, image in enumerate(page.get("images", [])):
                    if image.get("image_base64"):
                        try:
                            img_data = base64.b64decode(image["image_base64"])
                            # Sanitize OCR image filenames
                            raw_name = (
                                image.get("id")
                                or f"{base_name}_page{page_idx + 1}_img{img_idx + 1}.png"
                            )
                            safe_name = Path(raw_name).name
                            if not Path(safe_name).suffix:
                                safe_name += ".png"
                            img_path = output_dir / safe_name
                            with open(img_path, "wb") as f:
                                f.write(img_data)
                            saved_images.append(img_path)

                            img_metadata = {
                                "source_page": page_idx + 1,
                                "image_index": img_idx + 1,
                                "bbox": {
                                    "top_left_x": image.get("top_left_x"),
                                    "top_left_y": image.get("top_left_y"),
                                    "bottom_right_x": image.get("bottom_right_x"),
                                    "bottom_right_y": image.get("bottom_right_y"),
                                },
                                "description": image.get("image_annotation", ""),
                                "extracted_at": datetime.now().isoformat(),
                                "file_size_bytes": len(img_data),
                            }
                            metadata_path = output_dir / f"{safe_name}.metadata.json"
                            write_text(
                                metadata_path,
                                json.dumps(img_metadata, indent=2, default=str),
                            )
                        except Exception as e:
                            logline(
                                f"  -> Warning: Failed to save image {img_idx + 1} from page {page_idx + 1}: {e}"
                            )
    except Exception as e:
        logline(f"  -> Warning: Error saving extracted images: {e}")

    if saved_images:
        logline(
            f"  -> Saved {len(saved_images)} extracted images to output_images/{output_dir.name}/"
        )
    return saved_images


def extract_structured_data_with_functions(
    file_path: Path, base_name: str, use_cache: bool = True
) -> dict | None:
    """
    Advanced Mistral processing using function calling for structured data extraction.
    This provides more precise and structured output for specific document types.
    """
    if not _ensure_mistral_client():
        return None

    # Define functions for structured extraction
    functions = [
        {
            "name": "extract_financial_table",
            "description": "Extract financial data from tables, especially trial balances and financial statements",
            "parameters": {
                "type": "object",
                "properties": {
                    "accounts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "account_code": {"type": "string"},
                                "account_title": {"type": "string"},
                                "beginning_balance": {"type": "number"},
                                "monthly_balances": {
                                    "type": "object",
                                    "properties": {
                                        "january": {"type": "number"},
                                        "february": {"type": "number"},
                                        "march": {"type": "number"},
                                        "april": {"type": "number"},
                                        "may": {"type": "number"},
                                        "june": {"type": "number"},
                                        "july": {"type": "number"},
                                        "august": {"type": "number"},
                                        "september": {"type": "number"},
                                        "october": {"type": "number"},
                                        "november": {"type": "number"},
                                        "december": {"type": "number"},
                                    },
                                },
                                "current_balance": {"type": "number"},
                            },
                        },
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "statement_type": {"type": "string"},
                            "period": {"type": "string"},
                            "currency": {"type": "string"},
                            "total_accounts": {"type": "integer"},
                        },
                    },
                },
                "required": ["accounts", "metadata"],
            },
        },
        {
            "name": "extract_document_metadata",
            "description": "Extract document metadata and structure information",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "author": {"type": "string"},
                    "creation_date": {"type": "string"},
                    "document_type": {"type": "string"},
                    "page_count": {"type": "integer"},
                    "sections": {"type": "array", "items": {"type": "string"}},
                    "key_topics": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["document_type"],
            },
        },
        {
            "name": "analyze_image_content",
            "description": "Analyze image content for charts, diagrams, and visual elements",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_type": {"type": "string"},
                    "description": {"type": "string"},
                    "contains_charts": {"type": "boolean"},
                    "contains_tables": {"type": "boolean"},
                    "text_elements": {"type": "array", "items": {"type": "string"}},
                    "visual_complexity": {"type": "string"},
                },
                "required": ["image_type", "description"],
            },
        },
    ]

    try:
        # Prepare document for processing
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        selected_model = select_optimal_model(file_path, file_size_mb)

        # Upload file if needed
        uploaded_file = None
        doc_url = ""
        if file_path.suffix.lower() == ".pdf" or file_size_mb > LARGE_FILE_THRESHOLD_MB:
            with open(file_path, "rb") as f:
                uploaded_file = mistral_client.files.upload(
                    file={"file_name": file_path.name, "content": f},
                    purpose="ocr",
                )
            payload = {
                "type": "file",
                "file_id": uploaded_file.id,
            }
        else:
            with open(file_path, "rb") as f:
                b64_content = base64.b64encode(f.read()).decode("utf-8")
            mime_type = get_mime_type(file_path)
            doc_url = f"data:{mime_type};base64,{b64_content}"
            payload = {
                "type": "document_url",
                "document_url": doc_url,
                "document_name": file_path.name,
            }

        # Use function calling for structured extraction
        # CRITICAL FIX: Include the document payload in the message content
        messages = [
            {
                "role": "user",
                "content": [
                    payload,  # Document payload (file_id or document_url)
                    {
                        "type": "text",
                        "text": f"""Please analyze this document and extract structured information using the available functions.

Document: {file_path.name}
Type: {file_path.suffix.upper()[1:] if file_path.suffix else "Unknown"}

Please use the appropriate functions to extract:
1. Financial tables (if present)
2. Document metadata
3. Image analysis (if images are present)

Be thorough and use multiple function calls if needed.""",
                    },
                ],
            }
        ]

        # Make the API call with function calling
        response = mistral_client.chat(
            model=selected_model,
            messages=messages,
            functions=functions,
            function_call="auto",
            temperature=0.1,  # Lower temperature for more structured output
        )

        # Process function calls and their results
        structured_results = {
            "document_analysis": {},
            "financial_data": {},
            "image_analysis": {},
            "metadata": {
                "model_used": selected_model,
                "processing_time": datetime.now().isoformat(),
                "functions_used": [],
            },
        }

        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and choice.message:
                message = choice.message
                if hasattr(message, "function_calls") and message.function_calls:
                    for func_call in message.function_calls:
                        function_name = func_call.name
                        function_args = func_call.arguments
                        structured_results["metadata"]["functions_used"].append(
                            function_name
                        )

                        # Process different function results
                        if function_name == "extract_financial_table":
                            structured_results["financial_data"] = function_args
                        elif function_name == "extract_document_metadata":
                            structured_results["document_analysis"] = function_args
                        elif function_name == "analyze_image_content":
                            structured_results["image_analysis"] = function_args

        return structured_results

    except Exception as e:
        logline(f"  -> ERROR: Advanced function calling failed: {e}")
        return None


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


def analyze_image_quality(file_path: Path) -> dict:
    """
    Analyze image quality and characteristics to optimize processing.

    Args:
        file_path: Path to the image file

    Returns:
        dict: Image quality metrics and recommendations
    """
    try:
        from PIL import Image
        import math

        with Image.open(file_path) as img:
            width, height = img.size
            file_size = file_path.stat().st_size

            # Basic metrics
            megapixels = (width * height) / 1_000_000
            aspect_ratio = width / height if height > 0 else 0
            bits_per_pixel = (
                (file_size * 8) / (width * height) if width * height > 0 else 0
            )

            # Quality assessment
            quality_score = min(1.0, (megapixels / 10) + (bits_per_pixel / 10))

            # Determine image type
            if img.mode == "RGB":
                color_type = "color"
            elif img.mode == "L":
                color_type = "grayscale"
            else:
                color_type = "other"

            # Detect if image contains text (rough heuristic)
            # Convert to grayscale and check contrast
            if img.mode != "L":
                gray_img = img.convert("L")
            else:
                gray_img = img

            # Sample pixels to detect text-like patterns
            pixels = list(gray_img.getdata())
            contrast_ratio = (max(pixels) - min(pixels)) / 255 if pixels else 0

            # Simple text detection based on contrast and file size
            has_text = contrast_ratio > 0.5 and file_size > 50000  # 50KB threshold

            # Complexity assessment
            if megapixels > 5:
                complexity = "high"
            elif megapixels > 2:
                complexity = "medium"
            else:
                complexity = "low"

            return {
                "width": width,
                "height": height,
                "megapixels": megapixels,
                "aspect_ratio": aspect_ratio,
                "file_size_mb": file_size / (1024 * 1024),
                "quality_score": quality_score,
                "color_type": color_type,
                "has_text": has_text,
                "contrast_ratio": contrast_ratio,
                "complexity": complexity,
                "recommended_model": "pixtral-large-latest"
                if (quality_score > 0.6 or has_text)
                else "mistral-ocr-latest",
            }

    except Exception as e:
        logline(f"Warning: Image quality analysis failed for {file_path.name}: {e}")
        return {"error": str(e), "recommended_model": "mistral-ocr-latest"}


def optimize_image_for_processing(file_path: Path) -> dict:
    """
    Optimize image processing based on image characteristics.

    Args:
        file_path: Path to the image file

    Returns:
        dict: Optimization recommendations
    """
    quality_analysis = analyze_image_quality(file_path)

    if "error" in quality_analysis:
        return {
            "model": "mistral-ocr-latest",
            "processing_options": {},
            "recommendations": ["Basic OCR processing due to analysis error"],
        }

    recommendations = []
    processing_options = {}

    # Model selection based on image characteristics
    if quality_analysis["quality_score"] > 0.7:
        model = "pixtral-large-latest"
        recommendations.append(
            "High-quality image detected - using advanced vision model"
        )
    elif quality_analysis["has_text"]:
        model = "pixtral-large-latest"
        recommendations.append("Text content detected - using multimodal model")
    elif quality_analysis["complexity"] == "high":
        model = "pixtral-large-latest"
        recommendations.append("Complex image detected - using advanced vision model")
    else:
        model = "mistral-ocr-latest"
        recommendations.append("Simple image - using standard OCR model")

    # Processing optimizations
    if quality_analysis["megapixels"] > 8:
        processing_options["resize"] = True
        processing_options["max_dimension"] = 2048
        recommendations.append("Large image - will resize for optimal processing")

    if quality_analysis["color_type"] == "grayscale":
        processing_options["enhance_contrast"] = True
        recommendations.append("Grayscale image - will enhance contrast")

    if quality_analysis["contrast_ratio"] < 0.3:
        processing_options["preprocessing"] = "contrast_enhancement"
        recommendations.append("Low contrast detected - will apply enhancement")

    return {
        "model": model,
        "processing_options": processing_options,
        "recommendations": recommendations,
        "quality_analysis": quality_analysis,
    }


def preprocess_image_for_ocr(file_path: Path) -> Path | None:
    """
    Preprocess image to improve OCR accuracy.

    Args:
        file_path: Path to the image file

    Returns:
        Path: Path to preprocessed image, or None if preprocessing failed
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter
        import os

        # Create output path for preprocessed image
        preprocessed_path = (
            file_path.parent / f"{file_path.stem}_preprocessed{file_path.suffix}"
        )

        with Image.open(file_path) as img:
            # Convert to RGB if necessary
            if img.mode not in ["RGB", "L"]:
                img = img.convert("RGB")

            # Apply preprocessing based on image characteristics
            quality_analysis = analyze_image_quality(file_path)

            # Enhance contrast if needed
            if quality_analysis.get("contrast_ratio", 1) < 0.5:
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.5)

            # Sharpen image
            img = img.filter(
                ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3)
            )

            # Resize if too large
            if quality_analysis.get("megapixels", 0) > 8:
                max_dimension = 2048
                width, height = img.size
                if width > height:
                    new_width = max_dimension
                    new_height = int(height * max_dimension / width)
                else:
                    new_height = max_dimension
                    new_width = int(width * max_dimension / height)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Save preprocessed image
            img.save(preprocessed_path, quality=95, optimize=True)
            return preprocessed_path

    except Exception as e:
        logline(f"Warning: Image preprocessing failed for {file_path.name}: {e}")
        return None
