"""
Enhanced Document Converter v2.1.1 - Mistral AI Integration Module

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
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable

try:
    from mistralai import Mistral
    from mistralai import models
    from mistralai.utils import retries
except ImportError:
    Mistral = None
    models = None
    retries = None

try:
    from PIL import Image
except ImportError:
    Image = None

import config
import utils
import local_converter
import schemas  # New: JSON schemas for structured extraction

logger = utils.logger

# ============================================================================
# OCR Quality Assessment Constants
# ============================================================================

# Minimum text length for a valid OCR page result
OCR_MIN_TEXT_LENGTH = 50

# Minimum digit count for financial/data documents (low count suggests poor OCR)
OCR_MIN_DIGIT_COUNT = 20

# Minimum token uniqueness ratio (detects repetitive OCR artifacts)
OCR_MIN_UNIQUENESS_RATIO = 0.3

# Maximum allowed repetitions of the same phrase (detects header/footer artifacts)
OCR_MAX_PHRASE_REPETITIONS = 5

# Minimum average line length (very short lines suggest parsing issues)
OCR_MIN_AVG_LINE_LENGTH = 10

# Quality score thresholds (0-100 scale)
OCR_QUALITY_THRESHOLD_EXCELLENT = 80
OCR_QUALITY_THRESHOLD_GOOD = 60
OCR_QUALITY_THRESHOLD_ACCEPTABLE = 40

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
# Retry Configuration
# ============================================================================


def get_retry_config() -> Optional[Any]:
    """
    Create RetryConfig for Mistral API calls with exponential backoff.

    Returns:
        RetryConfig instance or None if retries module unavailable
    """
    if retries is None or config.MAX_RETRIES == 0:
        return None

    try:
        backoff_strategy = retries.BackoffStrategy(
            initial_interval=config.RETRY_INITIAL_INTERVAL_MS,
            max_interval=config.RETRY_MAX_INTERVAL_MS,
            exponent=config.RETRY_EXPONENT,
            max_elapsed_time=config.RETRY_MAX_ELAPSED_TIME_MS,
        )

        retry_config = retries.RetryConfig(
            strategy="backoff",
            backoff=backoff_strategy,
            retry_connection_errors=config.RETRY_CONNECTION_ERRORS,
        )

        logger.debug(
            f"Retry config: {config.MAX_RETRIES} attempts, {config.RETRY_INITIAL_INTERVAL_MS}ms initial interval"
        )
        return retry_config

    except Exception as e:
        logger.warning(f"Error creating retry config: {e}")
        return None


# ============================================================================
# Structured Output Configuration
# ============================================================================


def get_raw_schema(schema_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Get raw schema for OCR annotation formats.

    Note: OCR API expects raw JSON schema dicts, NOT ResponseFormat objects.
    ResponseFormat is for chat completion API with structured outputs.

    Args:
        schema_dict: Schema definition from schemas.py

    Returns:
        Raw schema dict or None if structured output disabled
    """
    if not config.MISTRAL_ENABLE_STRUCTURED_OUTPUT:
        return None

    try:
        # Return just the schema portion - OCR API expects this format
        return schema_dict.get("schema")
    except Exception as e:
        logger.warning(f"Error getting raw schema: {e}")
        return None


def get_bbox_annotation_format() -> Optional[Dict[str, Any]]:
    """
    Get raw schema dict for bounding box annotation.

    Returns:
        Raw JSON schema dict for bbox extraction or None if disabled
    """
    if not config.MISTRAL_ENABLE_BBOX_ANNOTATION:
        return None

    bbox_schema = schemas.get_bbox_schema("structured")
    return get_raw_schema(bbox_schema)


