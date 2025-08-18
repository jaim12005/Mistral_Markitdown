import os
import sys
import traceback
import time
from pathlib import Path
import shutil
from datetime import datetime

try:
    import pandas as pd
except Exception:
    pd = None
try:
    import pdfplumber
except Exception:
    pdfplumber = None
try:
    import camelot
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
    INPUT_DIR, OUT_MD, OUT_TXT, OUT_IMG, CACHE_DIR, LOG_DIR, BATCH_SIZE,
    MISTRAL_API_KEY, MISTRAL_MODEL, MISTRAL_INCLUDE_IMAGES, MISTRAL_INCLUDE_IMAGE_ANNOTATIONS,
    POPPLER_PATH,
    MARKITDOWN_USE_LLM, MARKITDOWN_LLM_MODEL, MARKITDOWN_LLM_KEY,
    AZURE_DOC_INTEL_ENDPOINT, AZURE_DOC_INTEL_KEY, MAX_RETRIES, CACHE_DURATION_HOURS
)
from utils import (
    logline, md_to_txt, have, write_text, ProcessingResult, get_metadata_tracker,
    get_enhanced_file_strategy, analyze_file_complexity,
    ConcurrentProcessor, ErrorRecoveryManager, get_cache,
    create_file_processor_function
)
from local_converter import run_markitdown_enhanced, extract_tables_to_markdown, pdfs_to_images
from mistral_converter import mistral_ocr_file_enhanced, process_mistral_response_enhanced


def convert_local_only():
    print("\n=== Local conversion (MarkItDown + tables) ===")
    files = [p for p in sorted(INPUT_DIR.iterdir()) if p.is_file()]
    if not files:
        print("No input files found.")
        return

    metadata_tracker = get_metadata_tracker()
    ok_count = 0
    for f in files:
        base = f.stem
        print(f"Processing: {f.name}")
        start_time = time.time()
        produced: list[Path] = []
        strategy_desc = "Markitdown + Local Tables"
        error_msg = ""
        try:
            md_main = OUT_MD / f"{base}.md"
            ok_md = run_markitdown_enhanced(f, md_main)
            if ok_md:
                produced.append(md_main)
                img_dir = OUT_IMG / f"{base}_markitdown"
                if img_dir.exists() and any(img_dir.iterdir()):
                    print(f"  -> Extracted images to output_images/{img_dir.name}/")
            if f.suffix.lower() == ".pdf":
                try:
                    extracted_tables = extract_tables_to_markdown(f, base)
                    produced += extracted_tables
                    if extracted_tables:
                        logline(f"  -> wrote {len(extracted_tables)} table file(s).")
                except Exception as e:
                    print(f"  -> Local table extraction error: {e}")
                    traceback.print_exc()
            for md in produced[:]:
                txt = OUT_TXT / (md.stem + ".txt")
                md_to_txt(md, txt)
                if txt.exists():
                    produced.append(txt)
            if produced:
                ok_count += 1
        except Exception as e:
            error_msg = f"Processing error: {e}"
            print(f"  -> Processing error: {e}")
            traceback.print_exc()
        processing_time = time.time() - start_time
        result = ProcessingResult(
            file_path=f,
            success=len(produced) > 0,
            output_files=produced,
            processing_time=processing_time,
            strategy_used=strategy_desc,
            error_message=error_msg.strip()
        )
        metadata_tracker.track_file_processing(f, result)
    metadata_tracker.finalize_session()
    print("\n=== Summary ===")
    print(f"Successfully processed files: {ok_count}")


