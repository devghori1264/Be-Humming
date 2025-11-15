#!/usr/bin/env python3

import os
import sys
import json
import csv
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from tqdm import tqdm

from ..utils.logging import Log
from ..utils.shell import run_cmd, which_bin
from ..utils.metrics import compute_ssim_cv2
from ..utils.reporting import save_json_report, save_csv_report

def to_kb(size_bytes):
    return round(size_bytes / 1024, 2)

def resize_image(in_file, out_file, max_dim):
    try:
        with Image.open(in_file) as img:
            if max(img.size) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                img.save(out_file)
                return True, "Resized"
            else:
                shutil.copy2(in_file, out_file)
                return True, "No resize needed"
    except Exception as e:
        return False, str(e)

def optimize_jpeg_advanced(in_file, out_file, cjpeg_bin, quality_start=90, quality_min=50, ssim_threshold=0.98):
    best_q, best_size = None, float('inf')

    for q in range(quality_start, quality_min -1, -2):
        cmd = [cjpeg_bin, "-quality", str(q), "-optimize", "-progressive", "-outfile", str(out_file), str(in_file)]
        ok, note = run_cmd(cmd, expected_outpaths=[out_file])
        if not ok:
            continue

        current_ssim = compute_ssim_cv2(in_file, out_file)
        if current_ssim >= ssim_threshold:
            current_size = out_file.stat().st_size
            best_q, best_size = q, current_size
        else:
            break

    if best_q is not None:
        cmd = [cjpeg_bin, "-quality", str(best_q), "-optimize", "-progressive", "-outfile", str(out_file), str(in_file)]
        run_cmd(cmd, expected_outpaths=[out_file])
        final_ssim = compute_ssim_cv2(in_file, out_file)
        return True, f"jpeg_q{best_q}_ssim{final_ssim:.3f}", out_file.stat().st_size
    else:
        if out_file.exists(): out_file.unlink()
        return False, "Could not meet SSIM threshold", None

def convert_to_webp(in_file, out_file, cwebp_bin, quality=85, ssim_threshold=0.98):
    """Converts image to lossy WebP."""
    cmd = [cwebp_bin, "-q", str(quality), "-m", "6", "-pass", "10", "-low_memory", str(in_file), "-o", str(out_file)]
    ok, note = run_cmd(cmd, expected_outpaths=[out_file])
    if not ok or not out_file.exists():
        return False, note, None
    final_ssim = compute_ssim_cv2(in_file, out_file)
    if final_ssim < ssim_threshold:
        if out_file.exists(): out_file.unlink()
        return False, f"WebP SSIM {final_ssim:.3f} below threshold", None
    return True, f"webp_q{quality}_ssim{final_ssim:.3f}", out_file.stat().st_size

def convert_to_avif(in_file, out_file, avifenc_bin, quality=50, ssim_threshold=0.98):
    """Converts image to AVIF."""
    cmd = [avifenc_bin, "-j", "all", "-s", "4", "-y", "420", "--min", str(quality - 5), "--max", str(quality + 5), str(in_file), str(out_file)]
    ok, note = run_cmd(cmd, expected_outpaths=[out_file])
    if not ok or not out_file.exists():
        return False, note, None
    final_ssim = compute_ssim_cv2(in_file, out_file)
    if final_ssim < ssim_threshold:
        if out_file.exists(): out_file.unlink()
        return False, f"AVIF SSIM {final_ssim:.3f} below threshold", None
    return True, f"avif_cq{quality}_ssim{final_ssim:.3f}", out_file.stat().st_size