def get_document_annotation_format(doc_type: str = "auto") -> Optional[Dict[str, Any]]:
    """
    Get raw schema dict for document-level annotation.

    Args:
        doc_type: Document type (invoice, financial_statement, form, generic, auto)

    Returns:
        Raw JSON schema dict for document extraction or None if disabled
    """
    if not config.MISTRAL_ENABLE_DOCUMENT_ANNOTATION:
        return None

    # Auto-detect based on config if set to auto
    if doc_type == "auto":
        doc_type = config.MISTRAL_DOCUMENT_SCHEMA_TYPE
        if doc_type == "auto":
            doc_type = "generic"  # Default fallback

    document_schema = schemas.get_document_schema(doc_type)
    return get_raw_schema(document_schema)


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

        # Save optimized image with format-appropriate parameters
        optimized_path = (
            image_path.parent / f"{image_path.stem}_optimized{image_path.suffix}"
        )

        # Use different save parameters based on format
        if img.format == "PNG" or image_path.suffix.lower() == ".png":
            # PNG supports optimize and compress_level, not quality
            img.save(optimized_path, format="PNG", optimize=True, compress_level=6)
        elif img.format in ["JPEG", "JPG"] or image_path.suffix.lower() in [
            ".jpg",
            ".jpeg",
        ]:
            # JPEG supports quality parameter
            img.save(
                optimized_path,
                format="JPEG",
                quality=config.MISTRAL_IMAGE_QUALITY_THRESHOLD,
                optimize=True,
            )
        else:
            # For other formats, save with optimize only
            img.save(optimized_path, optimize=True)

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
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)

        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.3)

        # Save preprocessed image
        preprocessed_path = (
            image_path.parent / f"{image_path.stem}_preprocessed{image_path.suffix}"
        )
        img.save(preprocessed_path, quality=95)

        logger.debug(f"Preprocessed image: {image_path.name}")
        return preprocessed_path

    except Exception as e:
        logger.warning(f"Error preprocessing image {image_path.name}: {e}")
        return image_path


# ============================================================================
# Files API Integration
# ============================================================================


def cleanup_uploaded_files(client: Mistral, days_old: Optional[int] = None) -> int:
    """
    Clean up old files uploaded to Mistral Files API.

    Args:
        client: Mistral client instance
        days_old: Delete files older than N days (default: from config)

    Returns:
        Number of files deleted
    """
    if days_old is None:
        days_old = config.UPLOAD_RETENTION_DAYS

    try:
        from datetime import datetime, timedelta, timezone

        # List all OCR files
        files_list = client.files.list(purpose="ocr")
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        deleted = 0

        for file in files_list:
            try:
                # Handle created_at as either string or datetime object
                if hasattr(file, 'created_at'):
                    if isinstance(file.created_at, str):
                        # Parse ISO format string
                        file_created = datetime.fromisoformat(file.created_at.replace('Z', '+00:00'))
                    elif hasattr(file.created_at, 'replace'):
                        # Already a datetime object
                        file_created = file.created_at
                        # Ensure timezone-aware
                        if file_created.tzinfo is None:
                            file_created = file_created.replace(tzinfo=timezone.utc)
                    else:
                        logger.debug(f"Unexpected created_at type for file {file.id}: {type(file.created_at)}")
                        continue

                    if file_created < cutoff_date:
                        client.files.delete(file_id=file.id)
                        deleted += 1
                        logger.debug(f"Deleted old file: {file.id} (created {file_created})")
            except Exception as e:
                logger.debug(f"Error processing file {file.id}: {e}")
                continue

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old uploaded files (older than {days_old} days)")

        return deleted

    except Exception as e:
        logger.warning(f"Error cleaning up uploaded files: {e}")
        return 0


