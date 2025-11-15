#!/usr/bin/env python3

import sys
import json
import csv
import shutil
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, ImageOps
from tqdm import tqdm

from ..utils.logging import Log
from ..utils.metrics import compute_mse_psnr, compute_ssim_skimage
from ..utils.image_ops import resize_orientation_aware_r2
from ..utils.reporting import save_json_report, save_csv_report

def bytes_to_kb(b): return round(b / 1024, 2)
def kb_to_bytes(k): return int(k * 1024)

def save_jpeg_pillow(in_path, out_path, q=85, subsampling=0, progressive=True, optimize=True, keep_exif=False):
    try:
        img = Image.open(in_path)
        exif_bytes = img.info.get("exif")
        img = ImageOps.exif_transpose(img)
        save_kwargs = {"format": "JPEG", "quality": q, "optimize": optimize, "progressive": progressive}
        if subsampling is not None: save_kwargs["subsampling"] = subsampling
        
        if keep_exif and exif_bytes:
            img.save(out_path, exif=exif_bytes, **save_kwargs)
        else:
            img.save(out_path, **save_kwargs)
        return True, None
    except Exception as e:
        return False, str(e)

def find_best_jpeg(in_work_path, orig_path, tmp_dir, min_q, max_q, target_psnr, target_ssim, use_ssim):
    lo, hi = min_q, max_q
    best = None
    
    while lo <= hi:
        mid = (lo + hi) // 2
        cand_path = Path(tmp_dir) / f"cand_q{mid}.jpg"
        ok, note = save_jpeg_pillow(in_work_path, cand_path, q=mid)
        
        if not ok:
            lo = mid + 1
            continue
            
        mse, psnr_val = compute_mse_psnr(orig_path, cand_path)
        ssim_val = compute_ssim_skimage(orig_path, cand_path) if use_ssim else None
        
        passes = False
        if use_ssim and ssim_val is not None:
            passes = ssim_val >= target_ssim
        else:
            if psnr_val is not None: passes = psnr_val >= target_psnr
            
        if passes:
            best = {"q": mid, "path": cand_path, "psnr": psnr_val, "ssim": ssim_val, "bytes": int(cand_path.stat().st_size)}
            hi = mid - 1
        else:
            lo = mid + 1

    if best: return {"success": True, **best}
    return {"success": False, "reason": "no q met thresholds"}

def process_file(in_file, out_dir, args):
    in_path = Path(in_file)
    out_dir = Path(out_dir)
    
    result = {
        "file": str(in_path),
        "original_bytes": int(in_path.stat().st_size),
        "final_bytes": int(in_path.stat().st_size),
        "resized": False,
        "error": None
    }

    tmp_root = Path(tempfile.mkdtemp(prefix="jpgopt_"))
    try:
        work_in = tmp_root / in_path.name
        resized, work_in = resize_orientation_aware_r2(in_path, work_in, max_side=args.max_side)
        result["resized"] = bool(resized)
        
        search = find_best_jpeg(str(work_in), str(in_path), tmp_root, args.min_q, args.max_q, args.target_psnr, args.target_ssim, args.use_ssim)
        
        if not search.get("success"):
            fallback = tmp_root / f"fallback.jpg"
            ok, note = save_jpeg_pillow(str(work_in), fallback, q=args.fallback_q, keep_exif=args.keep_exif)
            if ok:
                final_path = out_dir / in_path.name
                shutil.move(str(fallback), str(final_path))
                result["final_bytes"] = int(final_path.stat().st_size)
                result["quality"] = args.fallback_q
                return result
            else:
                final_path = out_dir / in_path.name
                shutil.copy2(in_path, final_path)
                return result

        q = int(search["q"])
        cand_path = Path(search["path"])
        cand_bytes = int(cand_path.stat().st_size)

        if args.target_size_kb and cand_bytes > kb_to_bytes(args.target_size_kb):
            q_try = q - 1
            while q_try >= args.min_q:
                try_path = tmp_root / f"try_q{q_try}.jpg"
                ok, _ = save_jpeg_pillow(str(work_in), try_path, q=q_try, keep_exif=args.keep_exif)
                if not ok: break
                
                _, psnr_t = compute_mse_psnr(str(in_path), try_path)
                ssim_t = compute_ssim_skimage(str(in_path), try_path) if args.use_ssim else None
                
                passes = True
                if args.use_ssim and ssim_t: passes = ssim_t >= args.target_ssim
                else: passes = (psnr_t and psnr_t >= args.target_psnr)
                
                if passes:
                    cand_path = try_path
                    q = q_try
                    if int(try_path.stat().st_size) <= kb_to_bytes(args.target_size_kb): break
                    q_try -= 1
                else:
                    break

        final_out = out_dir / in_path.with_suffix(".jpg").name
        shutil.move(str(cand_path), str(final_out))
        result["final_bytes"] = int(final_out.stat().st_size)
        result["quality"] = q
        return result

    except Exception as e:
        result["error"] = str(e)
        return result
    finally:
        try: shutil.rmtree(str(tmp_root))
        except: pass

def run(args):
    in_dir = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    exts = [e.strip() for e in args.extensions.split(",") if e.strip()]
    img_files = []
    for e in exts:
        img_files.extend(sorted(in_dir.glob(f"*.{e}")))

    if not img_files:
        Log.error("No images found.")
        sys.exit(1)

    Log.info(f"Processing {len(img_files)} images (Mod 3)...")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_file, f, out_dir, args): f for f in img_files}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Compressing"):
            results.append(fut.result())

    if args.report_json:
        save_json_report(args.report_json, results)

    if args.report_csv:
        fieldnames = ["file", "original_size", "final_size", "method", "output_file", "error"]
        save_csv_report(args.report_csv, results, fieldnames)
        Log.info(f"CSV report saved to {args.report_csv}")