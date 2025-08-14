import os
import sys
import traceback
import time
from pathlib import Path
import shutil
from datetime import datetime

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
    MISTRAL_API_KEY, MISTRAL_MODEL, MISTRAL_INCLUDE_IMAGES, POPPLER_PATH,
    MARKITDOWN_USE_LLM, MARKITDOWN_LLM_MODEL, MARKITDOWN_LLM_KEY,
    AZURE_DOC_INTEL_ENDPOINT, AZURE_DOC_INTEL_KEY, MAX_RETRIES
)
from utils import logline, md_to_txt, have, write_text
from local_converter import run_markitdown_enhanced, extract_tables_to_markdown, pdfs_to_images
from mistral_converter import mistral_ocr_file_enhanced, process_mistral_response, process_mistral_response_enhanced

def convert_local_only():
    print("\n=== Local conversion (MarkItDown + tables) ===")
    files = [p for p in sorted(INPUT_DIR.iterdir()) if p.is_file()]
    if not files:
        print("No input files found.")
        return
    ok_count = 0
    for f in files:
        base = f.stem
        print(f"Processing: {f.name}")
        produced: list[Path] = []

        # 1. Run Enhanced MarkItDown
        md_main = OUT_MD / f"{base}.md"
        ok_md = run_markitdown_enhanced(f, md_main)
        if ok_md:
            produced.append(md_main)

        # 2. Extract local tables (PDF only)
        if f.suffix.lower() == ".pdf":
            try:
                extracted_tables = extract_tables_to_markdown(f, base)
                produced += extracted_tables
                if extracted_tables:
                    logline(f"  -> wrote {len(extracted_tables)} table file(s).")
            except Exception as e:
                print(f"  -> Local table extraction error: {e}")
                traceback.print_exc()

        # 3. Convert all produced MD files to TXT
        for md in produced:
            txt = OUT_TXT / (md.name.rsplit(".", 1)[0] + ".txt")
            md_to_txt(md, txt)

        if produced:
            ok_count += 1

    print("\n=== Summary ===")
    print(f"Successfully processed files: {ok_count}")

def convert_mistral_only():
    print("\n=== OCR conversion (Mistral only) ===")
    # Mistral OCR supports PDFs and images
    supported_exts = (".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif")
    files = [p for p in sorted(INPUT_DIR.iterdir()) if p.is_file() and p.suffix.lower() in supported_exts]

    if not files:
        print("No suitable files found in input.")
        if not MISTRAL_API_KEY:
             logline("-> ERROR: MISTRAL_API_KEY not set.")
        return

    ok_count = 0
    for doc in files:
        base = doc.stem
        print(f"Processing: {doc.name}")
        # Use enhanced Mistral OCR with caching and retry
        resp = mistral_ocr_file_enhanced(doc, base, use_cache=True)
        if not resp:
            continue

        # Process response (generate MD, save images, handle fallbacks)
        out_md = process_mistral_response_enhanced(resp, base, doc)

        if out_md:
            print(f"  -> wrote: {out_md.relative_to(OUT_MD.parent)}")
            if MISTRAL_INCLUDE_IMAGES:
                 # Check if the image directory actually contains files before logging
                 img_dir = OUT_IMG / f"{base}_ocr"
                 if img_dir.exists() and any(img_dir.iterdir()):
                    print(f"  -> extracted images to output_images/{base}_ocr/")
            txt = OUT_TXT / (out_md.name.rsplit(".", 1)[0] + ".txt")
            md_to_txt(out_md, txt)
            ok_count += 1

    print("\n=== Summary ===")
    print(f"Successfully processed files: {ok_count}")