def upload_file_for_ocr(client: Mistral, file_path: Path) -> Optional[str]:
    """
    Upload file to Mistral using Files API with purpose="ocr" and get signed URL.

    For PDFs, this uploads directly. For images, preprocessing is applied first if enabled.
    Temporary files created during preprocessing are automatically cleaned up after upload.
    
    Note: Image preprocessing (optimization/enhancement) only works on individual image files,
    NOT on PDFs. PDFs are processed as-is by Mistral OCR which handles them natively.

    Args:
        client: Mistral client instance
        file_path: Path to file to upload

    Returns:
        Signed URL if successful, None otherwise
    """
    # Track temporary files to clean up
    temp_files_to_cleanup = []
    
    try:
        # Apply preprocessing to images (if enabled)
        # Note: This does NOT work for PDFs - only for standalone image files
        processed_file_path = file_path
        if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
            logger.debug(f"Image file detected: {file_path.suffix}")
            
            # Apply image preprocessing if enabled (contrast, sharpness)
            if config.MISTRAL_ENABLE_IMAGE_PREPROCESSING:
                preprocessed_path = preprocess_image(file_path)
                if preprocessed_path and preprocessed_path != file_path:
                    processed_file_path = preprocessed_path
                    temp_files_to_cleanup.append(preprocessed_path)  # Track for cleanup
                    logger.info(f"Image preprocessed: {processed_file_path.name}")
            
            # Apply image optimization if enabled (resize, compress)
            if config.MISTRAL_ENABLE_IMAGE_OPTIMIZATION:
                optimized_path = optimize_image(processed_file_path)
                if optimized_path and optimized_path != processed_file_path:
                    processed_file_path = optimized_path
                    temp_files_to_cleanup.append(optimized_path)  # Track for cleanup
                    logger.info(f"Image optimized: {processed_file_path.name}")
        else:
            logger.debug(f"PDF/document file - preprocessing skipped (not applicable)")
        
        logger.info(f"Uploading file to Mistral: {processed_file_path.name}")

        with open(processed_file_path, "rb") as f:
            file_content = f.read()

        # Upload with purpose="ocr"
        response = client.files.upload(
            file={
                "file_name": file_path.name,  # Use original name
                "content": file_content,
            },
            purpose="ocr",  # Critical: Must specify purpose="ocr"
        )

        if not hasattr(response, "id"):
            logger.error("Upload response missing file ID")
            # Clean up temp files before returning
            _cleanup_temp_files(temp_files_to_cleanup)
            return None

        logger.info(f"File uploaded successfully: {response.id}")

        # Get signed URL for the uploaded file
        # The signed URL is required to process the file with OCR
        signed_url_response = client.files.get_signed_url(
            file_id=response.id,
            expiry=1,  # URL expires in 1 hour
        )

        if hasattr(signed_url_response, "url"):
            logger.debug(f"Got signed URL for file {response.id}")
            # Clean up temp files after successful upload
            _cleanup_temp_files(temp_files_to_cleanup)
            return signed_url_response.url
        else:
            logger.error("Failed to get signed URL for uploaded file")
            # Clean up temp files before returning
            _cleanup_temp_files(temp_files_to_cleanup)
            return None

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        # Clean up temp files on error
        _cleanup_temp_files(temp_files_to_cleanup)
        return None


def _cleanup_temp_files(temp_files: List[Path]) -> None:
    """
    Clean up temporary files created during image preprocessing.
    
    Args:
        temp_files: List of temporary file paths to delete
    """
    if not temp_files:
        return
    
    for temp_file in temp_files:
        try:
            if temp_file and temp_file.exists():
                temp_file.unlink()
                logger.debug(f"Deleted temporary file: {temp_file.name}")
        except Exception as e:
            logger.warning(f"Could not delete temporary file {temp_file.name}: {e}")


# ============================================================================
# OCR Processing
# ============================================================================


