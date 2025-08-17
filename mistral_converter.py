import base64
import json
import time
import traceback
from pathlib import Path
from collections import Counter
import re
from datetime import datetime
from config import (
    MISTRAL_API_KEY, MISTRAL_MODEL, MISTRAL_INCLUDE_IMAGES, MISTRAL_INCLUDE_IMAGE_ANNOTATIONS,
    SAVE_MISTRAL_JSON,
    LARGE_FILE_THRESHOLD_MB, MAX_RETRIES, MISTRAL_TIMEOUT, CACHE_DIR, LOG_DIR, OUT_IMG, OUT_MD
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


def _ensure_mistral_client() -> bool:
    """Initialize a Mistral client compatible with multiple SDK layouts."""
    global mistral_client, MistralException
    if mistral_client is not None:
        return True

    api_key = (MISTRAL_API_KEY or os.environ.get("MISTRAL_API_KEY", "")).strip()
    if not api_key:
        logline("  -> ERROR: Mistral client not initialized. Check MISTRAL_API_KEY.")
        return False

    # Best effort import of the exception type (optional)
    try:
        from mistralai.exceptions import MistralAPIException as _Exc  # SDKs where exceptions module exists
        MistralException = _Exc
    except Exception:
        try:
            from mistralai._exceptions import MistralAPIException as _Exc  # some older layouts
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
    except Exception as e_top:
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


def mistral_ocr_file_enhanced(file_path: Path, base_name: str, use_cache: bool = True) -> dict | None:
    """
    Enhanced Mistral OCR using the official Python SDK and IntelligentCache.
    - Utilizes image annotation and extraction.
    """
    if not _ensure_mistral_client():
        return None

    cache = get_cache()
    cache_params = {
        "model": MISTRAL_MODEL,
        "include_images": MISTRAL_INCLUDE_IMAGES,
        "image_annotation": MISTRAL_INCLUDE_IMAGE_ANNOTATIONS,
        "sdk_version": "v1+"
    }
    cache_key = cache.get_cache_key(file_path, "mistral_ocr", cache_params)

    if use_cache:
        cached_result = cache.get_cached_result(cache_key)
        if cached_result:
            logline(f"  -> Using cached OCR result (Cache ID: {cache_key[:8]}...)")
            return cached_result

    logline(f"  -> Processing with Mistral OCR (Model: {MISTRAL_MODEL})")
    logline(f"     Features: Images={MISTRAL_INCLUDE_IMAGES}, Annotation={MISTRAL_INCLUDE_IMAGE_ANNOTATIONS}, Cache={use_cache}")

    try:
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        suffix = file_path.suffix.lower()
        is_image = suffix in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
        doc_type = "image_url" if is_image else "document_url"
        doc_url = ""

        # Prefer file upload for PDFs and large images; otherwise inline image via data URL
        uploaded_file = None
        if (suffix == ".pdf") or (file_size_mb > LARGE_FILE_THRESHOLD_MB):
            logline(f"  -> Uploading file for OCR ({file_size_mb:.1f} MB)...")
            for attempt in range(MAX_RETRIES):
                try:
                    with open(file_path, "rb") as f:
                        # Use dict-style payload (expected by mistralai SDK)
                        uploaded_file = mistral_client.files.upload(
                            file={"file_name": file_path.name, "content": f},
                            purpose="ocr",
                        )
                    break
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        delay = 5 * (attempt + 1)
                        logline(f"  -> Upload attempt {attempt+1} failed: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        raise Exception(f"File upload failed after {MAX_RETRIES} attempts: {e}")
            logline(f"  -> File uploaded (ID: {uploaded_file.id}). Processing OCR...")
        else:
            with open(file_path, "rb") as f:
                b64_content = base64.b64encode(f.read()).decode("utf-8")
            mime_type = get_mime_type(file_path)
            doc_url = f"data:{mime_type};base64,{b64_content}"

        if uploaded_file is not None:
            payload = {
                "type": "file",
                "file_id": uploaded_file.id,
            }
        else:
            payload = {
                "type": "image_url",
                "image_url": {"url": doc_url},
            }

        # Call OCR endpoint with compatibility for include_image_annotation
        try:
            ocr_response = mistral_client.ocr.process(
                model=MISTRAL_MODEL,
                document=payload,
                include_image_base64=MISTRAL_INCLUDE_IMAGES,
                include_image_annotation=MISTRAL_INCLUDE_IMAGE_ANNOTATIONS,
            )
        except TypeError:
            # Older SDKs may not support include_image_annotation
            ocr_response = mistral_client.ocr.process(
                model=MISTRAL_MODEL,
                document=payload,
                include_image_base64=MISTRAL_INCLUDE_IMAGES,
            )

        response_json = ocr_response.model_dump()
        response_json['_source'] = {
            'doc_type': 'file' if (uploaded_file is not None) else doc_type,
            'doc_url': doc_url if uploaded_file is None else None,
            'file_id': getattr(uploaded_file, 'id', None),
            'file_path': str(file_path),
        }
        if not response_json.get('pages'):
            logline("  -> Warning: Empty response from Mistral OCR")
            return None

        if use_cache:
            processing_info = {
                "method": "mistral_ocr",
                "parameters": cache_params,
                "file_size_mb": file_size_mb
            }
            cache.store_result(cache_key, response_json, file_path, processing_info)
            logline(f"  -> Cached OCR result (Cache ID: {cache_key[:8]}...)")

        if SAVE_MISTRAL_JSON:
            try:
                json_path = LOG_DIR / f"{base_name}_mistral_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                write_text(json_path, json.dumps(response_json, indent=2))
                logline(f"  -> Saved debug JSON to logs/")
            except Exception as e:
                logline(f"  -> WARN: Failed to save debug JSON: {e}")
        return response_json
    except MistralException as e:
        status_code = getattr(e, 'status_code', 'N/A')
        message = getattr(e, 'message', str(e))
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
        logline(f"  -> FATAL: An unexpected error occurred in Mistral OCR for {file_path.name}: {e}")
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
                lines = [line for line in md.split('\n') if line.strip() and not line.strip().startswith("---")]
                if len(lines) > 5:
                    counts = Counter(lines)
                    if counts:
                        most_common_line, count = counts.most_common(1)[0]
                        if count > len(lines) * 0.5:
                            is_md_poor = True
            if md and not is_md_poor:
                content = re.sub(r"\]\(([^)]+\.(jpe?g|png|tiff?))\)",
                                 lambda m: f"]({img_dir_rel}/{Path(m.group(1)).name})", md, flags=re.IGNORECASE)
                parts.append(content)
            elif txt:
                logline(f"  -> Page {idx}: Markdown quality poor. Falling back to raw text.")
                parts.append(f"*(OCR Text Fallback)*\n\n```text\n{txt}\n```")
            elif saved_imgs:
                logline(f"  -> Page {idx}: No text extracted. Falling back to image.")
                parts.append(f"*(Image Fallback)*\n\n![Page {idx}]({img_dir_rel}/{saved_imgs[0]})")
            else:
                parts.append("*(No content extracted)*")
        out_md = OUT_MD / f"{base_name}_ocr.md"
        write_text(out_md, "\n".join(parts).rstrip() + "\n")
        return out_md
    except Exception as e:
        logline(f"  -> Failed to process Mistral response: {e}")
        traceback.print_exc()
        return None


def extract_structured_content(response_json: dict) -> dict:
    structured = {
        'text_blocks': [],
        'tables': [],
        'images': [],
        'metadata': {
            'total_pages': len(response_json.get('pages', [])),
            'processing_model': response_json.get('model', 'unknown'),
            'total_text_length': 0,
            'detected_languages': set(),
            'document_structure': {
                'has_headers': False,
                'has_tables': False,
                'has_images': False,
                'has_lists': False
            }
        }
    }
    try:
        for page_idx, page in enumerate(response_json.get('pages', [])):
            page_text = page.get('markdown', '')
            structured['metadata']['total_text_length'] += len(page_text)
            if any(line.startswith('#') for line in page_text.split('\n')):
                structured['metadata']['document_structure']['has_headers'] = True
            if '|' in page_text and '-' in page_text:
                structured['metadata']['document_structure']['has_tables'] = True
            if any(line.strip().startswith(('-', '*', '1.')) for line in page_text.split('\n')):
                structured['metadata']['document_structure']['has_lists'] = True
            text_block = {
                'page': page_idx + 1,
                'content': page_text,
                'length': len(page_text),
                'line_count': len(page_text.split('\n'))
            }
            structured['text_blocks'].append(text_block)
            if page.get('images'):
                structured['metadata']['document_structure']['has_images'] = True
                for img_idx, image in enumerate(page.get('images', [])):
                    image_info = {
                        'page': page_idx + 1,
                        'image_index': img_idx,
                        'bbox': {
                            'top_left_x': image.get('top_left_x'),
                            'top_left_y': image.get('top_left_y'),
                            'bottom_right_x': image.get('bottom_right_x'),
                            'bottom_right_y': image.get('bottom_right_y'),
                        },
                        'has_base64': bool(image.get('image_base64')),
                        'description': image.get('image_annotation', ''),
                        'filename': image.get('id') or f'page_{page_idx+1}_image_{img_idx+1}.png'
                    }
                    if not Path(image_info['filename']).suffix:
                        image_info['filename'] += ".png"
                    structured['images'].append(image_info)
        all_text = '\n'.join(block['content'] for block in structured['text_blocks'])
        table_indicators = all_text.count('|') + all_text.count('---')
        if table_indicators > 10:
            structured['metadata']['document_structure']['has_tables'] = True
    except Exception as e:
        logline(f"Warning: Error extracting structured content: {e}")
    return structured


def create_enhanced_markdown_output(response_json: dict, base_name: str, img_dir_rel: str = None) -> str:
    """
    Create enhanced markdown output with better structure, metadata, and image annotations as captions.
    img_dir_rel: Relative path to saved images for link rewriting.
    """
    structured = extract_structured_content(response_json)
    output = f"# OCR Results: {base_name}\n\n"
    output += f"**Processing Model**: {structured['metadata']['processing_model']}\n"
    output += f"**Total Pages**: {structured['metadata']['total_pages']}\n"
    output += f"**Text Length**: {structured['metadata']['total_text_length']:,} characters\n"
    output += f"**Processing Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    structure = structured['metadata']['document_structure']
    output += "**Document Analysis**:\n"
    output += f"- Headers detected: {'✓' if structure['has_headers'] else '✗'}\n"
    output += f"- Tables detected: {'✓' if structure['has_tables'] else '✗'}\n"
    output += f"- Lists detected: {'✓' if structure['has_lists'] else '✗'}\n"
    output += f"- Images detected: {'✓' if structure['has_images'] else '✗'}\n\n"
    if structured['images']:
        output += f"**Images Found**: {len(structured['images'])} images across {structured['metadata']['total_pages']} pages\n\n"
    output += "---\n\n"

    image_map = {img['filename']: img for img in structured['images']}

    if structured['metadata']['total_pages'] > 1:
        output += "## 📄 Multi-Page Content\n\n"
    else:
        output += "## 📄 Content\n\n"

    for block in structured['text_blocks']:
        if block['content'].strip():
            if structured['metadata']['total_pages'] > 1:
                output += f"### Page {block['page']}\n\n"
            content = block['content']
            if img_dir_rel:
                def rewrite_image_link(match):
                    img_name = Path(match.group(1)).name
                    rel_path = f"{img_dir_rel}/{img_name}"
                    if img_name in image_map and image_map[img_name].get('description'):
                        annotation = image_map[img_name]['description']
                        return f"]({rel_path})\n\n*Caption (AI): {annotation}*\n\n"
                    return f"]({rel_path})"
                content = re.sub(r"\]\(([^)]+\.(jpe?g|png|tiff?|webp))\)",
                                 rewrite_image_link, content, flags=re.IGNORECASE)
            output += content + "\n\n"

    if structured['images'] and not img_dir_rel:
        output += "\n\n---\n\n"
        output += "## 🖼️ Detected Images (Metadata Only)\n\n"
        for img in structured['images']:
            output += f"### {img['filename']}\n"
            output += f"- **Page**: {img['page']}\n"
            if img['bbox']:
                output += f"- **Position**: {img['bbox']}\n"
            if img['description']:
                output += f"- **Description**: {img['description']}\n"
            output += "\n"
    return output


def process_mistral_response_enhanced(response_json: dict, base_name: str, original_file: Path | None = None) -> Path | None:
    """Enhanced processing of Mistral OCR response with structured output and image handling."""
    try:
        if original_file and original_file.suffix.lower() == ".pdf":
            pages = response_json.get('pages') or []
            improved_any = False
            for i, p in enumerate(pages):
                md = (p.get('markdown') or '').strip()
                if _is_page_md_poor(md):
                    new_md = None
                    if convert_from_path is not None:
                        new_md = _reprocess_pdf_page_via_image(original_file, i)
                    if not new_md:
                        src = response_json.get('_source') or {}
                        if src.get('doc_type') == 'file' and src.get('file_id'):
                            new_md = _reprocess_pdf_page_via_file_id(src['file_id'], i)
                        elif src.get('doc_type') == 'document_url' and src.get('doc_url'):
                            new_md = _reprocess_pdf_page_via_document_url(src['doc_url'], original_file.name, i)
                    if new_md and len(new_md) > len(md):
                        p['markdown'] = new_md
                        improved_any = True
            if improved_any:
                logline("  -> Improved one or more pages via image-based OCR fallback")

        img_dir = OUT_IMG / f"{base_name}_ocr"
        img_dir_rel = f"../output_images/{img_dir.name}"

        saved_images = []
        if MISTRAL_INCLUDE_IMAGES:
            saved_images = save_extracted_images(response_json, base_name, img_dir)

        enhanced_md = create_enhanced_markdown_output(
            response_json,
            base_name,
            img_dir_rel=img_dir_rel if saved_images else None
        )

        ocr_md_path = OUT_MD / f"{base_name}_mistral_ocr.md"
        write_text(ocr_md_path, enhanced_md)

        structured = extract_structured_content(response_json)
        if structured['text_blocks'] or structured['images']:
            metadata_path = OUT_MD / f"{base_name}_ocr_metadata.json"
            write_text(metadata_path, json.dumps(structured, indent=2, default=str))
            logline(f"  -> Saved structured metadata: {metadata_path.name}")
        logline(f"  -> Enhanced OCR output: {ocr_md_path.name}")
        return ocr_md_path
    except Exception as e:
        logline(f"  -> ERROR: Failed to process enhanced OCR response: {e}")
        return None


def _is_page_md_poor(md: str) -> bool:
    if not md or len(md.strip()) < 120:
        return True
    lines = [l for l in md.split('\n') if l.strip() and not l.strip().startswith('---')]
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
        images = convert_from_path(
            str(pdf_path),
            dpi=250,
            first_page=page_index + 1,
            last_page=page_index + 1,
            poppler_path=POPPLER_PATH if POPPLER_PATH else None,
        )
        if not images:
            return None
        img = images[0]
        bio = BytesIO()
        img.save(bio, format='PNG')
        img_b64 = base64.b64encode(bio.getvalue()).decode('utf-8')
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
        pages = rj.get('pages') or []
        if not pages:
            return None
        return (pages[0].get('markdown') or '').strip()
    except Exception:
        return None


def _reprocess_pdf_page_via_document_url(doc_url: str, file_name: str, page_index: int) -> str | None:
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
        pages = rj.get('pages') or []
        if not pages:
            return None
        return (pages[0].get('markdown') or '').strip()
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
        pages = rj.get('pages') or []
        if not pages:
            return None
        return (pages[0].get('markdown') or '').strip()
    except Exception:
        return None


def save_extracted_images(response_json: dict, base_name: str, output_dir: Path) -> list[Path]:
    """
    Save extracted images from OCR response with enhanced metadata in the specified directory.
    """
    saved_images = []
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        for page_idx, page in enumerate(response_json.get('pages', [])):
            if page.get('images'):
                for img_idx, image in enumerate(page.get('images', [])):
                    if image.get('image_base64'):
                        try:
                            img_data = base64.b64decode(image['image_base64'])
                            img_filename = image.get('id')
                            if not img_filename:
                                img_filename = f"{base_name}_page{page_idx+1}_img{img_idx+1}.png"
                            if not Path(img_filename).suffix:
                                img_filename += ".png"
                            img_path = output_dir / img_filename
                            with open(img_path, 'wb') as f:
                                f.write(img_data)
                            saved_images.append(img_path)
                            img_metadata = {
                                'source_page': page_idx + 1,
                                'image_index': img_idx + 1,
                                'bbox': {
                                    'top_left_x': image.get('top_left_x'),
                                    'top_left_y': image.get('top_left_y'),
                                    'bottom_right_x': image.get('bottom_right_x'),
                                    'bottom_right_y': image.get('bottom_right_y'),
                                },
                                'description': image.get('image_annotation', ''),
                                'extracted_at': datetime.now().isoformat(),
                                'file_size_bytes': len(img_data)
                            }
                            metadata_path = output_dir / f"{img_filename}.metadata.json"
                            write_text(metadata_path, json.dumps(img_metadata, indent=2, default=str))
                        except Exception as e:
                            logline(f"  -> Warning: Failed to save image {img_idx+1} from page {page_idx+1}: {e}")
    except Exception as e:
        logline(f"  -> Warning: Error saving extracted images: {e}")
    if saved_images:
        logline(f"  -> Saved {len(saved_images)} extracted images to output_images/{output_dir.name}/")
    return saved_images
