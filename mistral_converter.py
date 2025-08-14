import base64
import json
import time
import traceback
from pathlib import Path
from collections import Counter
import re
from datetime import datetime

from config import (
    MISTRAL_API_KEY, MISTRAL_MODEL, MISTRAL_INCLUDE_IMAGES, SAVE_MISTRAL_JSON,
    LARGE_FILE_THRESHOLD_MB, MAX_RETRIES, MISTRAL_TIMEOUT, CACHE_DIR, LOG_DIR, OUT_IMG, OUT_MD
)
from utils import logline, write_text, get_mime_type
import os
from typing import Any
from io import BytesIO

# Optional: render PDF pages to images for per-page OCR fallback
try:
    from pdf2image import convert_from_path  # type: ignore
except Exception:
    convert_from_path = None

mistral_client: Any = None
MistralException: Any = Exception

def _ensure_mistral_client() -> bool:
    """Ensure the global Mistral client is initialized; log precise import/init errors."""
    global mistral_client, MistralException
    if mistral_client is not None:
        return True
    try:
        from mistralai import Mistral  # type: ignore
    except Exception as e:
        logline(f"  -> ERROR: Could not import 'mistralai.Mistral': {e}")
        return False
    api_key = (MISTRAL_API_KEY or os.environ.get("MISTRAL_API_KEY", "")).strip()
    if not api_key:
        logline("  -> ERROR: Mistral client not initialized. Check MISTRAL_API_KEY.")
        return False
    try:
        # v1 SDK constructor supports api_key; per-call retries can be configured via request args if needed
        mistral_client = Mistral(api_key=api_key)
        return True
    except Exception as e:
        logline(f"  -> ERROR: Failed to initialize Mistral client: {e}")
        return False

def mistral_ocr_file_enhanced(file_path: Path, base_name: str, use_cache: bool = True) -> dict | None:
    """
    Enhanced Mistral OCR using the official Python SDK.
    - Handles large files by uploading them first.
    - Uses caching and SDK's built-in retry logic.
    """
    if not _ensure_mistral_client():
        return None

    # Check cache first
    cache_file = CACHE_DIR / f"{base_name}_{MISTRAL_MODEL}.json"
    if use_cache and cache_file.exists():
        try:
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age < 86400:  # 24 hours
                logline(f"  -> Using cached OCR result (age: {cache_age/3600:.1f} hours)")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logline(f"  -> WARN: Could not read cache file: {e}")

    logline(f"  -> Processing with Mistral OCR (Model: {MISTRAL_MODEL})")
    logline(f"     Features: Images={'Yes' if MISTRAL_INCLUDE_IMAGES else 'No'}, Cache={'Yes' if use_cache else 'No'}")

    try:
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        suffix = file_path.suffix.lower()
        is_image = suffix in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
        doc_type = "image_url" if is_image else "document_url"
        doc_url = ""

        # Prefer FileChunk for PDFs and large images; otherwise inline image via data URL
        uploaded_file = None
        if (suffix == ".pdf") or (file_size_mb > LARGE_FILE_THRESHOLD_MB):
            logline(f"  -> Uploading file for OCR ({file_size_mb:.1f} MB)...")
            with open(file_path, "rb") as f:
                uploaded_file = mistral_client.files.upload(
                    file={
                        "file_name": file_path.name,
                        "content": f,
                    },
                    purpose="ocr",
                )
            logline(f"  -> File uploaded (ID: {uploaded_file.id}). Processing OCR...")
        else:
            # For smaller images, send as a base64 data URL
            with open(file_path, "rb") as f:
                b64_content = base64.b64encode(f.read()).decode("utf-8")
            mime_type = get_mime_type(file_path)
            doc_url = f"data:{mime_type};base64,{b64_content}"

        # Call the OCR endpoint
        if uploaded_file is not None:
            payload = {
                "type": "file",
                "file_id": uploaded_file.id,
            }
        else:
            # ImageURLChunk for inlined small images
            payload = {
                "type": "image_url",
                "image_url": {"url": doc_url},
            }

        ocr_response = mistral_client.ocr.process(
            model=MISTRAL_MODEL,
            document=payload,
            include_image_base64=MISTRAL_INCLUDE_IMAGES,
        )

        response_json = ocr_response.model_dump()
        # Keep source information to enable targeted reprocessing
        response_json['_source'] = {
            'doc_type': 'file' if (uploaded_file is not None) else doc_type,
            'doc_url': doc_url if uploaded_file is None else None,
            'file_id': getattr(uploaded_file, 'id', None),
            'file_path': str(file_path),
        }

        if not response_json.get('pages'):
            logline("  -> Warning: Empty response from Mistral OCR")
            return None

        # Cache successful response
        if use_cache:
            try:
                write_text(cache_file, json.dumps(response_json, indent=2))
                logline(f"  -> Cached OCR result")
            except Exception as e:
                logline(f"  -> WARN: Failed to write to cache: {e}")

        # Save raw JSON for debugging if configured
        if SAVE_MISTRAL_JSON:
            from datetime import datetime
            try:
                json_path = LOG_DIR / f"{base_name}_mistral_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                write_text(json_path, json.dumps(response_json, indent=2))
                logline(f"  -> Saved debug JSON to logs/")
            except Exception as e:
                logline(f"  -> WARN: Failed to save debug JSON: {e}")

        return response_json

    except MistralException as e:
        logline(f"  -> FATAL: Mistral API Error: {e}")
        if "401" in str(e):
            logline("     -> Please check your MISTRAL_API_KEY.")
        elif "429" in str(e):
            logline("     -> Rate limit exceeded. The SDK's retry logic was exhausted.")
        return None
    except IOError as e:
        logline(f"  -> FATAL: File I/O error for {file_path.name}: {e}")
        return None
    except Exception as e:
        logline(f"  -> FATAL: An unexpected error occurred in Mistral OCR for {file_path.name}: {e}")
        traceback.print_exc()
        return None