def convert_hybrid_pipeline():
    """
    Enhanced hybrid pipeline with intelligent file type detection and routing.
    Uses optimal processing strategy based on file analysis and available capabilities.
    """
    print("\n=== Enhanced Hybrid Processing (Markitdown + Mistral OCR) ===")

    files = [p for p in sorted(INPUT_DIR.iterdir()) if p.is_file()]
    if not files:
        print("No input files found.")
        return

    # Import here to avoid circular dependency
    from utils import get_enhanced_file_strategy, analyze_file_complexity

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
        
        produced: list[Path] = []
        start_time = time.time()

        # 1. Markitdown processing (if recommended)
        md_main = OUT_MD / f"{base}.md"
        ok_md = False
        table_files = []
        
        if strategy.use_markitdown:
            print(f"   🔄 Running Markitdown...")
            ok_md = run_markitdown_enhanced(f, md_main)
            if ok_md:
                produced.append(md_main)
                print(f"   ✅ Markitdown successful")

                # Enhanced table extraction for PDFs
                if f.suffix.lower() == '.pdf':
                    try:
                        table_files = extract_tables_to_markdown(f, base)
                        produced += table_files
                        if table_files:
                            print(f"   📊 Extracted {len(table_files)} table file(s)")
                    except Exception as e:
                        logline(f"   ⚠️  Table extraction error: {e}")

        # 2. Mistral OCR processing (if recommended and available)
        ocr_md = None
        if strategy.use_ocr and MISTRAL_API_KEY:
            print(f"   🔄 Running Mistral OCR...")
            resp = mistral_ocr_file_enhanced(f, base, use_cache=True)
            if resp:
                ocr_md_path = process_mistral_response_enhanced(resp, base, f)
                if ocr_md_path:
                    produced.append(ocr_md_path)
                    ocr_md = ocr_md_path
                    print(f"   ✅ OCR successful")
                else:
                    print(f"   ⚠️  OCR response processing failed")
            else:
                print(f"   ❌ OCR failed")
        elif strategy.use_ocr and not MISTRAL_API_KEY:
            print(f"   ⚠️  OCR recommended but MISTRAL_API_KEY not configured")

        # 3. Intelligent output combination
        if ok_md and (ocr_md or table_files):
            combined_path = OUT_MD / f"{base}_combined.md"
            print(f"   🔧 Creating enhanced combined output...")
            try:
                # Enhanced combined output with better structure
                markitdown_content = md_main.read_text(encoding="utf-8")
                
                combined = f"# Enhanced Processing Results: {base}\n\n"
                combined += f"**Processing Strategy**: {strategy.description}\n"
                combined += f"**File Size**: {complexity['size_mb']:.1f}MB\n"
                combined += f"**Processed**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                combined += f"**Methods Used**: {'Markitdown' if strategy.use_markitdown else ''}{'+ OCR' if strategy.use_ocr else ''}\n"
                combined += f"**Benefits**: {', '.join(strategy.benefits)}\n\n"
                combined += "---\n\n"

                # Main content from Markitdown
                combined += "## 📝 Primary Content (Markitdown)\n\n"
                combined += markitdown_content

                # Extracted tables (if any)
                if table_files:
                    combined += "\n\n---\n\n"
                    combined += "## 📊 Extracted Tables (Local Analysis)\n\n"
                    for i, table_file in enumerate(table_files):
                        combined += f"### Table {i+1}: {table_file.name}\n\n"
                        try:
                            table_content = table_file.read_text(encoding="utf-8")
                            combined += table_content + "\n\n"
                        except Exception as e:
                            combined += f"*Error loading table: {e}*\n\n"

                # OCR analysis (if available)
                if ocr_md:
                    combined += "\n\n---\n\n"
                    combined += "## 🔍 Enhanced OCR Analysis (Mistral)\n\n"
                    ocr_content = ocr_md.read_text(encoding="utf-8")
                    combined += ocr_content

                write_text(combined_path, combined)
                produced.append(combined_path)
                print(f"   ✅ Combined output created")

            except Exception as e:
                print(f"   ❌ Failed to create combined output: {e}")

        # 4. Convert all markdown to text
        for md_file in produced:
            txt = OUT_TXT / (md_file.stem + ".txt")
            md_to_txt(md_file, txt)

        # Track processing results
        processing_time = time.time() - start_time
        total_processing_time += processing_time
        
        if produced:
            ok_count += 1
            print(f"   ✅ Generated {len(produced)} output file(s) in {processing_time:.1f}s")
        else:
            print(f"   ❌ No output generated")

    # Enhanced summary
    print("\n" + "="*60)
    print("📈 PROCESSING SUMMARY")
    print("="*60)
    print(f"✅ Successfully processed: {ok_count}/{len(files)} files")
    print(f"⏱️  Total processing time: {total_processing_time:.1f}s")
    print(f"⚡ Average time per file: {total_processing_time/len(files):.1f}s")
    print(f"📁 Output locations:")
    print(f"   • Markdown: {OUT_MD}/")
    print(f"   • Text: {OUT_TXT}/")
    if MISTRAL_INCLUDE_IMAGES:
        print(f"   • Images: {OUT_IMG}/")
    print("="*60)