def process_with_ocr(
    client: Mistral,
    file_path: Path,
    model: Optional[str] = None,
    pages: Optional[List[int]] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Process file with Mistral OCR.

    Args:
        client: Mistral client instance
        file_path: Path to file
        model: Optional model override
        pages: Optional specific pages to process (0-indexed)
        progress_callback: Optional callback for progress updates (message, progress_0_to_1)

    Returns:
        Tuple of (success, ocr_result_dict, error_message)
    """

    def _report_progress(message: str, progress: float = 0.0):
        """Report progress if callback is provided and streaming is enabled."""
        if progress_callback and config.ENABLE_STREAMING:
            progress_callback(message, progress)

    try:
        _report_progress("Analyzing file...", 0.1)
        # Determine best model
        if model is None:
            model = config.get_ocr_model()

        logger.info(f"Processing with Mistral OCR using model: {model}")

        _report_progress("Preparing document...", 0.2)

        # ALWAYS use Files API for better OCR quality (not base64)
        # The Files API produces significantly better results than base64 encoding
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        use_files_api = True  # Always use Files API for best quality

        # Prepare document - use dict format instead of model classes
        if use_files_api:
            _report_progress(f"Uploading file ({file_size_mb:.1f} MB)...", 0.3)
            # Upload file and get signed URL
            # NOTE: The Mistral OCR API requires a signed HTTPS URL, not a file ID
            # After uploading, we must call get_signed_url() to get an HTTPS URL
            signed_url = upload_file_for_ocr(client, file_path)
            if not signed_url:
                return False, None, "Failed to upload file"

            _report_progress("Upload complete", 0.4)
            document = {
                "type": "document_url",
                "document_url": signed_url,  # Use the signed HTTPS URL
            }
        else:
            # Use base64 encoding for smaller files
            with open(file_path, "rb") as f:
                file_content = base64.b64encode(f.read()).decode("utf-8")

            # Determine MIME type
            mime_types = {
                "pdf": "application/pdf",
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            }

            ext = file_path.suffix.lower().lstrip(".")
            mime_type = mime_types.get(ext, "application/octet-stream")

            document = {
                "type": "document_url",
                "document_url": f"data:{mime_type};base64,{file_content}",
            }

        # Get retry configuration
        retry_config = get_retry_config()

        # Get structured output formats if enabled
        bbox_format = get_bbox_annotation_format()
        doc_format = get_document_annotation_format()

        _report_progress("Processing with Mistral OCR...", 0.5)

        # Build OCR request parameters
        # Note: Mistral OCR API only accepts: model, document, include_image_base64,
        # pages (optional), bbox_annotation_format, document_annotation_format, retries
        # Parameters like temperature, max_tokens, language are NOT supported by OCR endpoint
        ocr_params = {
            "model": model,
            "document": document,
            "include_image_base64": config.MISTRAL_INCLUDE_IMAGES,
            "retries": retry_config,
        }
        
        # Add optional parameters (only those supported by OCR API)
        if pages is not None:
            ocr_params["pages"] = pages
        
        # Add structured output formats if they were successfully created
        if bbox_format is not None:
            ocr_params["bbox_annotation_format"] = bbox_format
        if doc_format is not None:
            ocr_params["document_annotation_format"] = doc_format

        # Process with OCR
        response = client.ocr.process(**ocr_params)

        _report_progress("Parsing OCR response...", 0.8)

        # Parse response
        if response:
            result = _parse_ocr_response(response, file_path)

            # Validate that we got actual text content
            if not result.get("full_text", "").strip():
                error_msg = "Mistral OCR returned empty text. Your API key may not have OCR access. "
                error_msg += "Try using Mode 3 (MarkItDown Only) instead, which works perfectly for text-based PDFs."
                logger.warning(error_msg)
                return False, None, error_msg

            _report_progress("OCR processing complete", 1.0)
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


async def process_with_ocr_async(
    client: Mistral,
    file_path: Path,
    model: Optional[str] = None,
    pages: Optional[List[int]] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Process file with Mistral OCR asynchronously.

    Args:
        client: Mistral client instance
        file_path: Path to file
        model: Optional model override
        pages: Optional specific pages to process (0-indexed)
        progress_callback: Optional callback for progress updates (message, progress_0_to_1)

    Returns:
        Tuple of (success, ocr_result_dict, error_message)
    """

    def _report_progress(message: str, progress: float = 0.0):
        """Report progress if callback is provided and streaming is enabled."""
        if progress_callback and config.ENABLE_STREAMING:
            progress_callback(message, progress)

    try:
        _report_progress("Analyzing file (async)...", 0.1)
        # Determine best model
        if model is None:
            model = config.get_ocr_model()

        logger.info(f"Processing with Mistral OCR (async) using model: {model}")

        # ALWAYS use Files API for better OCR quality
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        use_files_api = True  # Always use Files API for best quality

        # Prepare document - use dict format instead of model classes
        if use_files_api:
            # Upload file and get signed URL
            signed_url = upload_file_for_ocr(client, file_path)
            if not signed_url:
                return False, None, "Failed to upload file"

            document = {
                "type": "document_url",
                "document_url": signed_url,
            }
        else:
            # Use base64 encoding for smaller files
            with open(file_path, "rb") as f:
                file_content = base64.b64encode(f.read()).decode("utf-8")

            # Determine MIME type
            mime_types = {
                "pdf": "application/pdf",
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            }

            ext = file_path.suffix.lower().lstrip(".")
            mime_type = mime_types.get(ext, "application/octet-stream")

            document = {
                "type": "document_url",
                "document_url": f"data:{mime_type};base64,{file_content}",
            }

        # Get retry configuration
        retry_config = get_retry_config()

        # Get structured output formats if enabled
        bbox_format = get_bbox_annotation_format()
        doc_format = get_document_annotation_format()

        # Build OCR request parameters
        # Note: Mistral OCR API only accepts: model, document, include_image_base64,
        # pages (optional), bbox_annotation_format, document_annotation_format, retries
        # Parameters like temperature, max_tokens, language are NOT supported by OCR endpoint
        ocr_params = {
            "model": model,
            "document": document,
            "include_image_base64": config.MISTRAL_INCLUDE_IMAGES,
            "retries": retry_config,
        }
        
        # Add optional parameters (only those supported by OCR API)
        if pages is not None:
            ocr_params["pages"] = pages
        
        # Add structured output formats if they were successfully created
        if bbox_format is not None:
            ocr_params["bbox_annotation_format"] = bbox_format
        if doc_format is not None:
            ocr_params["document_annotation_format"] = doc_format

        # Process with OCR (async)
        response = await client.ocr.process_async(**ocr_params)

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
        error_msg = f"Error processing with Mistral OCR (async): {e}"

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
        "bbox_annotations": [],  # NEW: Structured bounding box data
        "document_annotation": None,  # NEW: Structured document-level data
    }

    try:
        # Extract structured outputs if present
        if hasattr(response, "bbox_annotations") and response.bbox_annotations:
            result["bbox_annotations"] = [
                bbox.model_dump() if hasattr(bbox, "model_dump") else bbox
                for bbox in response.bbox_annotations
            ]
            logger.debug(
                f"Extracted {len(result['bbox_annotations'])} bbox annotations"
            )

        if hasattr(response, "document_annotation") and response.document_annotation:
            result["document_annotation"] = (
                response.document_annotation.model_dump()
                if hasattr(response.document_annotation, "model_dump")
                else response.document_annotation
            )
            logger.debug("Extracted document annotation")
        # Try different response formats
        # Format 1: response.pages (list of page objects)
        if hasattr(response, "pages") and response.pages:
            logger.debug(f"Found {len(response.pages)} pages in response")

            for idx, page in enumerate(response.pages):
                # Try different text attributes (markdown is the primary one for Mistral OCR)
                page_text = ""

                if hasattr(page, "markdown") and page.markdown:
                    page_text = page.markdown
                elif hasattr(page, "text") and page.text:
                    page_text = page.text
                elif hasattr(page, "content") and page.content:
                    page_text = page.content
                elif isinstance(page, dict):
                    page_text = page.get(
                        "markdown", page.get("text", page.get("content", ""))
                    )
                elif isinstance(page, str):
                    page_text = page

                # Apply cleaning to remove consecutive duplicate lines (OCR artifacts)
                original_length = len(page_text)
                page_text = utils.clean_consecutive_duplicates(page_text)
                cleaned_length = len(page_text)

                if cleaned_length < original_length:
                    reduction = original_length - cleaned_length
                    logger.debug(
                        f"Page {idx}: Cleaned {reduction} chars of consecutive duplicates."
                    )

                logger.debug(f"Page {idx}: {len(page_text)} chars extracted")

                page_data = {
                    # Enforce standardized 0-based index instead of relying on OCR metadata
                    "page_number": idx,
                    "text": page_text,
                    "images": [],
                }

                # Extract images from page
                if hasattr(page, "images") and page.images:
                    logger.debug(f"Page {idx} has {len(page.images)} images")
                    for img in page.images:
                        image_data = {
                            "bbox": getattr(img, "bbox", None),
                            "base64": getattr(img, "base64", None)
                            if config.MISTRAL_INCLUDE_IMAGES
                            else None,
                        }
                        page_data["images"].append(image_data)

                result["pages"].append(page_data)
                if page_text:
                    result["full_text"] += page_text + "\n\n"

        # Format 2: response.markdown (Mistral OCR format)
        elif hasattr(response, "markdown") and response.markdown:
            cleaned_text = utils.clean_consecutive_duplicates(response.markdown)
            result["full_text"] = cleaned_text
            result["pages"].append(
                {
                    "page_number": 0,
                    "text": cleaned_text,
                    "images": [],
                }
            )

        # Format 3: response.text (direct text)
        elif hasattr(response, "text") and response.text:
            cleaned_text = utils.clean_consecutive_duplicates(response.text)
            result["full_text"] = cleaned_text
            result["pages"].append(
                {
                    "page_number": 0,
                    "text": cleaned_text,
                    "images": [],
                }
            )

        # Format 4: response.content
        elif hasattr(response, "content") and response.content:
            cleaned_text = utils.clean_consecutive_duplicates(response.content)
            result["full_text"] = cleaned_text
            result["pages"].append(
                {
                    "page_number": 0,
                    "text": cleaned_text,
                    "images": [],
                }
            )

        # Format 5: response as dict
        elif isinstance(response, dict):
            if "pages" in response:
                for idx, page in enumerate(response["pages"]):
                    page_text = page.get(
                        "markdown", page.get("text", page.get("content", ""))
                    )
                    # Apply cleaning to dict-based pages
                    page_text = utils.clean_consecutive_duplicates(page_text)
                    result["pages"].append(
                        {
                            "page_number": idx,  # Standardized numbering
                            "text": page_text,
                            "images": page.get("images", []),
                        }
                    )
                    if page_text:
                        result["full_text"] += page_text + "\n\n"
            elif "markdown" in response:
                cleaned_text = utils.clean_consecutive_duplicates(response["markdown"])
                result["full_text"] = cleaned_text
                result["pages"].append(
                    {
                        "page_number": 0,
                        "text": cleaned_text,
                        "images": [],
                    }
                )
            elif "text" in response:
                cleaned_text = utils.clean_consecutive_duplicates(response["text"])
                result["full_text"] = cleaned_text
                result["pages"].append(
                    {
                        "page_number": 0,
                        "text": cleaned_text,
                        "images": [],
                    }
                )

        # Extract metadata
        if hasattr(response, "metadata"):
            result["metadata"] = response.metadata
        elif isinstance(response, dict) and "metadata" in response:
            result["metadata"] = response["metadata"]

        # Log final result
        logger.debug(
            f"Extracted {len(result['pages'])} pages, {len(result['full_text'])} chars"
        )

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

    # Check 1: Very short text
    if len(text.strip()) < OCR_MIN_TEXT_LENGTH:
        return True

    # Check 2: Count digits (financial docs should have many numbers)
    digit_count = sum(1 for char in text if char.isdigit())
    if digit_count < OCR_MIN_DIGIT_COUNT:
        return True

    # Check 3: Token uniqueness ratio (detect heavy repetition)
    tokens = text.split()
    if not tokens:
        return True

    unique_tokens = set(tokens)
    uniqueness_ratio = len(unique_tokens) / len(tokens)

    if uniqueness_ratio < OCR_MIN_UNIQUENESS_RATIO:
        logger.debug(f"Low uniqueness ratio: {uniqueness_ratio:.2f}")
        return True

    # Check 4: Detect repeated header patterns
    # Count occurrences of common repeated strings
    common_phrases = [
        "5151 E Broadway",  # Example from SWE feedback
        "Page 1",
        "Page 2",
        "Page 3",
    ]

    for phrase in common_phrases:
        occurrences = text.count(phrase)
        if occurrences > OCR_MAX_PHRASE_REPETITIONS:
            logger.debug(f"Repeated phrase '{phrase}' found {occurrences} times")
            return True

    # Check 5: Average line length (very short lines suggest parsing issues)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if lines:
        avg_line_length = sum(len(line) for line in lines) / len(lines)
        if avg_line_length < OCR_MIN_AVG_LINE_LENGTH:
            logger.debug(f"Short average line length: {avg_line_length:.1f}")
            return True

    return False