def process_mistral_response(resp: dict, base_name: str) -> Path | None:
    """
    Processes the Mistral response, saves images, and generates markdown with fallbacks.
    """
    try:
        pages = resp.get("pages", [])
        if not pages:
            logline("  -> Mistral OCR returned no pages.")
            return None

        # Setup image directory
        img_dir = OUT_IMG / f"{base_name}_ocr"
        img_dir.mkdir(parents=True, exist_ok=True)
        # Relative path for embedding in MD (assuming MD is in output_md)
        # Using forward slashes for compatibility in Markdown
        img_dir_rel = f"../output_images/{img_dir.name}"

        parts = [f"# OCR (Mistral): {base_name}"]
        pages_sorted = sorted(pages, key=lambda p: p.get("index", 0))

        for p in pages_sorted:
            idx = p.get("index", 0) + 1 # 1-based index
            parts.append(f"\n\n---\n\n## Page {idx}\n")

            # 1. Extract and Save Images
            saved_imgs = []
            if MISTRAL_INCLUDE_IMAGES:
                for i, img in enumerate(p.get("images", []) or [], start=1):
                    raw = img.get("image_base64")
                    if not raw: continue
                    # Use provided ID or generate filename
                    fname = img.get("id") or f"page_{idx:03d}_{i:02d}.jpg"
                    try:
                        (img_dir / fname).write_bytes(base64.b64decode(raw))
                        saved_imgs.append(fname)
                    except Exception:
                        continue

            # 2. Determine Content (Markdown > Text > Image Fallback)
            md = (p.get("markdown") or "").strip()
            txt = (p.get("text") or "").strip()

            is_md_poor = False
            # Heuristic: High repetition (detects the failure mode seen in bad outputs)
            if md:
                # Clean lines (ignore empty and markdown separators)
                lines = [line for line in md.split('\n') if line.strip() and not line.strip().startswith("---")]
                if len(lines) > 5:
                    # Check frequency of the most common line
                    counts = Counter(lines)
                    if counts:
                        most_common_line, count = counts.most_common(1)[0]
                        # If the most common line makes up > 50% of the lines, it's likely repetitive noise
                        if count > len(lines) * 0.5:
                            is_md_poor = True

            if md and not is_md_poor:
                # Use Markdown. Rewrite image links to point to our saved images.
                # This regex handles links generated by Mistral and rewrites them to the relative path.
                content = re.sub(r"\]\(([^)]+\.(jpe?g|png|tiff?))\)",
                                 lambda m: f"]({img_dir_rel}/{Path(m.group(1)).name})", md, flags=re.IGNORECASE)
                parts.append(content)
            elif txt:
                # Fallback to raw text if markdown is poor/missing
                logline(f"  -> Page {idx}: Markdown quality poor. Falling back to raw text.")
                parts.append(f"*(OCR Text Fallback)*\n\n```text\n{txt}\n```")
            elif saved_imgs:
                # Fallback to the page image if no text or markdown extracted
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
    """
    Extract structured content from Mistral OCR response for enhanced processing.
    
    Returns:
        dict with structured data including text blocks, tables, images, metadata
    """
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
            
            # Analyze document structure
            if any(line.startswith('#') for line in page_text.split('\n')):
                structured['metadata']['document_structure']['has_headers'] = True
            if '|' in page_text and '-' in page_text:
                structured['metadata']['document_structure']['has_tables'] = True
            if any(line.strip().startswith(('-', '*', '1.')) for line in page_text.split('\n')):
                structured['metadata']['document_structure']['has_lists'] = True
            
            # Extract text blocks
            text_block = {
                'page': page_idx + 1,
                'content': page_text,
                'length': len(page_text),
                'line_count': len(page_text.split('\n'))
            }
            structured['text_blocks'].append(text_block)
            
            # Extract image information if available
            if page.get('images'):
                structured['metadata']['document_structure']['has_images'] = True
                for img_idx, image in enumerate(page.get('images', [])):
                    image_info = {
                        'page': page_idx + 1,
                        'image_index': img_idx,
                        # Build bbox-like dict from coordinates if present
                        'bbox': {
                            'top_left_x': image.get('top_left_x'),
                            'top_left_y': image.get('top_left_y'),
                            'bottom_right_x': image.get('bottom_right_x'),
                            'bottom_right_y': image.get('bottom_right_y'),
                        },
                        'has_base64': bool(image.get('image_base64')),
                        'description': image.get('image_annotation', ''),
                        'filename': image.get('id', f'page_{page_idx+1}_image_{img_idx+1}')
                    }
                    structured['images'].append(image_info)
        
        # Detect potential table content
        all_text = '\n'.join(block['content'] for block in structured['text_blocks'])
        table_indicators = all_text.count('|') + all_text.count('---')
        if table_indicators > 10:  # Threshold for table detection
            structured['metadata']['document_structure']['has_tables'] = True
            
    except Exception as e:
        logline(f"Warning: Error extracting structured content: {e}")
    
    return structured

