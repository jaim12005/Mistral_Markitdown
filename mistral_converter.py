"""
Enhanced Document Converter - Mistral AI Integration Module

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
import re
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from functools import lru_cache

try:
    from mistralai import Mistral
    from mistralai import models
    from mistralai.utils import retries
    # New SDK types for OCR document handling
    from mistralai import DocumentURLChunk, ImageURLChunk, FileChunk
except ImportError:
    Mistral = None
    models = None
    retries = None
    DocumentURLChunk = None
    ImageURLChunk = None
    FileChunk = None

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
# OCR Quality Assessment
# ============================================================================
# NOTE: All OCR quality thresholds are now configured via config.py
# This ensures .env settings are honored as documented in README.md
# See: config.OCR_MIN_TEXT_LENGTH, config.OCR_MIN_DIGIT_COUNT, etc.

# ============================================================================
# Mistral Client Initialization
# ============================================================================


@lru_cache(maxsize=1)
def get_mistral_client() -> Optional[Mistral]:
    """
    Create and configure a Mistral client instance.
    Cached to prevent connection pool churn in batch operations.

    Thread-safety note:
        The Mistral SDK client uses ``httpx`` under the hood, which is
        thread-safe for concurrent requests.  This cached singleton is
        therefore safe to share across the ``ThreadPoolExecutor`` used
        by batch processing modes.  If you switch to a different HTTP
        backend or need per-thread isolation, replace this with a
        ``threading.local()`` pattern.

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
        client_kwargs = {"api_key": config.MISTRAL_API_KEY}

        # Set global retry config on client (applies to all calls by default)
        global_retry = get_retry_config()
        if global_retry:
            client_kwargs["retry_config"] = global_retry

        # Set global timeout (60 seconds default)
        client_kwargs["timeout_ms"] = config.RETRY_MAX_ELAPSED_TIME_MS

        client = Mistral(**client_kwargs)
        return client

    except Exception as e:
        logger.error(f"Error initializing Mistral client: {e}")
        return None


def reset_mistral_client() -> None:
    """Clear the cached Mistral client so the next call creates a fresh one.

    Useful after rotating an API key at runtime or in tests.
    """
    get_mistral_client.cache_clear()


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


def _extract_model_json_schema(pydantic_model: Any) -> Optional[Dict[str, Any]]:
    """Return JSON schema dict from a Pydantic model across v1/v2 APIs."""
    if hasattr(pydantic_model, "model_json_schema"):
        return pydantic_model.model_json_schema()
    if hasattr(pydantic_model, "schema"):
        return pydantic_model.schema()
    return None


def get_bbox_annotation_format() -> Optional[Dict[str, Any]]:
    """
    Get schema format for bounding box annotation.

    IMPORTANT: The OCR API expects raw JSON schema dicts, NOT ResponseFormat objects.
    ResponseFormat (from response_format_from_pydantic_model) is for chat completion
    structured outputs only. The OCR endpoint's bbox_annotation_format and
    document_annotation_format parameters require plain JSON schema dictionaries.

    Returns:
        Raw JSON schema dict for bbox annotation, or None if disabled
    """
    if not config.MISTRAL_ENABLE_BBOX_ANNOTATION:
        return None

    # Try to get JSON schema from Pydantic model (preferred - type-safe)
    pydantic_model = schemas.get_bbox_pydantic_model()
    if pydantic_model is not None:
        try:
            # Extract raw JSON schema from Pydantic model (v1/v2 compatible)
            json_schema = _extract_model_json_schema(pydantic_model)
            if json_schema:
                logger.debug("Using Pydantic-derived JSON schema for bbox annotation")
                return json_schema
        except Exception as e:
            logger.debug(f"Could not get JSON schema from Pydantic model: {e}, falling back to predefined schema")

    # Fallback to predefined JSON schema from schemas.py
    bbox_schema = schemas.get_bbox_schema("structured")
    return bbox_schema.get("schema")