def assess_ocr_quality(ocr_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assess the quality of OCR results to determine if they should be used.

    Args:
        ocr_result: OCR result dictionary

    Returns:
        Dictionary with quality assessment:
        {
            "is_usable": bool,           # Overall quality verdict
            "quality_score": float,       # 0-100 score
            "issues": List[str],          # List of quality issues found
            "weak_page_count": int,       # Number of weak pages
            "total_page_count": int,      # Total pages analyzed
            "digit_count": int,           # Total digits extracted
            "uniqueness_ratio": float,    # Token uniqueness across all pages
        }
    """
    full_text = ocr_result.get("full_text", "")
    pages = ocr_result.get("pages", [])

    assessment = {
        "is_usable": True,
        "quality_score": 100.0,
        "issues": [],
        "weak_page_count": 0,
        "total_page_count": len(pages),
        "digit_count": 0,
        "uniqueness_ratio": 0.0,
    }

    if not full_text or len(full_text.strip()) < 50:
        assessment["is_usable"] = False
        assessment["quality_score"] = 0.0
        assessment["issues"].append("Minimal text extracted")
        return assessment

    # Count weak pages
    for page in pages:
        page_text = page.get("text", "")
        if _is_weak_page(page_text):
            assessment["weak_page_count"] += 1

    # Calculate metrics
    assessment["digit_count"] = sum(1 for char in full_text if char.isdigit())

    tokens = full_text.split()
    if tokens:
        unique_tokens = set(tokens)
        assessment["uniqueness_ratio"] = len(unique_tokens) / len(tokens)

    # Deduct points for issues
    if assessment["weak_page_count"] > 0:
        weak_ratio = assessment["weak_page_count"] / max(
            1, assessment["total_page_count"]
        )
        points_lost = weak_ratio * 50  # Up to 50 points for all weak pages
        assessment["quality_score"] -= points_lost
        assessment["issues"].append(
            f"{assessment['weak_page_count']}/{assessment['total_page_count']} pages are weak quality"
        )

    if assessment["digit_count"] < 100:  # Low number count for financial docs
        assessment["quality_score"] -= 20
        assessment["issues"].append(
            f"Low numerical content ({assessment['digit_count']} digits)"
        )

    if assessment["uniqueness_ratio"] < 0.3:  # Highly repetitive
        assessment["quality_score"] -= 30
        assessment["issues"].append(
            f"High repetition (uniqueness: {assessment['uniqueness_ratio']:.1%})"
        )

    # Final verdict
    if assessment["quality_score"] < 40:
        assessment["is_usable"] = False
        assessment["issues"].append("Overall quality too low for inclusion")

    logger.info(
        f"OCR Quality Assessment: Score={assessment['quality_score']:.1f}/100, "
        f"Usable={assessment['is_usable']}, Issues={len(assessment['issues'])}"
    )

    return assessment


def improve_weak_pages(
    client: Mistral, file_path: Path, ocr_result: Dict[str, Any], model: str
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
                client, file_path, model=model, pages=[page_idx]
            )

            if success and improved_result:
                # Replace weak page with improved result
                if improved_result.get("pages") and len(improved_result["pages"]) > 0:
                    improved_page = improved_result["pages"][0]

                    if len(improved_page.get("text", "")) > len(
                        ocr_result["pages"][page_idx].get("text", "")
                    ):
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


def save_extracted_images(ocr_result: Dict[str, Any], file_path: Path) -> List[Path]:
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

                with open(image_path, "wb") as f:
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
    file_path: Path, use_cache: bool = True, improve_weak: bool = True
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
        error_msg = (
            "Mistral client not available. Please set MISTRAL_API_KEY in .env file"
        )
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

    # Assess OCR quality
    logger.info("Assessing OCR quality...")
    quality_assessment = assess_ocr_quality(ocr_result)
    ocr_result["quality_assessment"] = quality_assessment

    # Re-process weak pages if requested and quality is low
    if (
        improve_weak
        and ocr_result.get("pages")
        and quality_assessment.get("weak_page_count", 0) > 0
    ):
        logger.info(
            f"Attempting to improve {quality_assessment['weak_page_count']} weak pages..."
        )
        content_analysis = local_converter.analyze_file_content(file_path)
        model = config.select_best_model(
            file_type=file_path.suffix.lower().lstrip("."),
            content_analysis=content_analysis,
        )
        ocr_result = improve_weak_pages(client, file_path, ocr_result, model)

        # Re-assess quality after improvement
        improved_quality = assess_ocr_quality(ocr_result)
        ocr_result["quality_assessment"] = improved_quality
        logger.info(
            f"Quality after improvement: {improved_quality['quality_score']:.1f}/100"
        )

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
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(ocr_result, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved OCR metadata: {json_path.name}")

    # Save structured outputs if they exist
    _save_structured_outputs(file_path, ocr_result)

    return True, output_path, None


async def convert_with_mistral_ocr_async(
    file_path: Path, use_cache: bool = True, improve_weak: bool = True
) -> Tuple[bool, Optional[Path], Optional[str]]:
    """
    Convert file using Mistral OCR with full pipeline (async version).

    Args:
        file_path: Path to file
        use_cache: Use cached results if available
        improve_weak: Re-process weak pages

    Returns:
        Tuple of (success, output_md_path, error_message)
    """
    client = get_mistral_client()
    if client is None:
        error_msg = (
            "Mistral client not available. Please set MISTRAL_API_KEY in .env file"
        )
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
            success, ocr_result, error = await process_with_ocr_async(client, file_path)
    else:
        success, ocr_result, error = await process_with_ocr_async(client, file_path)

    if not success or not ocr_result:
        return False, None, error

    # Assess OCR quality
    logger.info("Assessing OCR quality...")
    quality_assessment = assess_ocr_quality(ocr_result)
    ocr_result["quality_assessment"] = quality_assessment

    # Re-process weak pages if requested and quality is low
    # Note: Weak page improvement is synchronous for now
    if (
        improve_weak
        and ocr_result.get("pages")
        and quality_assessment.get("weak_page_count", 0) > 0
    ):
        logger.info(
            f"Attempting to improve {quality_assessment['weak_page_count']} weak pages..."
        )
        content_analysis = local_converter.analyze_file_content(file_path)
        model = config.select_best_model(
            file_type=file_path.suffix.lower().lstrip("."),
            content_analysis=content_analysis,
        )
        ocr_result = improve_weak_pages(client, file_path, ocr_result, model)

        # Re-assess quality after improvement
        improved_quality = assess_ocr_quality(ocr_result)
        ocr_result["quality_assessment"] = improved_quality
        logger.info(
            f"Quality after improvement: {improved_quality['quality_score']:.1f}/100"
        )

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
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(ocr_result, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved OCR metadata: {json_path.name}")

    # Save structured outputs if they exist
    _save_structured_outputs(file_path, ocr_result)

    return True, output_path, None


def _save_structured_outputs(file_path: Path, ocr_result: Dict[str, Any]) -> None:
    """
    Save structured outputs from bbox and document annotations.

    Args:
        file_path: Original file path
        ocr_result: OCR result dictionary containing structured outputs
    """
    # Save bounding box annotations if present
    if "bbox_annotations" in ocr_result and ocr_result["bbox_annotations"]:
        bbox_path = config.OUTPUT_MD_DIR / f"{file_path.stem}_bbox_annotations.json"
        with open(bbox_path, "w", encoding="utf-8") as f:
            json.dump(ocr_result["bbox_annotations"], f, indent=2, ensure_ascii=False)
        logger.info(f"Saved bbox annotations: {bbox_path.name}")

    # Save document annotations if present
    if "document_annotation" in ocr_result and ocr_result["document_annotation"]:
        doc_path = config.OUTPUT_MD_DIR / f"{file_path.stem}_document_annotation.json"
        with open(doc_path, "w", encoding="utf-8") as f:
            json.dump(
                ocr_result["document_annotation"], f, indent=2, ensure_ascii=False
            )
        logger.info(f"Saved document annotation: {doc_path.name}")


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
        },
    )

    # Build markdown content
    md_content = frontmatter + f"\n# OCR Result: {file_path.name}\n\n"

    # Add page-by-page breakdown (no "Full Text" section to avoid duplication)
    if ocr_result.get("pages"):
        total_pages = len(ocr_result["pages"])
        md_content += (
            f"## OCR Content ({total_pages} page{'s' if total_pages != 1 else ''})\n\n"
        )

        # Iterate directly over pages. Since page_number is standardized to 0-based index in _parse_ocr_response,
        # we just need to add 1 for 1-based display (Page 1, Page 2, etc.)
        for page in ocr_result["pages"]:
            text = page.get("text", "")
            # Display as 1-based index using the standardized 0-based page_number
            display_page_num = page.get("page_number", 0) + 1

            md_content += f"### Page {display_page_num}\n\n"
            md_content += text
            md_content += "\n\n---\n\n"
    else:
        # Fallback if pages aren't available (shouldn't happen, but be defensive)
        md_content += "## OCR Content\n\n"
        md_content += ocr_result.get("full_text", "")
        md_content += "\n\n---\n\n"

    # Save markdown
    output_path = config.OUTPUT_MD_DIR / f"{file_path.stem}_mistral_ocr.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # Save text version
    utils.save_text_output(output_path, md_content)

    logger.info(f"Saved Mistral OCR output: {output_path.name}")

    return output_path
