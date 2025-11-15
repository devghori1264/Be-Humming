#!/usr/bin/env python3

import os
import sys
import json
import csv
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from ..utils.logging import Log
from ..utils.shell import run_cmd, which_bin
from ..utils.metrics import files_identical
from ..utils.reporting import save_json_report, save_csv_report

def to_kb(size_bytes):
    return round(size_bytes / 1024, 2)

def optimize_with_pillow(in_file, out_file):
    from PIL import Image
    try:
        img = Image.open(in_file)
        img.save(out_file, format="PNG", optimize=True)
        return True, None
    except Exception as e:
        return False, str(e)

def optimize_with_oxipng(in_file, out_file, oxipng_bin, level=4):
    cmd = [oxipng_bin, "-o", str(level), "--strip", "safe", "-out", str(out_file), str(in_file)]
    return run_cmd(cmd, expected_outpaths=[out_file])

def optimize_with_zopflipng(in_file, out_file, zopfli_bin, iterations=15):
    cmd = [zopfli_bin, "-y", "-m", "-i", str(iterations), str(in_file), str(out_file)]
    return run_cmd(cmd, expected_outpaths=[out_file])

def convert_to_webp(in_file, out_file, cwebp_bin, lossless=True, q=100):
    if lossless:
        cmd = [cwebp_bin, "-lossless", "-q", "100", str(in_file), "-o", str(out_file)]
    else:
        cmd = [cwebp_bin, "-q", str(q), str(in_file), "-o", str(out_file)]
    return run_cmd(cmd, expected_outpaths=[out_file])

def compress_to_webp_target(in_file, out_file, cwebp_bin, target_kb, min_q=30, max_q=95, step=5):
    """Iteratively compress WebP until <= target_kb."""
    temp_out = out_file.with_suffix(".webp")
    best_file, final_size, used_q = None, None, None

    for q in range(max_q, min_q - 1, -step):
        ok, note = convert_to_webp(in_file, temp_out, cwebp_bin, lossless=False, q=q)
        if not ok: continue
        
        size_kb = os.path.getsize(temp_out) / 1024
        if size_kb <= target_kb:
            best_file, final_size, used_q = temp_out, size_kb, q
            break

    if best_file:
        shutil.move(best_file, out_file)
        return True, f"webp-q{used_q}", int(final_size * 1024)
    return False, None, None

def process_file(in_path, out_dir, args, bins):
    in_path = Path(in_path)
    base_name = in_path.stem
    orig_size = in_path.stat().st_size
    candidates = []

    pillow_out = out_dir / f"{base_name}_pillow.png"
    ok, note = optimize_with_pillow(in_path, pillow_out)
    if ok: candidates.append(("pillow", pillow_out, True, note))

    if bins["oxipng"]:
        oxi_out = out_dir / f"{base_name}_oxipng.png"
        ok, note = optimize_with_oxipng(in_path, oxi_out, bins["oxipng"], args.oxipng_level)
        if ok: candidates.append(("oxipng", oxi_out, True, note))

    if bins["zopflipng"]:
        zop_out = out_dir / f"{base_name}_zopfli.png"
        ok, note = optimize_with_zopflipng(in_path, zop_out, bins["zopflipng"], args.zopfli_iter)
        if ok: candidates.append(("zopfli", zop_out, True, note))

    if bins["cwebp"]:
        webp_out = out_dir / f"{base_name}_lossless.webp"
        ok, note = convert_to_webp(in_path, webp_out, bins["cwebp"], lossless=True)
        if ok and files_identical(in_path, webp_out):
            candidates.append(("webp_lossless", webp_out, True, note))

    if args.allow_lossy and args.lossy_quality and bins["cwebp"]:
        lossy_out = out_dir / f"{base_name}_lossy.webp"
        ok, note = convert_to_webp(in_path, lossy_out, bins["cwebp"], lossless=False, q=args.lossy_quality)
        if ok: candidates.append((f"webp_q{args.lossy_quality}", lossy_out, True, note))

    best = None
    for method, file, ok, note in candidates:
        if not ok or not file.exists(): continue
        size = file.stat().st_size
        if args.target_kb and size > args.target_kb * 1024:
            continue
        if not best or size < best["final_size"]:
            best = {"method": method, "file": file, "final_size": size, "note": note}

    if not best and args.target_kb and bins["cwebp"]:
        forced_out = out_dir / f"{base_name}.webp"
        ok, method, final_size = compress_to_webp_target(in_path, forced_out, bins["cwebp"], args.target_kb)
        if ok:
            best = {"method": method, "file": forced_out, "final_size": final_size, "note": "forced lossy"}

    if not best:
        for _, f, _, _ in candidates:
            if f.exists(): f.unlink()
        return {
            "file": str(in_path),
            "original_size": to_kb(orig_size),
            "final_size": to_kb(orig_size),
            "method": "none",
            "error": "No valid compression met criteria"
        }

    final_out = out_dir / in_path.name
    shutil.move(best["file"], final_out)

    for _, f, _, _ in candidates:
        if f.exists() and f != final_out: f.unlink()

    return {
        "file": str(in_path),
        "original_size": to_kb(orig_size),
        "final_size": to_kb(best["final_size"]),
        "method": best["method"],
        "note": best["note"]
    }

def run(args):
    bins = {
        "oxipng": which_bin(["oxipng"]),
        "zopflipng": which_bin(["zopflipng"]),
        "cwebp": which_bin(["cwebp"])
    }

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    png_files = list(in_dir.glob("*.png"))
    if not png_files:
        Log.error("No PNG files found.")
        sys.exit(1)

    Log.info(f"Processing {len(png_files)} images (Mod 2)...")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_file, f, out_dir, args, bins): f for f in png_files}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Optimizing"):
            try:
                results.append(fut.result())
            except Exception as e:
                Log.error(f"Error: {e}")

    Log.info("Summary:")
    for r in results:
        if r.get("error"):
            Log.error(f"{r['file']}: {r['error']}")
        else:
            saved = r['original_size'] - r['final_size']
            pct = saved / r['original_size'] * 100 if r['original_size'] else 0
            Log.success(f"{Path(r['file']).name} -> {r['final_size']} KB (saved {pct:.1f}%) [{r['method']}]")

    if args.report_json:
        save_json_report(args.report_json, results)

    if args.report_csv:
        fieldnames = ["file", "original_size", "final_size", "method", "output_file", "error"]
        save_csv_report(args.report_csv, results, fieldnames)
        Log.info(f"CSV report saved to {args.report_csv}")