def get_document_annotation_format(doc_type: str = "auto") -> Optional[Dict[str, Any]]:
    """
    Get schema format for document-level annotation.

    IMPORTANT: The OCR API expects raw JSON schema dicts, NOT ResponseFormat objects.
    ResponseFormat (from response_format_from_pydantic_model) is for chat completion
    structured outputs only. The OCR endpoint's document_annotation_format parameter
    requires a plain JSON schema dictionary.

    Args:
        doc_type: Document type (invoice, financial_statement, form, generic, auto).
                  When set to "auto", the value of MISTRAL_DOCUMENT_SCHEMA_TYPE from
                  the environment is used.  If that is also "auto", "generic" is used
                  as the final fallback.  True content-based auto-detection is not yet
                  implemented; set the schema type explicitly for best results.

    Returns:
        Raw JSON schema dict for document annotation, or None if disabled
    """
    if not config.MISTRAL_ENABLE_DOCUMENT_ANNOTATION:
        return None

    # Auto-detect based on config if set to auto
    if doc_type == "auto":
        doc_type = config.MISTRAL_DOCUMENT_SCHEMA_TYPE
        if doc_type == "auto":
            doc_type = "generic"  # Default fallback

    # Try to get JSON schema from Pydantic model (preferred - type-safe)
    pydantic_model = schemas.get_document_pydantic_model(doc_type)
    if pydantic_model is not None:
        try:
            # Extract raw JSON schema from Pydantic model (v1/v2 compatible)
            json_schema = _extract_model_json_schema(pydantic_model)
            if json_schema:
                logger.debug(f"Using Pydantic-derived JSON schema for document annotation (type: {doc_type})")
                return json_schema
        except Exception as e:
            logger.debug(f"Could not get JSON schema from Pydantic model: {e}, falling back to predefined schema")

    # Fallback to predefined JSON schema from schemas.py
    document_schema = schemas.get_document_schema(doc_type)
    return document_schema.get("schema")


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

        # Save preprocessed image with format-appropriate parameters
        preprocessed_path = (
            image_path.parent / f"{image_path.stem}_preprocessed{image_path.suffix}"
        )
        if image_path.suffix.lower() in [".jpg", ".jpeg"]:
            img.save(preprocessed_path, format="JPEG", quality=95, optimize=True)
        elif image_path.suffix.lower() == ".png":
            img.save(preprocessed_path, format="PNG", optimize=True)
        else:
            img.save(preprocessed_path)

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

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)

        def _cleanup_files_by_purpose(purpose: str) -> int:
            """Delete files older than cutoff_date for a given purpose."""
            deleted = 0
            page = 0
            page_size = 100

            while True:
                try:
                    files_response = client.files.list(purpose=purpose, page=page, page_size=page_size)
                    files_list = files_response.data if hasattr(files_response, 'data') else files_response
                except Exception as e:
                    logger.debug(f"Error listing {purpose} files for cleanup (page {page}): {e}")
                    break

                if not files_list:
                    break

                for file in files_list:
                    try:
                        if not hasattr(file, 'created_at'):
                            continue

                        if isinstance(file.created_at, str):
                            file_created = datetime.fromisoformat(file.created_at.replace('Z', '+00:00'))
                        elif hasattr(file.created_at, 'replace'):
                            file_created = file.created_at
                            if file_created.tzinfo is None:
                                file_created = file_created.replace(tzinfo=timezone.utc)
                        else:
                            logger.debug(f"Unexpected created_at type for file {file.id}: {type(file.created_at)}")
                            continue

                        if file_created < cutoff_date:
                            client.files.delete(file_id=file.id)
                            deleted += 1
                            logger.debug(f"Deleted old {purpose} file: {file.id} (created {file_created})")
                    except Exception as e:
                        logger.debug(f"Error processing {purpose} file {file.id}: {e}")
                        continue

                total = getattr(files_response, 'total', None)
                if isinstance(total, int) and total >= 0 and (page + 1) * page_size >= total:
                    break
                if len(files_list) < page_size:
                    break
                page += 1

            return deleted

        deleted = _cleanup_files_by_purpose("ocr")
        deleted += _cleanup_files_by_purpose("batch")

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
    Temporary files created during preprocessing are always cleaned up.

    Note: Image preprocessing (optimization/enhancement) only works on individual image files,
    NOT on PDFs. PDFs are processed as-is by Mistral OCR which handles them natively.

    Args:
        client: Mistral client instance
        file_path: Path to file to upload

    Returns:
        Signed URL if successful, None otherwise
    """
    temp_files_to_cleanup: List[Path] = []

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
                    temp_files_to_cleanup.append(preprocessed_path)
                    logger.info(f"Image preprocessed: {processed_file_path.name}")

            # Apply image optimization if enabled (resize, compress)
            if config.MISTRAL_ENABLE_IMAGE_OPTIMIZATION:
                optimized_path = optimize_image(processed_file_path)
                if optimized_path and optimized_path != processed_file_path:
                    processed_file_path = optimized_path
                    temp_files_to_cleanup.append(optimized_path)
                    logger.info(f"Image optimized: {processed_file_path.name}")
        else:
            logger.debug("PDF/document file - preprocessing skipped (not applicable)")

        logger.info(f"Uploading file to Mistral: {processed_file_path.name}")

        # Stream file object directly (avoids loading full file bytes into memory first).
        with open(processed_file_path, "rb") as f:
            response = client.files.upload(
                file={
                    "file_name": file_path.name,  # Use original name
                    "content": f,
                },
                purpose="ocr",  # Critical: Must specify purpose="ocr"
            )

        if not hasattr(response, "id"):
            logger.error("Upload response missing file ID")
            return None

        logger.info(f"File uploaded successfully: {response.id}")

        # Get signed URL for the uploaded file
        signed_url_response = client.files.get_signed_url(
            file_id=response.id,
            expiry=config.MISTRAL_SIGNED_URL_EXPIRY,  # URL expiry in hours
        )

        if hasattr(signed_url_response, "url"):
            logger.debug(f"Got signed URL for file {response.id}")
            return signed_url_response.url

        logger.error("Failed to get signed URL for uploaded file")
        return None

    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return None
    finally:
        _cleanup_temp_files(temp_files_to_cleanup)


def upload_file_for_ocr_chunk(client: Mistral, file_path: Path) -> Optional[Any]:
    """
    Upload file and return a FileChunk for direct use with OCR (no signed URL needed).

    This is simpler than the signed URL flow: upload once, pass the file ID directly.

    Args:
        client: Mistral client instance
        file_path: Path to file to upload

    Returns:
        FileChunk instance if successful, None otherwise
    """
    if FileChunk is None:
        logger.debug("FileChunk not available in SDK, falling back to signed URL flow")
        return None

    try:
        with open(file_path, "rb") as f:
            response = client.files.upload(
                file={"file_name": file_path.name, "content": f},
                purpose="ocr",
            )

        if not hasattr(response, "id"):
            return None

        logger.info(f"File uploaded for FileChunk: {response.id}")
        return FileChunk(file_id=response.id)

    except Exception as e:
        logger.warning(f"FileChunk upload failed: {e}, will fall back to signed URL")
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
    signed_url: Optional[str] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Process file with Mistral OCR.

    Args:
        client: Mistral client instance
        file_path: Path to file
        model: Optional model override
        pages: Optional specific pages to process (0-indexed)
        progress_callback: Optional callback for progress updates (message, progress_0_to_1)
        signed_url: Optional pre-obtained signed URL (avoids re-uploading for weak page improvement)

    Returns:
        Tuple of (success, ocr_result_dict, error_message)
    """

    def _report_progress(message: str, progress: float = 0.0):
        """Report progress if callback is provided."""
        if progress_callback:
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

        # Prepare document using SDK types when available
        # IMPORTANT: Mistral OCR API uses different types for images vs documents:
        # - Images (png, jpg, etc.): type="image_url", image_url=<url> -> ImageURLChunk
        # - Documents (pdf, docx, etc.): type="document_url", document_url=<url> -> DocumentURLChunk
        ext = file_path.suffix.lower().lstrip(".")
        is_image = ext in config.IMAGE_EXTENSIONS

        if signed_url:
            logger.debug("Using provided signed URL for OCR")
        else:
            _report_progress(f"Uploading file ({file_size_mb:.1f} MB)...", 0.3)
            # Upload file and get signed URL
            # NOTE: The Mistral OCR API requires a signed HTTPS URL, not a file ID
            # After uploading, we must call get_signed_url() to get an HTTPS URL
            signed_url = upload_file_for_ocr(client, file_path)
            if not signed_url:
                return False, None, "Failed to upload file"
            _report_progress("Upload complete", 0.4)

        # Use SDK types when available (new recommended approach)
        # Fallback to dict format for compatibility
        if is_image:
            if ImageURLChunk is not None:
                document = ImageURLChunk(image_url=signed_url)
                logger.debug(f"Using ImageURLChunk for {ext} file")
            else:
                document = {
                    "type": "image_url",
                    "image_url": signed_url,
                }
                logger.debug(f"Using image_url dict for {ext} file")
        else:
            if DocumentURLChunk is not None:
                document = DocumentURLChunk(document_url=signed_url)
                logger.debug(f"Using DocumentURLChunk for {ext} file")
            else:
                document = {
                    "type": "document_url",
                    "document_url": signed_url,
                }
                logger.debug(f"Using document_url dict for {ext} file")

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
        if config.MISTRAL_DOCUMENT_ANNOTATION_PROMPT:
            ocr_params["document_annotation_prompt"] = config.MISTRAL_DOCUMENT_ANNOTATION_PROMPT

        # OCR 3 (mistral-ocr-2512) parameters
        if config.MISTRAL_TABLE_FORMAT:
            ocr_params["table_format"] = config.MISTRAL_TABLE_FORMAT
        # Always pass header/footer extraction flags so user can disable them
        ocr_params["extract_header"] = config.MISTRAL_EXTRACT_HEADER
        ocr_params["extract_footer"] = config.MISTRAL_EXTRACT_FOOTER
        if config.MISTRAL_IMAGE_LIMIT > 0:
            ocr_params["image_limit"] = config.MISTRAL_IMAGE_LIMIT
        if config.MISTRAL_IMAGE_MIN_SIZE > 0:
            ocr_params["image_min_size"] = config.MISTRAL_IMAGE_MIN_SIZE

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


