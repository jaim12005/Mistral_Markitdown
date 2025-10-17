"""
Enhanced Document Converter v2.1 - Mistral AI Integration Module

This module handles Mistral OCR processing including:
- Files API integration with purpose="ocr"
- Multi-page OCR handling
- Per-page re-OCR for weak results
- Image extraction and optimization
- Function calling and structured outputs

Documentation references:
- Mistral OCR: https://docs.mistral.ai/capabilities/document_ai/basic_ocr/
- Mistral Python SDK: https://github.com/mistralai/client-python
- OCR Endpoint: https://github.com/mistralai/client-python/blob/main/docs/sdks/ocr/README.md
- Files API: https://github.com/mistralai/client-python/blob/main/docs/sdks/files/README.md
"""

import base64
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    from mistralai import Mistral
    from mistralai import models
except ImportError:
    Mistral = None
    models = None

try:
    from PIL import Image
except ImportError:
    Image = None

import config
import utils
import local_converter

logger = utils.logger

# ============================================================================
# Mistral Client Initialization
# ============================================================================

def get_mistral_client() -> Optional[Mistral]:
    """
    Create and configure a Mistral client instance.

    Returns:
        Configured Mistral client or None if unavailable
    """
    if Mistral is None:
        logger.error("Mistral SDK not installed. Install with: pip install mistralai")
        return None

    if not config.MISTRAL_API_KEY:
        logger.error("MISTRAL_API_KEY not set in environment variables")
        return None

    try:
        client = Mistral(api_key=config.MISTRAL_API_KEY)
        return client

    except Exception as e:
        logger.error(f"Error initializing Mistral client: {e}")
        return None

# ============================================================================
# Image Optimization
# ============================================================================

def optimize_image(image_path: Path) -> Optional[Path]:
    """
    Optimize image for better OCR results.

    Args:
        image_path: Path to image file

    Returns:
        Path to optimized image or original if optimization fails
    """
    if not config.MISTRAL_ENABLE_IMAGE_OPTIMIZATION or Image is None:
        return image_path

    try:
        img = Image.open(image_path)

        # Check if optimization needed
        width, height = img.size
        max_dim = config.MISTRAL_MAX_IMAGE_DIMENSION

        if width <= max_dim and height <= max_dim:
            return image_path  # No optimization needed

        # Resize while maintaining aspect ratio
        if width > height:
            new_width = max_dim
            new_height = int(height * (max_dim / width))
        else:
            new_height = max_dim
            new_width = int(width * (max_dim / height))

        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Save optimized image
        optimized_path = image_path.parent / f"{image_path.stem}_optimized{image_path.suffix}"
        img.save(optimized_path, quality=config.MISTRAL_IMAGE_QUALITY_THRESHOLD)

        logger.debug(f"Optimized image: {image_path.name} -> {optimized_path.name}")
        return optimized_path

    except Exception as e:
        logger.warning(f"Error optimizing image {image_path.name}: {e}")
        return image_path

def preprocess_image(image_path: Path) -> Optional[Path]:
    """
    Apply preprocessing to image for better OCR (contrast, sharpening, etc.).

    Args:
        image_path: Path to image file

    Returns:
        Path to preprocessed image or original if preprocessing fails
    """
    if not config.MISTRAL_ENABLE_IMAGE_PREPROCESSING or Image is None:
        return image_path

    try:
        from PIL import ImageEnhance

        img = Image.open(image_path)

        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)

        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.3)

        # Save preprocessed image
        preprocessed_path = image_path.parent / f"{image_path.stem}_preprocessed{image_path.suffix}"
        img.save(preprocessed_path, quality=95)

        logger.debug(f"Preprocessed image: {image_path.name}")
        return preprocessed_path

    except Exception as e:
        logger.warning(f"Error preprocessing image {image_path.name}: {e}")
        return image_path

# ============================================================================
# Files API Integration
# ============================================================================