def process_file(in_path, out_dir, args, bins):
    in_path = Path(in_path)
    base_name = in_path.stem
    orig_size = in_path.stat().st_size
    temp_dir = out_dir / "temp"
    temp_dir.mkdir(exist_ok=True)

    temp_resized_file = temp_dir / f"{base_name}{in_path.suffix}"
    if args.resize:
        ok, note = resize_image(in_path, temp_resized_file, args.resize)
        if not ok:
            return {"file": str(in_path), "error": f"Resize failed: {note}"}
        source_file_for_compression = temp_resized_file
    else:
        source_file_for_compression = in_path

    candidates = []

    if bins["cjpeg"]:
        jpeg_out = temp_dir / f"{base_name}_optim.jpg"
        ok, method, size = optimize_jpeg_advanced(source_file_for_compression, jpeg_out, bins["cjpeg"], ssim_threshold=args.ssim)
        if ok: candidates.append({"method": method, "file": jpeg_out, "size": size})

    if args.webp and bins["cwebp"]:
        webp_out = temp_dir / f"{base_name}.webp"
        ok, method, size = convert_to_webp(source_file_for_compression, webp_out, bins["cwebp"], quality=args.quality, ssim_threshold=args.ssim)
        if ok: candidates.append({"method": method, "file": webp_out, "size": size})

    if args.avif and bins["avifenc"]:
        avif_out = temp_dir / f"{base_name}.avif"
        ok, method, size = convert_to_avif(source_file_for_compression, avif_out, bins["avifenc"], quality=args.quality_avif, ssim_threshold=args.ssim)
        if ok: candidates.append({"method": method, "file": avif_out, "size": size})
    if not candidates:
        if temp_resized_file.exists(): temp_resized_file.unlink()
        return {"file": str(in_path), "original_size": to_kb(orig_size), "final_size": to_kb(orig_size), "method": "none", "error": "No compression method was successful or met quality threshold."}

    best_candidate = min(candidates, key=lambda x: x['size'])
    final_out_path = out_dir / best_candidate['file'].name
    shutil.move(best_candidate['file'], final_out_path)

    for cand in candidates:
        if cand['file'].exists(): cand['file'].unlink()
    if temp_resized_file.exists(): temp_resized_file.unlink()

    return {
        "file": str(in_path),
        "original_size": to_kb(orig_size),
        "final_size": to_kb(best_candidate['size']),
        "method": best_candidate['method'],
        "output_file": str(final_out_path.name)
    }

def run(args):
    bins = {
        "cjpeg": which_bin(["cjpeg", "mozjpeg"]),
        "cwebp": which_bin(["cwebp"]),
        "avifenc": which_bin(["avifenc"])
    }
    if not bins["cjpeg"]: Log.warn("mozjpeg (cjpeg) not found. JPEG optimization will be skipped.")
    if not bins["cwebp"]: Log.warn("cwebp not found. WebP conversion will be skipped.")
    if not bins["avifenc"]: Log.warn("avifenc not found. AVIF conversion will be skipped.")

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "temp").mkdir(exist_ok=True)

    img_files = sorted([*in_dir.glob("*.png"), *in_dir.glob("*.jpg"), *in_dir.glob("*.jpeg")])
    if not img_files:
        Log.error("No compatible image files found in input folder.")
        sys.exit(1)

    Log.info(f"Processing {len(img_files)} images with {args.workers} workers...")
    Log.info(f"Quality settings: SSIM >= {args.ssim}, WebP Quality ~{args.quality}, AVIF CQ ~{args.quality_avif}")
    if args.resize: Log.info(f"Resizing images to max dimension: {args.resize}px")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_file, f, out_dir, args, bins): f for f in img_files}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Compressing (Mod 1)"):
            try:
                results.append(fut.result())
            except Exception as e:
                Log.error(f"Error processing {futures[fut]}: {e}")

    try: (out_dir / "temp").rmdir()
    except OSError: pass 

    Log.info("--- Compression Summary ---")
    total_orig_size = sum(r.get('original_size', 0) for r in results)
    total_final_size = sum(r.get('final_size', 0) for r in results)
    for r in sorted(results, key=lambda x: x['file']):
        if r.get("error"):
            Log.error(f"{Path(r['file']).name}: {r['error']}")
        else:
            saved = r['original_size'] - r['final_size']
            pct = saved / r['original_size'] * 100 if r['original_size'] > 0 else 0
            Log.success(f"{Path(r['file']).name} -> {r['output_file']} ({r['final_size']:.1f} KB) | Saved: {saved:.1f} KB ({pct:.1f}%) | Method: {r['method']}")

    if total_orig_size > 0:
        total_saved = total_orig_size - total_final_size
        total_pct = total_saved / total_orig_size * 100
        Log.info("-" * 25)
        Log.success(f"Total size before: {total_orig_size / 1024:.2f} MB")
        Log.success(f"Total size after:  {total_final_size / 1024:.2f} MB")
        Log.header(f"Total savings: {total_saved / 1024:.2f} MB ({total_pct:.1f}%)")

    if args.report_json:
        save_json_report(args.report_json, results)

    if args.report_csv:
        fieldnames = ["file", "original_size", "final_size", "method", "output_file", "error"]
        save_csv_report(args.report_csv, results, fieldnames)
        Log.info(f"CSV report saved to {args.report_csv}")