def convert_mistral_only():
    print("\n=== OCR conversion (Mistral only) ===")
    supported_exts = (".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".docx", ".pptx")
    files = [p for p in sorted(INPUT_DIR.iterdir()) if p.is_file() and p.suffix.lower() in supported_exts]
    if not files:
        print("No suitable files found in input.")
        if not MISTRAL_API_KEY:
            logline("-> ERROR: MISTRAL_API_KEY not set.")
        return

    metadata_tracker = get_metadata_tracker()
    ok_count = 0
    for doc in files:
        base = doc.stem
        print(f"Processing: {doc.name}")
        start_time = time.time()
        produced: list[Path] = []
        strategy_desc = "Mistral OCR"
        error_msg = ""
        try:
            resp = mistral_ocr_file_enhanced(doc, base, use_cache=True)
            if not resp:
                error_msg = "Mistral OCR API call failed or returned empty."
            else:
                out_md = process_mistral_response_enhanced(resp, base, doc)
                if out_md:
                    produced.append(out_md)
                    print(f"  -> wrote: {out_md.relative_to(OUT_MD.parent)}")
                    txt = OUT_TXT / (out_md.stem + ".txt")
                    md_to_txt(out_md, txt)
                    if txt.exists():
                        produced.append(txt)
                    ok_count += 1
                else:
                    error_msg = "Failed to process Mistral OCR response."
        except Exception as e:
            error_msg = f"Processing error: {e}"
            print(f"  -> Processing error: {e}")
            traceback.print_exc()
        processing_time = time.time() - start_time
        result = ProcessingResult(
            file_path=doc,
            success=len(produced) > 0,
            output_files=produced,
            processing_time=processing_time,
            strategy_used=strategy_desc,
            error_message=error_msg
        )
        metadata_tracker.track_file_processing(doc, result)
    metadata_tracker.finalize_session()
    print("\n=== Summary ===")
    print(f"Successfully processed files: {ok_count}")


def convert_transcription_only():
    """New mode for audio/video transcription."""
    print("\n=== Transcription Mode (Markitdown) ===")
    supported_exts = {'.mp3', '.wav', '.m4a', '.flac', '.mp4', '.avi', '.mov', '.mkv', '.url'}
    files = [p for p in sorted(INPUT_DIR.iterdir()) if p.is_file() and p.suffix.lower() in supported_exts]

    if not files:
        print("No suitable audio, video, or .url files found for transcription.")
        return

    metadata_tracker = get_metadata_tracker()
    ok_count = 0
    for f in files:
        # For .url files, check if they are YouTube links
        if f.suffix.lower() == '.url':
            try:
                content = f.read_text(encoding='utf-8').strip()
                if not ('youtube.com' in content or 'youtu.be' in content):
                    print(f"Skipping non-YouTube .url file: {f.name}")
                    continue
            except Exception as e:
                print(f"Skipping unreadable .url file: {f.name} ({e})")
                continue

        base = f.stem
        print(f"Processing for transcription: {f.name}")
        start_time = time.time()
        produced: list[Path] = []
        strategy_desc = "Markitdown Transcription"
        error_msg = ""
        try:
            md_main = OUT_MD / f"{base}_transcription.md"
            ok_md = run_markitdown_enhanced(f, md_main)
            if ok_md:
                produced.append(md_main)
                print(f"  -> Transcription successful: {md_main.name}")

            for md in produced[:]:
                txt = OUT_TXT / (md.stem + ".txt")
                md_to_txt(md, txt)
                if txt.exists():
                    produced.append(txt)
            if produced:
                ok_count += 1
        except Exception as e:
            error_msg = f"Processing error: {e}"
            print(f"  -> Processing error: {e}")
            traceback.print_exc()

        processing_time = time.time() - start_time
        result = ProcessingResult(
            file_path=f,
            success=len(produced) > 0,
            output_files=produced,
            processing_time=processing_time,
            strategy_used=strategy_desc,
            error_message=error_msg.strip()
        )
        metadata_tracker.track_file_processing(f, result)

    metadata_tracker.finalize_session()
    print("\n=== Summary ===")
    print(f"Successfully transcribed files: {ok_count}")


def _run_hybrid_markitdown(f: Path, base: str, md_main: Path) -> tuple[bool, list[Path], list[Path]]:
    produced = []
    table_files = []
    print(f"   🔄 Running Markitdown...")
    ok_md = run_markitdown_enhanced(f, md_main)
    if ok_md:
        produced.append(md_main)
        print(f"   ✅ Markitdown successful")
        img_dir = OUT_IMG / f"{base}_markitdown"
        if img_dir.exists() and any(img_dir.iterdir()):
            print(f"   🖼️ Extracted images (Markitdown)")
        if f.suffix.lower() == '.pdf':
            try:
                table_files = extract_tables_to_markdown(f, base)
                produced += table_files
                if table_files:
                    print(f"   📊 Extracted {len(table_files)} table file(s)")
            except Exception as e:
                logline(f"   ⚠️  Table extraction error: {e}")
    return ok_md, produced, table_files

def _run_hybrid_ocr(f: Path, base: str) -> tuple[Path | None, list[Path]]:
    produced = []
    ocr_md_path = None
    print(f"   🔄 Running Mistral OCR...")
    resp = mistral_ocr_file_enhanced(f, base, use_cache=True)
    if resp:
        ocr_md_path = process_mistral_response_enhanced(resp, base, f)
        if ocr_md_path:
            produced.append(ocr_md_path)
            print(f"   ✅ OCR successful")
        else:
            print(f"   ⚠️  OCR response processing failed")
    else:
        print(f"   ❌ OCR failed")
    return ocr_md_path, produced

def _combine_hybrid_results(base: str, md_main: Path, table_files: list[Path], ocr_md: Path | None, strategy, complexity) -> Path | None:
    combined_path = OUT_MD / f"{base}_combined.md"
    print(f"   🔧 Creating enhanced combined output...")
    try:
        markitdown_content = md_main.read_text(encoding="utf-8")
        combined = f"# Enhanced Processing Results: {base}\n\n"
        combined += f"**Processing Strategy**: {strategy.description}\n"
        combined += f"**File Size**: {complexity['size_mb']:.1f}MB\n"
        combined += f"**Processed**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        combined += f"**Methods Used**: {'Markitdown' if strategy.use_markitdown else ''}{'+ OCR' if strategy.use_ocr else ''}\n"
        combined += f"**Benefits**: {', '.join(strategy.benefits)}\n\n"
        combined += "---\n\n"

        def strip_headers(content: str) -> str:
            lines = content.strip().split('\n')
            if not lines: return ""
            if lines[0] == '---':
                try:
                    end_yaml = lines.index('---', 1)
                    lines = lines[end_yaml+1:]
                except ValueError: pass
            lines = [line for line in lines if line.strip()]
            if lines and lines[0].startswith('# '):
                return '\n'.join(lines[1:]).strip()
            return '\n'.join(lines).strip()

        combined += "## 📝 Primary Content (Markitdown)\n\n"
        combined += strip_headers(markitdown_content)

        if table_files:
            combined += "\n\n---\n\n## 📊 Extracted Tables (Local Analysis)\n\n"
            for i, table_file in enumerate(table_files):
                combined += f"### Table {i+1}: {table_file.name}\n\n"
                try:
                    combined += table_file.read_text(encoding="utf-8") + "\n\n"
                except Exception as e:
                    combined += f"*Error loading table: {e}*\n\n"
        if ocr_md:
            combined += "\n\n---\n\n## 🔍 Enhanced OCR Analysis (Mistral)\n\n"
            combined += strip_headers(ocr_md.read_text(encoding="utf-8"))

        write_text(combined_path, combined)
        print(f"   ✅ Combined output created")
        return combined_path
    except Exception as e:
        print(f"   ❌ Failed to create combined output: {e}")
        return None

def convert_hybrid_pipeline():
    print("\n=== Enhanced Hybrid Processing (Markitdown + Mistral OCR) ===")
    files = [p for p in sorted(INPUT_DIR.iterdir()) if p.is_file()]
    if not files:
        print("No input files found.")
        return

    metadata_tracker = get_metadata_tracker()
    ok_count = 0
    total_processing_time = 0
    print(f"\nAnalyzing {len(files)} files for optimal processing...")

    for f in files:
        strategy = get_enhanced_file_strategy(f)
        complexity = analyze_file_complexity(f)
        base = f.stem

        print(f"\n📄 Processing: {f.name}")
        print(f"   📊 Size: {complexity['size_mb']:.1f}MB ({complexity['size_category']})")
        print(f"   🎯 Strategy: {strategy.description}")
        print(f"   ⏱️  Estimated time: {complexity['estimated_processing_time']}")
        print(f"   Methods: {'Markitdown' if strategy.use_markitdown else ''}{'+ OCR' if strategy.use_ocr else ''}")

        start_time = time.time()
        produced: list[Path] = []
        error_msg = ""

        try:
            md_main_path = OUT_MD / f"{base}.md"
            ok_md, md_produced, table_files = False, [], []
            if strategy.use_markitdown:
                ok_md, md_produced, table_files = _run_hybrid_markitdown(f, base, md_main_path)
                produced.extend(md_produced)

            ocr_md_path, ocr_produced = None, []
            if strategy.use_ocr and MISTRAL_API_KEY:
                ocr_md_path, ocr_produced = _run_hybrid_ocr(f, base)
                produced.extend(ocr_produced)
            elif strategy.use_ocr:
                print(f"   ⚠️  OCR recommended but MISTRAL_API_KEY not configured")

            if ok_md and (ocr_md_path or table_files):
                combined_path = _combine_hybrid_results(base, md_main_path, table_files, ocr_md_path, strategy, complexity)
                if combined_path:
                    produced.append(combined_path)

            for md_file in produced[:]:
                if md_file.suffix == '.md':
                    txt_path = OUT_TXT / f"{md_file.stem}.txt"
                    md_to_txt(md_file, txt_path)
                    if txt_path.exists():
                        produced.append(txt_path)

        except Exception as e:
            print(f"   ❌ Exception during processing: {e}")
            error_msg = str(e)
            traceback.print_exc()

        processing_time = time.time() - start_time
        total_processing_time += processing_time

        result = ProcessingResult(
            file_path=f,
            success=len(produced) > 0,
            output_files=produced,
            processing_time=processing_time,
            strategy_used=strategy.description,
            error_message=error_msg
        )
        metadata_tracker.track_file_processing(f, result)

        if produced:
            ok_count += 1
            print(f"   ✅ Generated {len(produced)} output file(s) in {processing_time:.1f}s")
        else:
            print(f"   ❌ No output generated")

    metadata_tracker.finalize_session()
    print("\n" + "="*60)
    print("📈 PROCESSING SUMMARY")
    print("="*60)
    print(f"✅ Successfully processed: {ok_count}/{len(files)} files")
    print(f"⏱️  Total processing time: {total_processing_time:.1f}s")
    if files:
        print(f"⚡ Average time per file: {total_processing_time/len(files):.1f}s")
    print(f"📁 Output locations:")
    print(f"   • Markdown: {OUT_MD}/")
    print(f"   • Text: {OUT_TXT}/")
    if MISTRAL_INCLUDE_IMAGES:
        print(f"   • Images: {OUT_IMG}/")
    print("="*60)


def batch_process_directory():
    print("\n=== Batch Processing Mode ===")
    files = list(INPUT_DIR.iterdir())
    if not files:
        print("No files to process.")
        return
    file_groups = {}
    for f in files:
        if f.is_file():
            ext = f.suffix.lower()
            if ext not in file_groups:
                file_groups[ext] = []
            file_groups[ext].append(f)
    print(f"Found {len(files)} files in {len(file_groups)} format groups")
    for ext, group_files in file_groups.items():
        print(f"\nProcessing {len(group_files)} {ext} files...")
        for i in range(0, len(group_files), BATCH_SIZE):
            batch = group_files[i:i+BATCH_SIZE]
            print(f"  Batch {i//BATCH_SIZE + 1}: Processing {len(batch)} files")
            for f in batch:
                base = f.stem
                try:
                    if ext in {'.jpg', '.jpeg', '.png', '.tiff', '.tif'}:
                        if MISTRAL_API_KEY:
                            resp = mistral_ocr_file_enhanced(f, base, use_cache=True)
                            if resp:
                                process_mistral_response_enhanced(resp, base, f)
                    else:
                        md_path = OUT_MD / f"{base}.md"
                        run_markitdown_enhanced(f, md_path)
                    print(f"    ✓ {f.name}")
                except Exception as e:
                    print(f"    ✗ {f.name}: {e}")
    print("\n=== Batch processing complete ===")


def print_env_summary():
    print("--- Environment Status ---")
    if MarkItDown is not None:
        print("[OK] Markitdown Python API available")
        if MARKITDOWN_USE_LLM and MARKITDOWN_LLM_KEY:
            print(f"  -> LLM support enabled ({MARKITDOWN_LLM_MODEL})")
        if AZURE_DOC_INTEL_ENDPOINT and AZURE_DOC_INTEL_KEY:
            print(f"  -> Azure Document Intelligence enabled")
    elif shutil.which("markitdown"):
        print("[OK] Markitdown CLI available (Python API not found)")
    else:
        print("[MISSING] Markitdown not found - install with: pip install markitdown[all]")
    if pd is not None and pdfplumber is not None:
        print("[OK] Table extraction enabled (pdfplumber + pandas)")
    else:
        missing = []
        if pd is None: missing.append("pandas")
        if pdfplumber is None: missing.append("pdfplumber")
        print(f"[WARN] Table extraction limited (missing: {', '.join(missing)})")
    try:
        import tabulate as _tab
        print("[OK] Enhanced table formatting available (tabulate)")
    except Exception:
        pass
    if camelot is not None:
        if have("gswin64c.exe") or have("gswin32c.exe") or have("gs"):
            print("[OK] Camelot with Ghostscript (best table extraction)")
        else:
            print("[WARN] Camelot without Ghostscript (limited mode)")
    if MISTRAL_API_KEY:
        print(f"[OK] Mistral OCR configured")
        print(f"  -> Model: {MISTRAL_MODEL}")
        print(f"  -> Image extraction: {'Enabled' if MISTRAL_INCLUDE_IMAGES else 'Disabled'}")
        if MISTRAL_INCLUDE_IMAGES:
            print(f"  -> Image annotations (AI): {'Enabled' if MISTRAL_INCLUDE_IMAGE_ANNOTATIONS else 'Disabled'}")
        print(f"  -> Caching: Enabled (IntelligentCache, {CACHE_DURATION_HOURS}h)")
        print(f"  -> Retry: SDK managed + Upload retries")
    else:
        print("[WARN] Mistral OCR not configured (set MISTRAL_API_KEY in .env)")
    if convert_from_path is not None:
        if POPPLER_PATH or have("pdftoppm"):
            print("[OK] PDF to image conversion available")
        else:
            print("[WARN] PDF to image needs Poppler (set POPPLER_PATH)")
    print(f"\n--- Performance Settings ---")
    print(f"Batch size: {BATCH_SIZE} files")
    from config import MISTRAL_TIMEOUT
    print(f"HTTP timeout: {MISTRAL_TIMEOUT}s")
    print(f"Max retries: {MAX_RETRIES}")
    print(f"\n--- Directories ---")
    print(f"Input:    {INPUT_DIR}")
    print(f"Output:   {OUT_MD}")
    print(f"Text:     {OUT_TXT}")
    print(f"Images:   {OUT_IMG}")
    print(f"Cache:    {CACHE_DIR}")
    print(f"Logs:     {LOG_DIR}")


def menu_loop():
    while True:
        print("\n" + "="*60)
        print("    ENHANCED DOCUMENT CONVERTER v2.1")
        print("    Powered by Microsoft Markitdown & Mistral OCR")
        print("="*60)
        print("Choose conversion mode:")
        print()
        print("  1) HYBRID Mode (Intelligent Processing)")
        print("     -> Smart file analysis + optimal method selection")
        print()
        print("  2) ENHANCED BATCH (Maximum Performance)")
        print("     -> Concurrent processing + caching + metadata")
        print()
        print("  3) Markitdown Only (Fast, Local)")
        print("     -> Best for Office docs, HTML, structured files")
        print()
        print("  4) Mistral OCR Only (High Accuracy)")
        print("     -> Best for images, scanned PDFs, complex layouts")
        print()
        print("  5) Transcription Only (Audio/Video)")
        print("     -> Transcribe audio, video, and YouTube URLs")
        print()
        print("  6) Standard Batch Process")
        print("     -> Process all files with basic settings")
        print()
        print("  7) Convert PDFs to Images")
        print("     -> Extract pages as PNG files")
        print()
        print("  8) Show System Status")
        print("     -> Cache stats, performance metrics, recommendations")
        print()
        print("  Q) Quit")
        print("="*60)
        try:
            choice = input("Enter your choice: ").strip().lower()
        except EOFError:
            print("\nExiting.")
            break
        if choice == "1":
            convert_hybrid_pipeline()
        elif choice == "2":
            convert_enhanced_batch()
        elif choice == "3":
            convert_local_only()
        elif choice == "4":
            convert_mistral_only()
        elif choice == "5":
            convert_transcription_only()
        elif choice == "6":
            batch_process_directory()
        elif choice == "7":
            pdfs_to_images()
        elif choice == "8":
            show_system_status()
        elif choice in ("q", "quit", "exit"):
            print("\nThank you for using Enhanced Document Converter v2.1!")
            break
        else:
            print("Invalid choice. Please try again.")


def print_banner():
    from datetime import datetime
    from config import APP_ROOT
    print("=" * 60)
    print("   ENHANCED DOCUMENT CONVERTER v2.1")
    print("   Powered by Microsoft Markitdown & Mistral OCR")
    print("=" * 60)
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Working directory: {APP_ROOT}")


def convert_enhanced_batch():
    print("\n=== ENHANCED BATCH PROCESSING ===")
    print("🚀 Using all optimization features for maximum performance")
    files = [p for p in sorted(INPUT_DIR.iterdir()) if p.is_file()]
    if not files:
        print("No input files found.")
        return
    from utils import (
        ConcurrentProcessor, ErrorRecoveryManager, get_cache, get_metadata_tracker,
        create_file_processor_function, get_enhanced_file_strategy, analyze_file_complexity
    )
    cache = get_cache()
    metadata_tracker = get_metadata_tracker()
    processor = ConcurrentProcessor(max_workers=min(os.cpu_count() or 4, 8), rate_limit_delay=1.0)
    error_manager = ErrorRecoveryManager()
    print(f"\n📊 PROCESSING ANALYSIS")
    print("="*50)
    analysis_results = {}
    total_estimated_time = 0
    for f in files:
        strategy = get_enhanced_file_strategy(f)
        complexity = analyze_file_complexity(f)
        analysis_results[f] = (strategy, complexity)
        time_str = complexity['estimated_processing_time']
        if time_str.endswith('s'):
            total_estimated_time += int(time_str[:-1])
    print(f"📁 Files to process: {len(files)}")
    print(f"⏱️  Estimated total time: {total_estimated_time}s ({total_estimated_time//60}m {total_estimated_time%60}s)")
    strategy_counts = {}
    for strategy, _ in analysis_results.values():
        desc = strategy.description
        strategy_counts[desc] = strategy_counts.get(desc, 0) + 1
    print(f"🎯 Processing strategies:")
    for desc, count in strategy_counts.items():
        print(f"   • {desc}: {count} files")
    cache_stats = cache.get_cache_stats()
    if cache_stats.get('total_entries', 0) > 0:
        print(f"💾 Cache: {cache_stats['total_entries']} entries, {cache_stats['size_mb']:.1f}MB")
        print(f"   Hit rate: {cache_stats.get('hit_rate', 0):.1%}")
    recommendations = metadata_tracker.get_recommendations()
    if recommendations:
        print(f"\n💡 RECOMMENDATIONS")
        for key, rec in recommendations.items():
            print(f"   • {rec}")
    print("\n" + "="*50)
    def progress_callback(completed: int, total: int):
        percentage = (completed / total) * 100
        print(f"\r🔄 Progress: {completed}/{total} ({percentage:.1f}%) ", end="", flush=True)
    processor_func = create_file_processor_function(use_enhanced_strategy=True)
    print(f"\n🚀 Starting enhanced batch processing (Workers: {processor.max_workers})...")
    start_time = time.time()
    results: list[ProcessingResult] = []
    try:
        results = processor.process_files_concurrent(
            files,
            processor_func,
            progress_callback
        )
        processing_time = time.time() - start_time
        print(f"\n\n✅ Processing completed in {processing_time:.1f}s")
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        print(f"\n📈 ENHANCED PROCESSING RESULTS")
        print("="*60)
        print(f"✅ Successful: {len(successful)}/{len(results)} ({len(successful)/len(results):.1%})")
        print(f"❌ Failed: {len(failed)}")
        print(f"⚡ Average time per file: {processing_time/len(files):.1f}s")
        for result in results:
            metadata_tracker.track_file_processing(result.file_path, result)
        method_counts = {}
        total_outputs = 0
        for result in successful:
            method = result.strategy_used
            method_counts[method] = method_counts.get(method, 0) + 1
            total_outputs += len(result.output_files)
        print(f"\n🔧 Methods used:")
        for method, count in method_counts.items():
            print(f"   • {method}: {count} files")
        print(f"\n📁 Output summary:")
        print(f"   • Total output files: {total_outputs}")
        print(f"   • Markdown files: {OUT_MD}/")
        print(f"   • Text files: {OUT_TXT}/")
        if MISTRAL_INCLUDE_IMAGES:
            print(f"   • Extracted images: {OUT_IMG}/")
        if failed:
            print(f"\n⚠️  Error analysis:")
            error_types = {}
            for result in failed:
                error_type = result.error_message.split(':')[0] if result.error_message else "Unknown"
                error_types[error_type] = error_types.get(error_type, 0) + 1
            for error_type, count in error_types.items():
                print(f"   • {error_type}: {count} files")
        processor_stats = processor.get_processing_stats()
        print(f"\n📊 Performance metrics:")
        print(f"   • API calls made: {processor_stats.get('api_calls', 0)}")
        print(f"   • Cache utilization: {cache.get_cache_stats().get('hit_rate', 0):.1%}")
        print(f"   • Processing efficiency: {processor_stats.get('success_rate', 0):.1%}")
        cache.cleanup_old_entries()
        metadata_tracker.add_performance_metric('total_processing_time', processing_time)
        metadata_tracker.add_performance_metric('files_per_second', len(files) / processing_time)
        metadata_tracker.add_performance_metric('concurrent_workers', processor.max_workers)
        metadata_tracker.finalize_session()
        print(f"\n💾 Session data saved for future optimization")
        print("="*60)
    except KeyboardInterrupt:
        print(f"\n\n⚠️  Processing interrupted by user")
        completed_count = len([r for r in results if hasattr(r, 'success')])
        metadata_tracker.log_error("Processing interrupted by user", {'files_completed': completed_count})
        metadata_tracker.finalize_session()
    except Exception as e:
        print(f"\n\n❌ Processing failed: {e}")
        metadata_tracker.log_error(f"Batch processing failed: {e}")
        metadata_tracker.finalize_session()
        raise


def show_system_status():
    print("\n" + "="*60)
    print("📊 ENHANCED DOCUMENT CONVERTER - SYSTEM STATUS")
    print("="*60)
    try:
        from utils import get_cache, get_metadata_tracker
        from config import MISTRAL_API_KEY, MARKITDOWN_USE_LLM, AZURE_DOC_INTEL_ENDPOINT
        print("\n🔧 CONFIGURATION STATUS")
        print("-" * 30)
        print(f"✅ Mistral OCR: {'Enabled' if MISTRAL_API_KEY else '❌ Disabled (no API key)'}")
        print(f"✅ LLM Features: {'Enabled' if MARKITDOWN_USE_LLM else '❌ Disabled'}")
        print(f"✅ Azure Doc Intel: {'Enabled' if AZURE_DOC_INTEL_ENDPOINT else '❌ Disabled'}")
        print(f"\n💾 CACHE PERFORMANCE")
        print("-" * 30)
        cache = get_cache()
        cache_stats = cache.get_cache_stats()
        if cache_stats.get('total_entries', 0) > 0:
            print(f"📁 Total entries: {cache_stats['total_entries']}")
            print(f"💾 Cache size: {cache_stats['size_mb']:.1f} MB")
            print(f"🎯 Hit rate: {cache_stats.get('hit_rate', 0):.1%}")
            print(f"✅ Cache hits: {cache_stats.get('cache_hits', 0)}")
            print(f"❌ Cache misses: {cache_stats.get('cache_misses', 0)}")
        else:
            print("📝 No cache entries yet")
        print(f"\n📈 PROCESSING INSIGHTS")
        print("-" * 30)
        metadata_tracker = get_metadata_tracker()
        recommendations = metadata_tracker.get_recommendations()
        if recommendations:
            print("💡 Recommendations:")
            for key, rec in recommendations.items():
                print(f"   • {rec}")
        else:
            print("📝 No historical data available yet")
        print(f"\n📁 INPUT DIRECTORY ANALYSIS")
        print("-" * 30)
        files = [p for p in sorted(INPUT_DIR.iterdir()) if p.is_file()]
        if files:
            from utils import get_enhanced_file_strategy, analyze_file_complexity
            print(f"📊 Total files: {len(files)}")
            file_types = {}
            total_size = 0
            strategy_types = {}
            for f in files:
                ext = f.suffix.lower() or 'no_extension'
                file_types[ext] = file_types.get(ext, 0) + 1
                total_size += f.stat().st_size
                strategy = get_enhanced_file_strategy(f)
                strategy_desc = strategy.description
                strategy_types[strategy_desc] = strategy_types.get(strategy_desc, 0) + 1
            print(f"📦 Total size: {total_size / (1024*1024):.1f} MB")
            print(f"📋 File types:")
            for ext, count in sorted(file_types.items()):
                print(f"   • {ext}: {count} files")
            print(f"🎯 Recommended strategies:")
            for strategy, count in sorted(strategy_types.items()):
                print(f"   • {strategy}: {count} files")
        else:
            print("📝 No files found in input directory")
        print(f"\n⚡ SYSTEM RESOURCES")
        print("-" * 30)
        import os as _os
        try:
            import psutil
        except ImportError:
            psutil = None
        print(f"🖥️  CPU cores: {_os.cpu_count()}")
        if psutil:
            try:
                memory = psutil.virtual_memory()
                print(f"💾 Memory: {memory.percent}% used ({memory.available / (1024**3):.1f}GB available)")
                disk = psutil.disk_usage(str(INPUT_DIR))
                print(f"💽 Disk space: {disk.percent}% used ({disk.free / (1024**3):.1f}GB free)")
            except Exception as e:
                print(f"📊 Error getting system metrics: {e}")
        else:
            print("📊 Install psutil for detailed system metrics")
        print(f"\n💡 PERFORMANCE TIPS")
        print("-" * 30)
        if len(files) > 10:
            print("⚡ Use Enhanced Batch mode for multiple files")
        if cache_stats.get('hit_rate', 0) < 0.5 and cache_stats.get('total_entries', 0) > 5:
            print("🔄 Consider clearing cache if hit rate is low")
        if not MISTRAL_API_KEY:
            print("🔑 Add MISTRAL_API_KEY for OCR capabilities")
        if (sum(f.stat().st_size for f in files) / (1024*1024)) > 100:
            print("🚀 Large files detected - concurrent processing recommended")
        print("\n" + "="*60)
        input("\nPress Enter to continue...")
    except Exception as e:
        print(f"❌ Error displaying system status: {e}")
        print("This might be due to missing dependencies or configuration issues.")
        input("\nPress Enter to continue...")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Enhanced Document Converter v2.1")
    parser.add_argument("--version", action="version", version="2.1")
    parser.add_argument("--test", action="store_true", help="Run in test mode")
    parser.add_argument("--mode", choices=["hybrid", "markitdown", "ocr", "batch", "enhanced", "transcription"], help="Conversion mode")
    parser.add_argument("--no-interactive", action="store_true", help="Exit after processing")
    args = parser.parse_args()
    try:
        print_banner()
        print_env_summary()
        if args.test:
            print("\n[SUCCESS] Converter loaded successfully!")
            print("Ready to process documents.")
            sys.exit(0)
        if args.mode:
            if args.mode == "hybrid":
                convert_hybrid_pipeline()
            elif args.mode == "markitdown":
                convert_local_only()
            elif args.mode == "ocr":
                convert_mistral_only()
            elif args.mode == "transcription":
                convert_transcription_only()
            elif args.mode == "batch":
                batch_process_directory()
            elif args.mode == "enhanced":
                convert_enhanced_batch()
            if args.no_interactive:
                sys.exit(0)
        menu_loop()
    except Exception:
        print("\nFATAL ERROR:\n" + traceback.format_exc())
        sys.exit(1)
    finally:
        if not args.no_interactive:
            print("\nScript Finished.")
            try:
                input("Press Enter to close...")
            except Exception:
                pass