def batch_process_directory():
    """Process files in batches for better performance."""
    print("\n=== Batch Processing Mode ===")

    files = list(INPUT_DIR.iterdir())
    if not files:
        print("No files to process.")
        return

    # Group files by type for optimized processing
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

        # Process in batches
        for i in range(0, len(group_files), BATCH_SIZE):
            batch = group_files[i:i+BATCH_SIZE]
            print(f"  Batch {i//BATCH_SIZE + 1}: Processing {len(batch)} files")

            for f in batch:
                base = f.stem
                try:
                    # Determine best processor
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

    # Markitdown checks
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

    # Table extraction
    if pd is not None and pdfplumber is not None:
        print("[OK] Table extraction enabled (pdfplumber + pandas)")
    else:
        missing = []
        if pd is None: missing.append("pandas")
        if pdfplumber is None: missing.append("pdfplumber")
        print(f"[WARN] Table extraction limited (missing: {', '.join(missing)})")

    # Check python tabulate module
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

    # Mistral OCR
    if MISTRAL_API_KEY:
        print(f"[OK] Mistral OCR configured")
        print(f"  -> Model: {MISTRAL_MODEL}")
        print(f"  -> Image extraction: {'Enabled' if MISTRAL_INCLUDE_IMAGES else 'Disabled'}")
        print(f"  -> Caching: Enabled (24h)")
        print(f"  -> Retry: {MAX_RETRIES} attempts with backoff")
    else:
        print("[WARN] Mistral OCR not configured (set MISTRAL_API_KEY in .env)")

    # PDF to Image
    if convert_from_path is not None:
        if POPPLER_PATH or have("pdftoppm"):
            print("[OK] PDF to image conversion available")
        else:
            print("[WARN] PDF to image needs Poppler (set POPPLER_PATH)")

    # Performance settings
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
    """Enhanced interactive menu with all processing options."""
    while True:
        print("\n" + "="*60)
        print("    ENHANCED DOCUMENT CONVERTER v2.0")
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
        print("  5) Standard Batch Process")
        print("     -> Process all files with basic settings")
        print()
        print("  6) Convert PDFs to Images")
        print("     -> Extract pages as PNG files")
        print()
        print("  7) Show System Status")
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
            batch_process_directory()
        elif choice == "6":
            pdfs_to_images()
        elif choice == "7":
            show_system_status()
        elif choice in ("q", "quit", "exit"):
            print("\nThank you for using Enhanced Document Converter v2.0!")
            break
        else:
            print("Invalid choice. Please try again.")

def print_banner():
    from datetime import datetime
    from config import APP_ROOT
    print("=" * 60)
    print("   ENHANCED DOCUMENT CONVERTER v2.0")
    print("   Powered by Microsoft Markitdown & Mistral OCR")
    print("=" * 60)
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Working directory: {APP_ROOT}")