def create_enhanced_markdown_output(response_json: dict, base_name: str) -> str:
    """
    Create enhanced markdown output with better structure and metadata.
    """
    structured = extract_structured_content(response_json)
    
    # Header with metadata
    output = f"# OCR Results: {base_name}\n\n"
    output += f"**Processing Model**: {structured['metadata']['processing_model']}\n"
    output += f"**Total Pages**: {structured['metadata']['total_pages']}\n"
    output += f"**Text Length**: {structured['metadata']['total_text_length']:,} characters\n"
    output += f"**Processing Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    # Document structure analysis
    structure = structured['metadata']['document_structure']
    output += "**Document Analysis**:\n"
    output += f"- Headers detected: {'✓' if structure['has_headers'] else '✗'}\n"
    output += f"- Tables detected: {'✓' if structure['has_tables'] else '✗'}\n"
    output += f"- Lists detected: {'✓' if structure['has_lists'] else '✗'}\n"
    output += f"- Images detected: {'✓' if structure['has_images'] else '✗'}\n\n"
    
    if structured['images']:
        output += f"**Images Found**: {len(structured['images'])} images across {structured['metadata']['total_pages']} pages\n\n"
    
    output += "---\n\n"
    
    # Main content
    if structured['metadata']['total_pages'] > 1:
        output += "## 📄 Multi-Page Content\n\n"
        for block in structured['text_blocks']:
            if block['content'].strip():
                output += f"### Page {block['page']}\n\n"
                output += block['content'] + "\n\n"
    else:
        output += "## 📄 Content\n\n"
        if structured['text_blocks']:
            output += structured['text_blocks'][0]['content']
    
    # Image information
    if structured['images']:
        output += "\n\n---\n\n"
        output += "## 🖼️ Detected Images\n\n"
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
    """
    Enhanced processing of Mistral OCR response with structured output.
    """
    try:
        # Optionally improve poor pages for PDFs by re-OCRing a rendered image of the page
        if original_file and original_file.suffix.lower() == ".pdf":
            pages = response_json.get('pages') or []
            improved_any = False
            for i, p in enumerate(pages):
                md = (p.get('markdown') or '').strip()
                if _is_page_md_poor(md):
                    new_md = None
                    # Prefer image-based per-page OCR if pdf2image is available
                    if convert_from_path is not None:
                        new_md = _reprocess_pdf_page_via_image(original_file, i)
                    # Fallback: reprocess specific page via document_url if present
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

        # Create enhanced markdown output (after any improvements)
        enhanced_md = create_enhanced_markdown_output(response_json, base_name)
        
        # Main OCR markdown file
        ocr_md_path = OUT_MD / f"{base_name}_mistral_ocr.md"
        write_text(ocr_md_path, enhanced_md)
        
        # Extract and save images if available and configured
        if MISTRAL_INCLUDE_IMAGES:
            save_extracted_images(response_json, base_name)
        
        # Create structured data export
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
    """
    Render a single PDF page to an image and run image-based OCR on it. Returns improved markdown if available.
    """
    try:
        from config import POPPLER_PATH, MISTRAL_MODEL, MISTRAL_INCLUDE_IMAGES
        if convert_from_path is None:
            return None
        # Render only the requested page (1-based for pdf2image)
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
    """Re-run OCR for a specific page using the original document_url source."""
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
        # Single requested page should be at index 0
        return (pages[0].get('markdown') or '').strip()
    except Exception:
        return None