def _parse_ocr_response(response: Any, file_path: Path) -> Dict[str, Any]:
    """
    Parse OCR response into structured dictionary.

    Handles the full OCR response format including:
    - pages: List of OCRPageObject with markdown, images, dimensions, tables, etc.
    - usage_info: pages_processed, doc_size_bytes
    - document_annotation: Structured output if document_annotation_format was provided
    - model: The model used for OCR

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
        "bbox_annotations": [],  # Structured bounding box data
        "document_annotation": None,  # Structured document-level data
        "usage_info": {},  # NEW: OCR usage information
        "model": None,  # NEW: Model used for OCR
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
                    # NEW: Additional page metadata from updated API
                    "dimensions": None,
                    "tables": [],
                    "hyperlinks": [],
                    "header": None,
                    "footer": None,
                }

                # Extract images from page
                if hasattr(page, "images") and page.images:
                    logger.debug(f"Page {idx} has {len(page.images)} images")
                    for img in page.images:
                        image_data = {
                            "id": getattr(img, "id", None),  # NEW: image ID
                            "top_left_x": getattr(img, "top_left_x", None),  # NEW: position
                            "top_left_y": getattr(img, "top_left_y", None),
                            "bottom_right_x": getattr(img, "bottom_right_x", None),
                            "bottom_right_y": getattr(img, "bottom_right_y", None),
                            "bbox": getattr(img, "bbox", None),  # Legacy format
                            "base64": getattr(img, "image_base64", None) or getattr(img, "base64", None)
                            if config.MISTRAL_INCLUDE_IMAGES
                            else None,
                        }
                        page_data["images"].append(image_data)

                # NEW: Extract dimensions (dpi, height, width)
                if hasattr(page, "dimensions") and page.dimensions:
                    dims = page.dimensions
                    page_data["dimensions"] = {
                        "dpi": getattr(dims, "dpi", None),
                        "height": getattr(dims, "height", None),
                        "width": getattr(dims, "width", None),
                    }
                    logger.debug(f"Page {idx} dimensions: {page_data['dimensions']}")

                # NEW: Extract tables from page
                if hasattr(page, "tables") and page.tables:
                    page_data["tables"] = [
                        t.model_dump() if hasattr(t, "model_dump") else t
                        for t in page.tables
                    ]
                    logger.debug(f"Page {idx} has {len(page_data['tables'])} tables")

                # NEW: Extract hyperlinks from page
                if hasattr(page, "hyperlinks") and page.hyperlinks:
                    page_data["hyperlinks"] = [
                        h.model_dump() if hasattr(h, "model_dump") else h
                        for h in page.hyperlinks
                    ]
                    logger.debug(f"Page {idx} has {len(page_data['hyperlinks'])} hyperlinks")

                # NEW: Extract header and footer
                if hasattr(page, "header") and page.header:
                    page_data["header"] = page.header
                if hasattr(page, "footer") and page.footer:
                    page_data["footer"] = page.footer

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

        # NEW: Extract usage_info (pages_processed, doc_size_bytes)
        if hasattr(response, "usage_info") and response.usage_info:
            usage = response.usage_info
            result["usage_info"] = {
                "pages_processed": getattr(usage, "pages_processed", None),
                "doc_size_bytes": getattr(usage, "doc_size_bytes", None),
            }
            logger.debug(f"Usage info: {result['usage_info']}")
        elif isinstance(response, dict) and "usage_info" in response:
            result["usage_info"] = response["usage_info"]

        # NEW: Extract model used for OCR
        if hasattr(response, "model") and response.model:
            result["model"] = response.model
            logger.debug(f"OCR model: {result['model']}")
        elif isinstance(response, dict) and "model" in response:
            result["model"] = response["model"]

        # Log final result
        logger.debug(
            f"Extracted {len(result['pages'])} pages, {len(result['full_text'])} chars"
        )

    except Exception as e:
        logger.error(f"Error parsing OCR response: {e}")
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

    All thresholds are configurable via config.py (from .env).

    Args:
        text: Page text to analyze

    Returns:
        True if page appears to have weak OCR results
    """
    if not text or len(text.strip()) < 10:
        return True

    # Check 1: Very short text (configurable via OCR_MIN_TEXT_LENGTH)
    if len(text.strip()) < config.OCR_MIN_TEXT_LENGTH:
        return True

    # Check 2: Count digits (financial docs should have many numbers)
    # Configurable via OCR_MIN_DIGIT_COUNT
    digit_count = sum(1 for char in text if char.isdigit())
    if digit_count < config.OCR_MIN_DIGIT_COUNT:
        return True

    # Check 3: Token uniqueness ratio (detect heavy repetition)
    # Configurable via OCR_MIN_UNIQUENESS_RATIO
    tokens = text.split()
    if not tokens:
        return True

    unique_tokens = set(tokens)
    uniqueness_ratio = len(unique_tokens) / len(tokens)

    if uniqueness_ratio < config.OCR_MIN_UNIQUENESS_RATIO:
        logger.debug(f"Low uniqueness ratio: {uniqueness_ratio:.2f}")
        return True

    # Check 4: Detect repeated header patterns
    # Use regex to catch all "Page N" patterns, not just a hardcoded few
    # Configurable via OCR_MAX_PHRASE_REPETITIONS
    page_refs = re.findall(r"Page\s+\d+", text)
    if len(page_refs) > config.OCR_MAX_PHRASE_REPETITIONS:
        logger.debug(f"Repeated page references found {len(page_refs)} times")
        return True

    # Check 5: Average line length (very short lines suggest parsing issues)
    # Configurable via OCR_MIN_AVG_LINE_LENGTH
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if lines:
        avg_line_length = sum(len(line) for line in lines) / len(lines)
        if avg_line_length < config.OCR_MIN_AVG_LINE_LENGTH:
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

    if assessment["digit_count"] < config.OCR_MIN_DIGIT_COUNT * 5:  # Aggregate threshold (page threshold * 5)
        assessment["quality_score"] -= 20
        assessment["issues"].append(
            f"Low numerical content ({assessment['digit_count']} digits)"
        )

    if assessment["uniqueness_ratio"] < config.OCR_MIN_UNIQUENESS_RATIO:  # Configurable threshold
        assessment["quality_score"] -= 30
        assessment["issues"].append(
            f"High repetition (uniqueness: {assessment['uniqueness_ratio']:.1%})"
        )

    # Final verdict (configurable via OCR_QUALITY_THRESHOLD_ACCEPTABLE)
    if assessment["quality_score"] < config.OCR_QUALITY_THRESHOLD_ACCEPTABLE:
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

    # Upload file ONCE for all weak pages to avoid redundant uploads
    # We'll reuse this signed URL for all page requests
    signed_url = None
    try:
        logger.debug("Uploading file once for weak page improvements...")
        signed_url = upload_file_for_ocr(client, file_path)
    except Exception as e:
        logger.warning(f"Failed to pre-upload for weak pages: {e}")
        # Continue anyway, process_with_ocr will handle upload individually if needed

    # Re-OCR weak pages
    for page_idx in weak_pages:
        try:
            success, improved_result, error = process_with_ocr(
                client, file_path, model=model, pages=[page_idx], signed_url=signed_url
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
                # Strip data URI prefix if present (e.g. "data:image/png;base64,...")
                if image_base64.startswith("data:"):
                    image_base64 = image_base64.split(",", 1)[1]

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


def _process_ocr_result_pipeline(
    client: Mistral,
    file_path: Path,
    ocr_result: Dict[str, Any],
    use_cache: bool = True,
    improve_weak: bool = True,
    from_cache: bool = False,
) -> Tuple[bool, Optional[Path], Optional[str]]:
    """
    Common pipeline for processing OCR results (quality check, improvement, saving).

    Args:
        client: Mistral client instance
        file_path: Path to file
        ocr_result: OCR result dictionary
        use_cache: Whether to cache the result
        improve_weak: Whether to improve weak pages
        from_cache: Whether this result came from cache (skips re-improvement and image saving)

    Returns:
        Tuple of (success, output_md_path, error_message)
    """
    quality_assessment: Optional[Dict[str, Any]] = None

    # If from cache, reuse stored quality assessment if available
    if from_cache and "quality_assessment" in ocr_result:
        logger.info("Using cached OCR result with stored quality assessment")
        quality_assessment = ocr_result["quality_assessment"]
    elif config.ENABLE_OCR_QUALITY_ASSESSMENT:
        # Assess OCR quality (only for fresh results)
        logger.info("Assessing OCR quality...")
        quality_assessment = assess_ocr_quality(ocr_result)
        ocr_result["quality_assessment"] = quality_assessment
    else:
        logger.info("OCR quality assessment disabled by configuration")

    # Re-process weak pages if requested and quality is low
    # IMPORTANT: Skip re-improvement for cached results to avoid redundant API calls
    # Cached results have already been improved (if improvement was enabled when they were created)
    if (
        not from_cache  # Only improve fresh results, not cached ones
        and config.ENABLE_OCR_QUALITY_ASSESSMENT
        and config.ENABLE_OCR_WEAK_PAGE_IMPROVEMENT
        and improve_weak
        and ocr_result.get("pages")
        and quality_assessment
        and quality_assessment.get("weak_page_count", 0) > 0
    ):
        logger.info(
            f"Attempting to improve {quality_assessment['weak_page_count']} weak pages..."
        )
        model = config.get_ocr_model()
        # Note: improve_weak_pages is synchronous
        ocr_result = improve_weak_pages(client, file_path, ocr_result, model)

        # Re-assess quality after improvement
        quality_assessment = assess_ocr_quality(ocr_result)
        ocr_result["quality_assessment"] = quality_assessment
        logger.info(
            f"Quality after improvement: {quality_assessment['quality_score']:.1f}/100"
        )

    # Cache result (only for fresh results)
    if use_cache and not from_cache:
        utils.cache.set(file_path, ocr_result, cache_type="mistral_ocr")

    # Save extracted images (skip for cached results to avoid redundant IO)
    if not from_cache:
        save_extracted_images(ocr_result, file_path)
    else:
        logger.debug("Skipping image extraction for cached result")

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
    from_cache = False
    if use_cache:
        cached_result = utils.cache.get(file_path, cache_type="mistral_ocr")
        if cached_result:
            logger.info(f"Using cached Mistral OCR result for {file_path.name}")
            ocr_result = cached_result
            success = True
            error = None
            from_cache = True  # Mark as from cache to skip re-improvement
        else:
            success, ocr_result, error = process_with_ocr(client, file_path)
    else:
        success, ocr_result, error = process_with_ocr(client, file_path)

    if not success or not ocr_result:
        return False, None, error

    # Process result using common pipeline
    # Pass from_cache flag to skip redundant API calls and IO for cached results
    return _process_ocr_result_pipeline(
        client, file_path, ocr_result, use_cache, improve_weak, from_cache
    )


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
    # Calculate total image count from all pages (images are stored per-page)
    total_image_count = sum(
        len(page.get("images", []))
        for page in ocr_result.get("pages", [])
    )

    # Generate frontmatter
    frontmatter = utils.generate_yaml_frontmatter(
        title=f"OCR: {file_path.stem}",
        file_name=file_path.name,
        conversion_method="Mistral OCR",
        additional_fields={
            "page_count": len(ocr_result.get("pages", [])),
            "image_count": total_image_count,
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


# ============================================================================
# Document QnA (NEW - from updated Mistral docs)
# Query documents using chat.complete with document_url content type
# ============================================================================


def _validate_document_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a document URL to prevent SSRF attacks.

    Rejects non-HTTPS URLs, URLs with embedded credentials, and URLs
    pointing to private/internal networks (IPv4 and IPv6).

    Args:
        url: URL to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    import ipaddress
    import socket
    from urllib.parse import urlparse

    def _is_forbidden_address(addr: Any) -> bool:
        if addr.is_private or addr.is_reserved or addr.is_loopback or addr.is_link_local or addr.is_multicast:
            return True
        # IPv6-mapped IPv4 (e.g. ::ffff:127.0.0.1)
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
            mapped = addr.ipv4_mapped
            if mapped.is_private or mapped.is_loopback or mapped.is_reserved or mapped.is_link_local:
                return True
        return False

    def _validate_ip_str(ip_str: str, source: str) -> Tuple[bool, Optional[str]]:
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            return True, None
        if _is_forbidden_address(addr):
            return False, f"URLs pointing to private/internal networks are not allowed: {source}"
        return True, None

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    # Require HTTPS
    if parsed.scheme not in ("https",):
        return False, f"Only HTTPS URLs are allowed (got {parsed.scheme}://)"

    # Reject embedded credentials (userinfo component)
    if parsed.username or parsed.password:
        return False, "URLs with embedded credentials are not allowed"

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False, "URL must include a hostname"

    blocked_hosts = {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "[::1]",
        "metadata.google.internal",
        "169.254.169.254",  # AWS/cloud metadata endpoint
        "metadata.google.internal.",  # trailing dot variant
    }
    if hostname in blocked_hosts:
        return False, f"URLs pointing to internal hosts are not allowed: {hostname}"

    # Fast path: direct IP literal
    ok, err = _validate_ip_str(hostname.strip("[]"), hostname)
    if not ok:
        return ok, err

    # Defense-in-depth: resolve hostname and reject if any resolved address is internal.
    # If DNS resolution fails locally, defer handling to the upstream request.
    try:
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        resolved_ips = {info[4][0] for info in infos if info and info[4]}
        for ip in resolved_ips:
            ok, err = _validate_ip_str(ip, f"{hostname} -> {ip}")
            if not ok:
                return ok, err
    except socket.gaierror:
        logger.debug(f"Could not resolve hostname during SSRF validation: {hostname}")
    except Exception as e:
        logger.debug(f"DNS resolution check skipped for {hostname}: {e}")

    return True, None


def query_document(
    document_url: str,
    question: str,
    model: Optional[str] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Query a document using Mistral's Document QnA capability.
    
    This combines OCR with chat completion to enable natural language
    interaction with document content. The document is processed and
    you can ask questions about it in natural language.
    
    Args:
        document_url: Public HTTPS URL to the document (PDF, image, etc.)
        question: Natural language question about the document
        model: Optional model override (default: mistral-small-latest)
    
    Returns:
        Tuple of (success, answer, error_message)
    
    Example:
        >>> success, answer, error = query_document(
        ...     "https://arxiv.org/pdf/1805.04770",
        ...     "What is the main contribution of this paper?"
        ... )
        >>> if success:
        ...     print(answer)
    
    Documentation:
        https://docs.mistral.ai/capabilities/document_ai/document_qna
    """
    client = get_mistral_client()
    if client is None:
        return False, None, "Mistral client not available"

    # Validate URL to prevent SSRF
    url_valid, url_error = _validate_document_url(document_url)
    if not url_valid:
        return False, None, f"Invalid document URL: {url_error}"

    if model is None:
        model = config.MISTRAL_DOCUMENT_QNA_MODEL
    
    try:
        logger.info(f"Querying document with question: {question[:50]}...")
        
        # Build message with document_url content type
        messages = []
        if config.MISTRAL_QNA_SYSTEM_PROMPT:
            messages.append({"role": "system", "content": config.MISTRAL_QNA_SYSTEM_PROMPT})
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": question
                    },
                    {
                        "type": "document_url",
                        "document_url": document_url
                    }
                ]
            }
        )
        
        # Get retry config
        retry_config = get_retry_config()
        
        # Call chat.complete with document
        chat_params = {
            "model": model,
            "messages": messages,
        }
        
        if retry_config:
            chat_params["retries"] = retry_config

        if config.MISTRAL_QNA_DOCUMENT_IMAGE_LIMIT > 0:
            chat_params["document_image_limit"] = config.MISTRAL_QNA_DOCUMENT_IMAGE_LIMIT
        if config.MISTRAL_QNA_DOCUMENT_PAGE_LIMIT > 0:
            chat_params["document_page_limit"] = config.MISTRAL_QNA_DOCUMENT_PAGE_LIMIT

        response = client.chat.complete(**chat_params)
        
        if response and response.choices and len(response.choices) > 0:
            answer = response.choices[0].message.content
            logger.info("Document query successful")
            return True, answer, None
        else:
            return False, None, "Empty response from chat completion"
    
    except Exception as e:
        error_msg = f"Error querying document: {e}"
        logger.error(error_msg)
        return False, None, error_msg


def query_document_file(
    file_path: Path,
    question: str,
    model: Optional[str] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Query a local document file using Mistral's Document QnA capability.
    
    Uploads the file to Mistral, gets a signed URL, and then queries it.
    
    Args:
        file_path: Path to local document file
        question: Natural language question about the document
        model: Optional model override (default: mistral-small-latest)
    
    Returns:
        Tuple of (success, answer, error_message)
    """
    client = get_mistral_client()
    if client is None:
        return False, None, "Mistral client not available"

    # Pre-validate file size (Mistral Document QnA limit: 50 MB)
    try:
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > 50:
            return False, None, (
                f"File too large for Document QnA ({file_size_mb:.1f} MB). "
                "Mistral limits documents to 50 MB. Consider splitting the document."
            )
    except OSError as e:
        return False, None, f"Cannot read file: {e}"

    try:
        # Upload file and get signed URL
        signed_url = upload_file_for_ocr(client, file_path)
        if not signed_url:
            return False, None, "Failed to upload file for QnA"

        # Query using the signed URL
        return query_document(signed_url, question, model)

    except Exception as e:
        error_msg = f"Error querying document file: {e}"
        logger.error(error_msg)
        return False, None, error_msg


# ============================================================================
# Batch OCR Processing (NEW - from updated Mistral docs)
# Process multiple documents at 50% cost reduction using Batch API
# ============================================================================


def create_batch_ocr_file(
    file_paths: List[Path],
    output_file: Path,
    model: Optional[str] = None,
    include_image_base64: bool = True,
) -> Tuple[bool, Optional[Path], Optional[str]]:
    """
    Create a JSONL batch file for OCR processing.
    
    This creates a file in the format required by Mistral's Batch API
    for processing multiple documents at 50% reduced cost.
    
    Args:
        file_paths: List of file paths to process
        output_file: Path where to save the JSONL batch file
        model: OCR model to use (default: mistral-ocr-latest)
        include_image_base64: Whether to include image base64 in results
    
    Returns:
        Tuple of (success, batch_file_path, error_message)
    
    Example:
        >>> success, batch_file, error = create_batch_ocr_file(
        ...     [Path("doc1.pdf"), Path("doc2.pdf")],
        ...     Path("batch_input.jsonl")
        ... )
    
    Documentation:
        https://docs.mistral.ai/capabilities/batch/
    """
    client = get_mistral_client()
    if client is None:
        return False, None, "Mistral client not available"
    
    if model is None:
        model = config.get_ocr_model()
    
    try:
        logger.info(f"Creating batch OCR file for {len(file_paths)} documents...")
        
        entries = []
        
        for idx, file_path in enumerate(file_paths):
            # Upload file and get signed URL
            signed_url = upload_file_for_ocr(client, file_path)
            if not signed_url:
                logger.warning(f"Failed to upload {file_path.name}, skipping...")
                continue
            
            # Determine document type
            ext = file_path.suffix.lower().lstrip(".")
            is_image = ext in config.IMAGE_EXTENSIONS
            
            # Create batch entry
            if is_image:
                document = {
                    "type": "image_url",
                    "image_url": signed_url
                }
            else:
                document = {
                    "type": "document_url",
                    "document_url": signed_url
                }
            
            entry = {
                "custom_id": f"{idx}_{file_path.stem}",
                "body": {
                    "model": model,
                    "document": document,
                    "include_image_base64": include_image_base64
                }
            }

            # Include structured annotation formats if enabled
            bbox_format = get_bbox_annotation_format()
            doc_format = get_document_annotation_format()
            if bbox_format is not None:
                entry["body"]["bbox_annotation_format"] = bbox_format
            if doc_format is not None:
                entry["body"]["document_annotation_format"] = doc_format
            if config.MISTRAL_DOCUMENT_ANNOTATION_PROMPT:
                entry["body"]["document_annotation_prompt"] = config.MISTRAL_DOCUMENT_ANNOTATION_PROMPT

            entries.append(entry)
            logger.debug(f"Added {file_path.name} to batch (id: {entry['custom_id']})")
        
        if not entries:
            return False, None, "No files could be prepared for batch processing"
        
        # Write JSONL file
        with open(output_file, 'w', encoding='utf-8') as f:
            for entry in entries:
                f.write(json.dumps(entry) + '\n')
        
        logger.info(f"Created batch file with {len(entries)} entries: {output_file}")
        return True, output_file, None
    
    except Exception as e:
        error_msg = f"Error creating batch OCR file: {e}"
        logger.error(error_msg)
        return False, None, error_msg


def submit_batch_ocr_job(
    batch_file_path: Path,
    model: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Submit a batch OCR job to Mistral's Batch API.
    
    This submits the batch file for processing and returns a job ID
    that can be used to monitor progress and retrieve results.
    
    Args:
        batch_file_path: Path to the JSONL batch file
        model: OCR model to use (default: mistral-ocr-latest)
        metadata: Optional metadata dictionary for the job
    
    Returns:
        Tuple of (success, job_id, error_message)
    
    Example:
        >>> success, job_id, error = submit_batch_ocr_job(
        ...     Path("batch_input.jsonl"),
        ...     metadata={"job_type": "document_processing"}
        ... )
        >>> if success:
        ...     print(f"Job submitted: {job_id}")
    """
    client = get_mistral_client()
    if client is None:
        return False, None, "Mistral client not available"
    
    if model is None:
        model = config.get_ocr_model()
    
    try:
        logger.info(f"Uploading batch file: {batch_file_path.name}")
        
        # Upload the batch file (read content as bytes, consistent with OCR upload)
        with open(batch_file_path, "rb") as f:
            file_content = f.read()

        batch_data = client.files.upload(
            file={
                "file_name": batch_file_path.name,
                "content": file_content,
            },
            purpose="batch"
        )
        
        logger.info(f"Batch file uploaded: {batch_data.id}")
        
        # Create the batch job
        job_params = {
            "input_files": [batch_data.id],
            "model": model,
            "endpoint": "/v1/ocr",
        }
        
        if metadata:
            job_params["metadata"] = metadata

        if config.MISTRAL_BATCH_TIMEOUT_HOURS != 24:  # Only pass if non-default
            job_params["timeout_hours"] = config.MISTRAL_BATCH_TIMEOUT_HOURS

        created_job = client.batch.jobs.create(**job_params)
        
        logger.info(f"Batch job created: {created_job.id}")
        return True, created_job.id, None
    
    except Exception as e:
        error_msg = f"Error submitting batch OCR job: {e}"
        logger.error(error_msg)
        return False, None, error_msg


def get_batch_job_status(job_id: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Get the status of a batch OCR job.
    
    Args:
        job_id: The batch job ID
    
    Returns:
        Tuple of (success, status_dict, error_message)
        
        status_dict contains:
        - status: Job status (QUEUED, RUNNING, SUCCESS, FAILED, etc.)
        - total_requests: Total number of requests in batch
        - succeeded_requests: Number of successful requests
        - failed_requests: Number of failed requests
        - output_file: Output file ID (when complete)
    """
    client = get_mistral_client()
    if client is None:
        return False, None, "Mistral client not available"
    
    try:
        job = client.batch.jobs.get(job_id=job_id)
        
        status = {
            "status": job.status,
            "total_requests": job.total_requests,
            "succeeded_requests": job.succeeded_requests,
            "failed_requests": job.failed_requests,
            "output_file": getattr(job, 'output_file', None),
            "error_file": getattr(job, 'error_file', None),
        }
        
        # Calculate progress percentage
        if job.total_requests > 0:
            completed = job.succeeded_requests + job.failed_requests
            status["progress_percent"] = round(
                (completed / job.total_requests) * 100, 2
            )
        else:
            status["progress_percent"] = 0
        
        logger.info(
            f"Batch job {job_id}: {status['status']} - "
            f"{status['progress_percent']}% complete"
        )
        
        return True, status, None
    
    except Exception as e:
        error_msg = f"Error getting batch job status: {e}"
        logger.error(error_msg)
        return False, None, error_msg


def download_batch_results(
    job_id: str,
    output_dir: Optional[Path] = None,
) -> Tuple[bool, Optional[Path], Optional[str]]:
    """
    Download results from a completed batch OCR job.
    
    Args:
        job_id: The batch job ID
        output_dir: Directory to save results (default: output_md/)
    
    Returns:
        Tuple of (success, results_file_path, error_message)
    """
    client = get_mistral_client()
    if client is None:
        return False, None, "Mistral client not available"
    
    if output_dir is None:
        output_dir = config.OUTPUT_MD_DIR
    
    try:
        # Get job status to get output file ID
        job = client.batch.jobs.get(job_id=job_id)
        
        if job.status not in ["SUCCESS", "FAILED", "TIMEOUT_EXCEEDED", "CANCELLED"]:
            return False, None, f"Job not complete. Status: {job.status}"
        
        if not job.output_file:
            return False, None, "No output file available"
        
        # Download the output file
        logger.info(f"Downloading batch results for job {job_id}...")
        
        output_path = output_dir / f"batch_ocr_results_{job_id}.jsonl"
        
        # Download file content
        file_content = client.files.download(file_id=job.output_file)
        
        with open(output_path, 'wb') as f:
            f.write(file_content)
        
        logger.info(f"Batch results saved to: {output_path}")
        return True, output_path, None
    
    except Exception as e:
        error_msg = f"Error downloading batch results: {e}"
        logger.error(error_msg)
        return False, None, error_msg


def list_batch_jobs(
    status: Optional[str] = None,
    page: int = 0,
    page_size: int = 100,
) -> Tuple[bool, Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    List batch OCR jobs with optional status filtering and pagination.

    Args:
        status: Optional filter by status (QUEUED, RUNNING, SUCCESS, FAILED, etc.)
        page: Page number (0-indexed) for pagination
        page_size: Number of results per page (default: 100)

    Returns:
        Tuple of (success, jobs_list, error_message)
    """
    client = get_mistral_client()
    if client is None:
        return False, None, "Mistral client not available"

    try:
        list_kwargs: Dict[str, Any] = {}
        if page > 0:
            list_kwargs["page"] = page
        if page_size != 100:
            list_kwargs["page_size"] = page_size

        jobs_response = client.batch.jobs.list(**list_kwargs)
        jobs_data = (jobs_response.data or []) if hasattr(jobs_response, 'data') else jobs_response

        jobs_list = []
        for job in jobs_data:
            job_info = {
                "id": job.id,
                "status": job.status,
                "model": getattr(job, 'model', None),
                "total_requests": getattr(job, 'total_requests', 0),
                "succeeded_requests": getattr(job, 'succeeded_requests', 0),
                "failed_requests": getattr(job, 'failed_requests', 0),
                "created_at": str(getattr(job, 'created_at', '')),
            }

            if status is None or job_info["status"] == status:
                jobs_list.append(job_info)

        logger.info(f"Found {len(jobs_list)} batch jobs")
        return True, jobs_list, None

    except Exception as e:
        error_msg = f"Error listing batch jobs: {e}"
        logger.error(error_msg)
        return False, None, error_msg


def cancel_batch_job(job_id: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Cancel a running batch OCR job.

    Args:
        job_id: The batch job ID to cancel

    Returns:
        Tuple of (success, status, error_message)
    """
    client = get_mistral_client()
    if client is None:
        return False, None, "Mistral client not available"

    try:
        job = client.batch.jobs.cancel(job_id=job_id)
        logger.info(f"Batch job {job_id} cancellation requested")
        return True, job.status, None

    except Exception as e:
        error_msg = f"Error cancelling batch job: {e}"
        logger.error(error_msg)
        return False, None, error_msg


def download_batch_errors(
    job_id: str,
    output_dir: Optional[Path] = None,
) -> Tuple[bool, Optional[Path], Optional[str]]:
    """
    Download error file from a batch OCR job.

    Args:
        job_id: The batch job ID
        output_dir: Directory to save errors (default: output_md/)

    Returns:
        Tuple of (success, error_file_path, error_message)
    """
    client = get_mistral_client()
    if client is None:
        return False, None, "Mistral client not available"

    if output_dir is None:
        output_dir = config.OUTPUT_MD_DIR

    try:
        job = client.batch.jobs.get(job_id=job_id)

        if not getattr(job, 'error_file', None):
            return False, None, "No error file available for this job"

        logger.info(f"Downloading batch errors for job {job_id}...")

        output_path = output_dir / f"batch_ocr_errors_{job_id}.jsonl"
        file_content = client.files.download(file_id=job.error_file)

        with open(output_path, 'wb') as f:
            f.write(file_content)

        logger.info(f"Batch errors saved to: {output_path}")
        return True, output_path, None

    except Exception as e:
        error_msg = f"Error downloading batch errors: {e}"
        logger.error(error_msg)
        return False, None, error_msg