def convert_enhanced_batch():
    """
    Enhanced batch processing with all optimization features:
    - Intelligent file type detection and routing
    - Concurrent processing with rate limiting
    - Advanced caching and metadata tracking
    - Comprehensive error handling and recovery
    """
    print("\n=== ENHANCED BATCH PROCESSING ===")
    print("🚀 Using all optimization features for maximum performance")
    
    files = [p for p in sorted(INPUT_DIR.iterdir()) if p.is_file()]
    if not files:
        print("No input files found.")
        return
    
    # Import enhanced utilities
    from utils import (
        ConcurrentProcessor, ErrorRecoveryManager, get_cache, get_metadata_tracker,
        create_file_processor_function, get_enhanced_file_strategy, analyze_file_complexity
    )
    
    # Initialize components
    cache = get_cache()
    metadata_tracker = get_metadata_tracker()
    processor = ConcurrentProcessor(max_workers=4, rate_limit_delay=1.5)
    error_manager = ErrorRecoveryManager()
    
    print(f"\n📊 PROCESSING ANALYSIS")
    print("="*50)
    
    # Analyze all files
    analysis_results = {}
    total_estimated_time = 0
    
    for f in files:
        strategy = get_enhanced_file_strategy(f)
        complexity = analyze_file_complexity(f)
        analysis_results[f] = (strategy, complexity)
        
        # Parse estimated time
        time_str = complexity['estimated_processing_time']
        if time_str.endswith('s'):
            total_estimated_time += int(time_str[:-1])
    
    # Display analysis summary
    print(f"📁 Files to process: {len(files)}")
    print(f"⏱️  Estimated total time: {total_estimated_time}s ({total_estimated_time//60}m {total_estimated_time%60}s)")
    
    strategy_counts = {}
    for strategy, _ in analysis_results.values():
        desc = strategy.description
        strategy_counts[desc] = strategy_counts.get(desc, 0) + 1
    
    print(f"🎯 Processing strategies:")
    for desc, count in strategy_counts.items():
        print(f"   • {desc}: {count} files")
    
    # Cache analysis
    cache_stats = cache.get_cache_stats()
    if cache_stats.get('total_entries', 0) > 0:
        print(f"💾 Cache: {cache_stats['total_entries']} entries, {cache_stats['size_mb']:.1f}MB")
        print(f"   Hit rate: {cache_stats.get('hit_rate', 0):.1%}")
    
    # Get historical recommendations
    recommendations = metadata_tracker.get_recommendations()
    if recommendations:
        print(f"\n💡 RECOMMENDATIONS")
        for key, rec in recommendations.items():
            print(f"   • {rec}")
    
    print("\n" + "="*50)
    
    # Progress callback
    def progress_callback(completed: int, total: int):
        percentage = (completed / total) * 100
        print(f"\r🔄 Progress: {completed}/{total} ({percentage:.1f}%) ", end="", flush=True)
    
    # Create enhanced processor function
    processor_func = create_file_processor_function(use_enhanced_strategy=True)
    
    print(f"\n🚀 Starting enhanced batch processing...")
    start_time = time.time()
    
    try:
        # Process files with all enhancements
        results = processor.process_files_concurrent(
            files, 
            processor_func,
            progress_callback
        )
        
        processing_time = time.time() - start_time
        print(f"\n\n✅ Processing completed in {processing_time:.1f}s")
        
        # Analyze results
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        print(f"\n📈 ENHANCED PROCESSING RESULTS")
        print("="*60)
        print(f"✅ Successful: {len(successful)}/{len(results)} ({len(successful)/len(results):.1%})")
        print(f"❌ Failed: {len(failed)}")
        print(f"⚡ Average time per file: {processing_time/len(files):.1f}s")
        print(f"🏆 Speedup vs estimated: {total_estimated_time/processing_time:.1f}x faster")
        
        # Track all results
        for result in results:
            metadata_tracker.track_file_processing(result.file_path, result)
        
        # Processing method breakdown
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
        
        # Error analysis
        if failed:
            print(f"\n⚠️  Error analysis:")
            error_types = {}
            for result in failed:
                error_type = result.error_message.split(':')[0] if result.error_message else "Unknown"
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            for error_type, count in error_types.items():
                print(f"   • {error_type}: {count} files")
        
        # Performance statistics
        processor_stats = processor.get_processing_stats()
        print(f"\n📊 Performance metrics:")
        print(f"   • API calls made: {processor_stats.get('api_calls', 0)}")
        print(f"   • Cache utilization: {cache.get_cache_stats().get('hit_rate', 0):.1%}")
        print(f"   • Processing efficiency: {processor_stats.get('success_rate', 0):.1%}")
        
        # Cache cleanup
        cache.cleanup_old_entries()
        
        # Finalize session tracking
        metadata_tracker.add_performance_metric('total_processing_time', processing_time)
        metadata_tracker.add_performance_metric('files_per_second', len(files) / processing_time)
        metadata_tracker.add_performance_metric('concurrent_workers', processor.max_workers)
        metadata_tracker.finalize_session()
        
        print(f"\n💾 Session data saved for future optimization")
        print("="*60)
        
    except KeyboardInterrupt:
        print(f"\n\n⚠️  Processing interrupted by user")
        metadata_tracker.log_error("Processing interrupted by user", {'files_completed': len([r for r in results if hasattr(r, 'success')])})
        metadata_tracker.finalize_session()
    except Exception as e:
        print(f"\n\n❌ Processing failed: {e}")
        metadata_tracker.log_error(f"Batch processing failed: {e}")
        metadata_tracker.finalize_session()
        raise