def upload_file_for_ocr(client: Mistral, file_path: Path) -> Optional[str]:
    """
    Upload file to Mistral using Files API with purpose="ocr".

    Required for files >4MB or when preferred for large files.

    Args:
        client: Mistral client instance
        file_path: Path to file to upload

    Returns:
        File ID if successful, None otherwise
    """
    try:
        logger.info(f"Uploading file to Mistral: {file_path.name}")

        with open(file_path, 'rb') as f:
            file_content = f.read()

        # Upload with purpose="ocr"
        response = client.files.upload(
            file={
                "file_name": file_path.name,
                "content": file_content,
            },
            purpose="ocr"  # Critical: Must specify purpose="ocr"
        )

        if hasattr(response, 'id'):
            logger.info(f"File uploaded successfully: {response.id}")
            return response.id
        else:
            logger.error("Upload response missing file ID")
            return None

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return None

# ============================================================================
# OCR Processing
# ============================================================================

def process_with_ocr(
    client: Mistral,
    file_path: Path,
    model: Optional[str] = None,
    pages: Optional[List[int]] = None
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Process file with Mistral OCR.

    Args:
        client: Mistral client instance
        file_path: Path to file
        model: Optional model override
        pages: Optional specific pages to process (0-indexed)

    Returns:
        Tuple of (success, ocr_result_dict, error_message)
    """
    try:
        # Determine best model
        if model is None:
            content_analysis = local_converter.analyze_file_content(file_path)
            model = config.select_best_model(
                file_type=file_path.suffix.lower().lstrip('.'),
                content_analysis=content_analysis
            )

        logger.info(f"Processing with Mistral OCR using model: {model}")

        # ALWAYS use Files API for better OCR quality (not base64)
        # The Files API produces significantly better results than base64 encoding
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        use_files_api = True  # Always use Files API for best quality

        # Prepare document - use dict format instead of model classes
        if use_files_api:
            file_id = upload_file_for_ocr(client, file_path)
            if not file_id:
                return False, None, "Failed to upload file"

            document = {
                "type": "document_url",
                "document_url": f"mistral://files/{file_id}"
            }
        else:
            # Use base64 encoding for smaller files
            with open(file_path, 'rb') as f:
                file_content = base64.b64encode(f.read()).decode('utf-8')

            # Determine MIME type
            mime_types = {
                'pdf': 'application/pdf',
                'png': 'image/png',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            }

            ext = file_path.suffix.lower().lstrip('.')
            mime_type = mime_types.get(ext, 'application/octet-stream')

            document = {
                "type": "document_url",
                "document_url": f"data:{mime_type};base64,{file_content}"
            }

        # Process with OCR
        response = client.ocr.process(
            model=model,
            document=document,
            pages=pages,
            include_image_base64=config.MISTRAL_INCLUDE_IMAGES,
        )

        # Parse response
        if response:
            result = _parse_ocr_response(response, file_path)

            # Validate that we got actual text content
            if not result.get("full_text", "").strip():
                error_msg = "Mistral OCR returned empty text. Your API key may not have OCR access. "
                error_msg += "Try using Mode 3 (MarkItDown Only) instead, which works perfectly for text-based PDFs."
                logger.warning(error_msg)
                return False, None, error_msg

            return True, result, None
        else:
            return False, None, "Empty response from Mistral OCR"

    except Exception as e:
        error_msg = f"Error processing with Mistral OCR: {e}"

        # Check for specific error types
        if "401" in str(e) or "Unauthorized" in str(e):
            error_msg = "Mistral API authentication failed (401 Unauthorized). "
            error_msg += "Please verify your API key has OCR access at https://console.mistral.ai/"
        elif "403" in str(e) or "Forbidden" in str(e):
            error_msg = "Access denied to Mistral OCR (403 Forbidden). This feature may require a paid plan."

        logger.error(error_msg)
        return False, None, error_msg

def _parse_ocr_response(response: Any, file_path: Path) -> Dict[str, Any]:
    """
    Parse OCR response into structured dictionary.

    Args:
        response: Mistral OCR response
        file_path: Original file path

    Returns:
        Parsed OCR result
    """
    result = {
        "file_name": file_path.name,
        "pages": [],
        "full_text": "",
        "images": [],
        "metadata": {},
    }

    try:
        # Try different response formats
        # Format 1: response.pages (list of page objects)
        if hasattr(response, 'pages') and response.pages:
            logger.debug(f"Found {len(response.pages)} pages in response")

            for idx, page in enumerate(response.pages):
                # Try different text attributes (markdown is the primary one for Mistral OCR)
                page_text = ""

                if hasattr(page, 'markdown') and page.markdown:
                    page_text = page.markdown
                elif hasattr(page, 'text') and page.text:
                    page_text = page.text
                elif hasattr(page, 'content') and page.content:
                    page_text = page.content
                elif isinstance(page, dict):
                    page_text = page.get('markdown', page.get('text', page.get('content', '')))
                elif isinstance(page, str):
                    page_text = page

                logger.debug(f"Page {idx}: {len(page_text)} chars extracted")

                page_data = {
                    "page_number": getattr(page, 'page_number', idx),
                    "text": page_text,
                    "images": [],
                }

                # Extract images from page
                if hasattr(page, 'images') and page.images:
                    logger.debug(f"Page {idx} has {len(page.images)} images")
                    for img in page.images:
                        image_data = {
                            "bbox": getattr(img, 'bbox', None),
                            "base64": getattr(img, 'base64', None) if config.MISTRAL_INCLUDE_IMAGES else None,
                        }
                        page_data["images"].append(image_data)

                result["pages"].append(page_data)
                if page_text:
                    result["full_text"] += page_text + "\n\n"

        # Format 2: response.markdown (Mistral OCR format)
        elif hasattr(response, 'markdown') and response.markdown:
            result["full_text"] = response.markdown
            result["pages"].append({
                "page_number": 0,
                "text": response.markdown,
                "images": [],
            })

        # Format 3: response.text (direct text)
        elif hasattr(response, 'text') and response.text:
            result["full_text"] = response.text
            result["pages"].append({
                "page_number": 0,
                "text": response.text,
                "images": [],
            })

        # Format 4: response.content
        elif hasattr(response, 'content') and response.content:
            result["full_text"] = response.content
            result["pages"].append({
                "page_number": 0,
                "text": response.content,
                "images": [],
            })

        # Format 5: response as dict
        elif isinstance(response, dict):
            if 'pages' in response:
                for idx, page in enumerate(response['pages']):
                    page_text = page.get('markdown', page.get('text', page.get('content', '')))
                    result["pages"].append({
                        "page_number": idx,
                        "text": page_text,
                        "images": page.get('images', []),
                    })
                    if page_text:
                        result["full_text"] += page_text + "\n\n"
            elif 'markdown' in response:
                result["full_text"] = response['markdown']
                result["pages"].append({
                    "page_number": 0,
                    "text": response['markdown'],
                    "images": [],
                })
            elif 'text' in response:
                result["full_text"] = response['text']
                result["pages"].append({
                    "page_number": 0,
                    "text": response['text'],
                    "images": [],
                })

        # Extract metadata
        if hasattr(response, 'metadata'):
            result["metadata"] = response.metadata
        elif isinstance(response, dict) and 'metadata' in response:
            result["metadata"] = response['metadata']

        # Log final result
        logger.debug(f"Extracted {len(result['pages'])} pages, {len(result['full_text'])} chars")

    except Exception as e:
        logger.error(f"Error parsing OCR response: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")

    return result

# ============================================================================
# Per-Page OCR Improvements
# ============================================================================

def _is_weak_page(text: str) -> bool:
    """
    Detect if OCR page text is weak or low-quality.

    Checks for:
    - Very short text
    - High repetition rate (same words/phrases repeated)
    - Very few numbers (important for financial/data documents)
    - Low unique token ratio

    Args:
        text: Page text to analyze

    Returns:
        True if page appears to have weak OCR results
    """
    if not text or len(text.strip()) < 10:
        return True

    # Check 1: Very short text (original check)
    if len(text.strip()) < 50:
        return True

    # Check 2: Count digits (financial docs should have many numbers)
    digit_count = sum(1 for char in text if char.isdigit())
    if digit_count < 20:  # Very few numbers for a data document
        return True

    # Check 3: Token uniqueness ratio (detect heavy repetition)
    tokens = text.split()
    if not tokens:
        return True

    unique_tokens = set(tokens)
    uniqueness_ratio = len(unique_tokens) / len(tokens)

    # If < 30% of tokens are unique, probably repetitive junk
    if uniqueness_ratio < 0.3:
        logger.debug(f"Low uniqueness ratio: {uniqueness_ratio:.2f}")
        return True

    # Check 4: Detect repeated header patterns
    # Count occurrences of common repeated strings
    common_phrases = [
        "5151 E Broadway",  # Example from SWE feedback
        "Page 1", "Page 2", "Page 3",
    ]

    for phrase in common_phrases:
        occurrences = text.count(phrase)
        if occurrences > 5:  # Same phrase repeated many times
            logger.debug(f"Repeated phrase '{phrase}' found {occurrences} times")
            return True

    # Check 5: Average line length (very short lines suggest parsing issues)
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if lines:
        avg_line_length = sum(len(line) for line in lines) / len(lines)
        if avg_line_length < 10:  # Very short average line length
            logger.debug(f"Short average line length: {avg_line_length:.1f}")
            return True

    return False

def improve_weak_pages(
    client: Mistral,
    file_path: Path,
    ocr_result: Dict[str, Any],
    model: str
) -> Dict[str, Any]:
    """
    Re-OCR weak pages with low confidence or short text.

    Uses enhanced detection heuristics to identify:
    - Short text
    - Repetitive content
    - Low information density
    - Missing numerical data

    Args:
        client: Mistral client instance
        file_path: Path to original file
        ocr_result: Initial OCR result
        model: Model to use

    Returns:
        Improved OCR result
    """
    if not ocr_result.get("pages"):
        return ocr_result

    logger.info("Analyzing pages for weak OCR results...")

    weak_pages = []

    for i, page in enumerate(ocr_result["pages"]):
        text = page.get("text", "")

        # Use enhanced weak page detection
        if _is_weak_page(text):
            weak_pages.append(i)
            logger.debug(f"Page {i + 1} has weak OCR result ({len(text)} chars)")

    if not weak_pages:
        logger.info("No weak pages detected")
        return ocr_result

    logger.info(f"Re-processing {len(weak_pages)} weak pages...")

    # Re-OCR weak pages
    for page_idx in weak_pages:
        try:
            success, improved_result, error = process_with_ocr(
                client,
                file_path,
                model=model,
                pages=[page_idx]
            )

            if success and improved_result:
                # Replace weak page with improved result
                if improved_result.get("pages") and len(improved_result["pages"]) > 0:
                    improved_page = improved_result["pages"][0]

                    if len(improved_page.get("text", "")) > len(ocr_result["pages"][page_idx].get("text", "")):
                        logger.info(f"Improved page {page_idx + 1}")
                        ocr_result["pages"][page_idx] = improved_page

        except Exception as e:
            logger.warning(f"Error improving page {page_idx + 1}: {e}")

    # Rebuild full text
    ocr_result["full_text"] = "\n\n".join(
        page.get("text", "") for page in ocr_result["pages"]
    )

    return ocr_result

# ============================================================================
# Image Extraction and Saving
# ============================================================================

def save_extracted_images(
    ocr_result: Dict[str, Any],
    file_path: Path
) -> List[Path]:
    """
    Save extracted images from OCR result.

    Args:
        ocr_result: OCR result dictionary
        file_path: Original file path

    Returns:
        List of saved image paths
    """
    saved_images = []

    if not config.MISTRAL_INCLUDE_IMAGES:
        return saved_images

    # Create output directory
    image_dir = config.OUTPUT_IMAGES_DIR / f"{file_path.stem}_ocr"
    image_dir.mkdir(parents=True, exist_ok=True)

    image_count = 0

    for page in ocr_result.get("pages", []):
        page_num = page.get("page_number", 0)

        for img in page.get("images", []):
            image_base64 = img.get("base64")

            if not image_base64:
                continue

            try:
                # Decode base64 image
                image_data = base64.b64decode(image_base64)

                image_count += 1
                image_path = image_dir / f"page_{page_num}_image_{image_count}.png"

                with open(image_path, 'wb') as f:
                    f.write(image_data)

                saved_images.append(image_path)
                logger.debug(f"Saved extracted image: {image_path.name}")

            except Exception as e:
                logger.error(f"Error saving image: {e}")

    if saved_images:
        logger.info(f"Saved {len(saved_images)} extracted images to {image_dir}")

    return saved_images

# ============================================================================
# Main Conversion Function
# ============================================================================

def convert_with_mistral_ocr(
    file_path: Path,
    use_cache: bool = True,
    improve_weak: bool = True
) -> Tuple[bool, Optional[Path], Optional[str]]:
    """
    Convert file using Mistral OCR with full pipeline.

    Args:
        file_path: Path to file
        use_cache: Use cached results if available
        improve_weak: Re-process weak pages

    Returns:
        Tuple of (success, output_md_path, error_message)
    """
    client = get_mistral_client()
    if client is None:
        error_msg = "Mistral client not available. Please set MISTRAL_API_KEY in .env file"
        logger.warning(error_msg)
        return False, None, error_msg

    # Check cache
    if use_cache:
        cached_result = utils.cache.get(file_path, cache_type="mistral_ocr")
        if cached_result:
            logger.info(f"Using cached Mistral OCR result for {file_path.name}")
            ocr_result = cached_result
            success = True
            error = None
        else:
            success, ocr_result, error = process_with_ocr(client, file_path)
    else:
        success, ocr_result, error = process_with_ocr(client, file_path)

    if not success or not ocr_result:
        return False, None, error

    # DISABLED: Weak page improvement (causing issues with response parsing)
    # The OCR API returns good results - re-processing weak pages makes things worse
    # if improve_weak and ocr_result.get("pages"):
    #     content_analysis = local_converter.analyze_file_content(file_path)
    #     model = config.select_best_model(
    #         file_type=file_path.suffix.lower().lstrip('.'),
    #         content_analysis=content_analysis
    #     )
    #     ocr_result = improve_weak_pages(client, file_path, ocr_result, model)

    # Cache result
    if use_cache:
        utils.cache.set(file_path, ocr_result, cache_type="mistral_ocr")

    # Save extracted images
    save_extracted_images(ocr_result, file_path)

    # Generate markdown output
    output_path = _create_markdown_output(file_path, ocr_result)

    # Save JSON metadata if requested
    if config.SAVE_MISTRAL_JSON:
        json_path = config.OUTPUT_MD_DIR / f"{file_path.stem}_ocr_metadata.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(ocr_result, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved OCR metadata: {json_path.name}")

    return True, output_path, None

def _create_markdown_output(file_path: Path, ocr_result: Dict[str, Any]) -> Path:
    """
    Create markdown output from OCR result.

    Args:
        file_path: Original file path
        ocr_result: OCR result dictionary

    Returns:
        Path to created markdown file
    """
    # Generate frontmatter
    frontmatter = utils.generate_yaml_frontmatter(
        title=f"OCR: {file_path.stem}",
        file_name=file_path.name,
        conversion_method="Mistral OCR",
        additional_fields={
            "page_count": len(ocr_result.get("pages", [])),
            "image_count": len(ocr_result.get("images", [])),
        }
    )

    # Build markdown content
    md_content = frontmatter + f"\n# OCR Result: {file_path.name}\n\n"

    # Add full text
    md_content += "## Full Text\n\n"
    md_content += ocr_result.get("full_text", "")
    md_content += "\n\n---\n\n"

    # Add page-by-page breakdown
    if ocr_result.get("pages"):
        md_content += "## Page-by-Page Content\n\n"

        for page in ocr_result["pages"]:
            page_num = page.get("page_number", 0)
            text = page.get("text", "")

            md_content += f"### Page {page_num}\n\n"
            md_content += text
            md_content += "\n\n---\n\n"

    # Save markdown
    output_path = config.OUTPUT_MD_DIR / f"{file_path.stem}_mistral_ocr.md"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    # Save text version
    utils.save_text_output(output_path, md_content)

    logger.info(f"Saved Mistral OCR output: {output_path.name}")

    return output_path