def _reprocess_pdf_page_via_file_id(file_id: str, page_index: int) -> str | None:
    """Re-run OCR for a specific page using previously uploaded file_id."""
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

def save_extracted_images(response_json: dict, base_name: str) -> list[Path]:
    """
    Save extracted images from OCR response with enhanced metadata.
    """
    saved_images = []
    
    try:
        for page_idx, page in enumerate(response_json.get('pages', [])):
            if page.get('images'):
                for img_idx, image in enumerate(page.get('images', [])):
                    # SDK uses 'image_base64' for extracted image content
                    if image.get('image_base64'):
                        try:
                            img_data = base64.b64decode(image['image_base64'])
                            img_filename = f"{base_name}_page{page_idx+1}_img{img_idx+1}.png"
                            img_path = OUT_IMG / img_filename
                            
                            with open(img_path, 'wb') as f:
                                f.write(img_data)
                            
                            saved_images.append(img_path)
                            
                            # Create image metadata file
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
                            
                            metadata_path = OUT_IMG / f"{img_filename}_metadata.json"
                            write_text(metadata_path, json.dumps(img_metadata, indent=2))
                            
                        except Exception as e:
                            logline(f"  -> Warning: Failed to save image {img_idx+1} from page {page_idx+1}: {e}")
                            
    except Exception as e:
        logline(f"  -> Warning: Error saving extracted images: {e}")
    
    if saved_images:
        logline(f"  -> Saved {len(saved_images)} extracted images")
    
    return saved_images