def show_system_status():
    """Display comprehensive system status, cache performance, and recommendations."""
    print("\n" + "="*60)
    print("📊 ENHANCED DOCUMENT CONVERTER - SYSTEM STATUS")
    print("="*60)
    
    try:
        from utils import get_cache, get_metadata_tracker
        from config import MISTRAL_API_KEY, MARKITDOWN_USE_LLM, AZURE_DOC_INTEL_ENDPOINT
        
        # Configuration Status
        print("\n🔧 CONFIGURATION STATUS")
        print("-" * 30)
        print(f"✅ Mistral OCR: {'Enabled' if MISTRAL_API_KEY else '❌ Disabled (no API key)'}")
        print(f"✅ LLM Features: {'Enabled' if MARKITDOWN_USE_LLM else '❌ Disabled'}")
        print(f"✅ Azure Doc Intel: {'Enabled' if AZURE_DOC_INTEL_ENDPOINT else '❌ Disabled'}")
        
        # Cache Statistics
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
        
        # Processing History and Recommendations
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
        
        # File Analysis
        print(f"\n📁 INPUT DIRECTORY ANALYSIS")
        print("-" * 30)
        
        files = [p for p in sorted(INPUT_DIR.iterdir()) if p.is_file()]
        if files:
            from utils import get_enhanced_file_strategy, analyze_file_complexity
            
            print(f"📊 Total files: {len(files)}")
            
            # File type breakdown
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
        
        # System Resources
        print(f"\n⚡ SYSTEM RESOURCES")
        print("-" * 30)
        import os
        try:
            import psutil
        except ImportError:
            psutil = None
        
        print(f"🖥️  CPU cores: {os.cpu_count()}")
        
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
        
        # Performance Tips
        print(f"\n💡 PERFORMANCE TIPS")
        print("-" * 30)
        
        if len(files) > 10:
            print("⚡ Use Enhanced Batch mode for multiple files")
        
        if cache_stats.get('hit_rate', 0) < 0.5 and cache_stats.get('total_entries', 0) > 5:
            print("🔄 Consider clearing cache if hit rate is low")
        
        if not MISTRAL_API_KEY:
            print("🔑 Add MISTRAL_API_KEY for OCR capabilities")
        
        if total_size > 100 * 1024 * 1024:  # 100MB
            print("🚀 Large files detected - concurrent processing recommended")
        
        print("\n" + "="*60)
        input("\nPress Enter to continue...")
        
    except Exception as e:
        print(f"❌ Error displaying system status: {e}")
        print("This might be due to missing dependencies or configuration issues.")
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced Document Converter v2.0")
    parser.add_argument("--test", action="store_true", help="Run in test mode")
    parser.add_argument("--mode", choices=["hybrid", "markitdown", "ocr", "batch", "enhanced"], help="Conversion mode")
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
