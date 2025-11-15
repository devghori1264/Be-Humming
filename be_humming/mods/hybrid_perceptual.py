#!/usr/bin/env python3

import shutil
import tempfile
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from tqdm import tqdm

from ..utils.logging import Log
from ..utils.shell import run_cmd, which_bin
from ..utils.metrics import compute_mse_psnr, compute_ssim_skimage, run_butteraugli
from ..utils.image_ops import smart_resize_width_only
from ..utils.reporting import save_json_report, save_csv_report

def kb_to_bytes(k): return int(k * 1024)

def mozjpeg_save(in_path, out_path, cjpeg_bin, q=85):
    cmd = [cjpeg_bin, "-quality", str(q), "-optimize", "-progressive", "-sample", "1x1", "-outfile", str(out_path), str(in_path)]
    return run_cmd(cmd, expected_outpaths=[out_path])

def pillow_save_jpeg(in_path, out_path, q=85, keep_exif=False):
    try:
        img = Image.open(in_path)
        kwargs = {"format": "JPEG", "quality": q, "optimize": True, "progressive": True, "subsampling": 0}
        if keep_exif:
            exif = img.info.get("exif")
            if exif: kwargs["exif"] = exif
        img.save(out_path, **kwargs)
        return True, None
    except Exception as e:
        return False, str(e)

def cwebp_save(in_path, out_path, cwebp_bin, q=80):
    cmd = [cwebp_bin, "-q", str(q), str(in_path), "-o", str(out_path)]
    return run_cmd(cmd, expected_outpaths=[out_path])

def pillow_save_webp(in_path, out_path, q=80):
    try:
        img = Image.open(in_path)
        img.save(out_path, format="WEBP", quality=q)
        return True, None
    except Exception:
        return False, "Pillow fail"

def avifenc_save(in_path, out_path, avif_bin, q=50):
    cq = max(0, min(63, int(q * 63 / 100)))
    cmd = [avif_bin, "--min", str(cq), "--max", str(cq), str(in_path), str(out_path)]
    return run_cmd(cmd, expected_outpaths=[out_path])

def binary_search_quality(make_cand_fn, metrics_fn, orig, lo, hi, args, butter_bin):
    best = None
    tmpdir = Path(tempfile.mkdtemp(prefix="search_"))
    try:
        while lo <= hi:
            mid = (lo + hi) // 2
            cand = tmpdir / f"q{mid}.tmp"
            ok, note = make_cand_fn(mid, cand)
            if not ok:
                lo = mid + 1
                continue
            
            m = metrics_fn(orig, cand, butter_bin)
            
            passes = True
            if args.target_butter and m.get("butter") is not None:
                passes = m["butter"] <= args.target_butter
            elif args.use_ssim and m.get("ssim") is not None:
                passes = m["ssim"] >= args.target_ssim
            else:
                passes = (m.get("psnr") or 0) >= args.target_psnr

            if passes:
                best = {"q": mid, "path": cand, "metrics": m}
                hi = mid - 1
            else:
                lo = mid + 1

        if best:
            dest = tmpdir / f"best_q{best['q']}.bin"
            shutil.move(str(best["path"]), str(dest))
            return {"success": True, "q": best["q"], "path": dest, "metrics": best["metrics"]}
        return {"success": False}
    finally:
        pass

def process_file(in_file, out_dir, args, bins):
    in_path = Path(in_file)
    out_dir = Path(out_dir)
    
    res = {"file": str(in_path), "original_bytes": int(in_path.stat().st_size), "method": "none"}
    
    workdir = Path(tempfile.mkdtemp(prefix="work_"))
    try:
        resized, work_in = smart_resize_width_only(in_path, workdir / in_path.name)
        
        def metrics_fn(orig, cand, butter):
            mse, psnr = compute_mse_psnr(orig, cand)
            s = compute_ssim_skimage(orig, cand)
            b = run_butteraugli(orig, cand, butter) if butter else None
            return {"psnr": psnr, "ssim": s, "butter": b}

        candidates = []

        if args.mode in ("jpeg", "best"):
            def make_jpeg(q, p):
                if bins["cjpeg"]: return mozjpeg_save(work_in, p, bins["cjpeg"], q)
                return pillow_save_jpeg(work_in, p, q, args.keep_exif)
            
            r = binary_search_quality(make_jpeg, metrics_fn, work_in, args.min_q, args.max_q, args, bins["butter"])
            if r["success"]:
                candidates.append({"fmt": "jpg", "bytes": int(Path(r["path"]).stat().st_size), "path": r["path"], "q": r["q"]})

        if args.mode == "best":
            def make_webp(q, p):
                if bins["cwebp"]: return cwebp_save(work_in, p, bins["cwebp"], q)
                return pillow_save_webp(work_in, p, q)

            r = binary_search_quality(make_webp, metrics_fn, work_in, 10, 100, args, bins["butter"])
            if r["success"]:
                candidates.append({"fmt": "webp", "bytes": int(Path(r["path"]).stat().st_size), "path": r["path"], "q": r["q"]})

        if args.mode == "best" and bins["avifenc"]:
            def make_avif(q, p):
                return avifenc_save(work_in, p, bins["avifenc"], q)

            r = binary_search_quality(make_avif, metrics_fn, work_in, 10, 90, args, bins["butter"])
            if r["success"]:
                candidates.append({"fmt": "avif", "bytes": int(Path(r["path"]).stat().st_size), "path": r["path"], "q": r["q"]})

        if candidates:
            best = min(candidates, key=lambda x: x["bytes"])
            out_path = out_dir / f"{in_path.stem}.{best['fmt']}"
            shutil.move(str(best["path"]), str(out_path))
            res["final_bytes"] = best["bytes"]
            res["method"] = f"{best['fmt']} (q={best['q']})"
        else:
            shutil.copy2(in_path, out_dir / in_path.name)
            res["error"] = "No candidates met criteria"

    except Exception as e:
        res["error"] = str(e)
    finally:
        shutil.rmtree(str(workdir), ignore_errors=True)
    
    return res

def run(args):
    bins = {
        "cjpeg": which_bin(["cjpeg", "mozjpeg"]),
        "cwebp": which_bin(["cwebp"]),
        "avifenc": which_bin(["avifenc"]),
        "butter": which_bin(["butteraugli", "butteraugli.exe"]) if args.use_butter else None
    }
    
    in_dir = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    exts = [e.strip() for e in args.extensions.split(",")]
    files = []
    for e in exts: files.extend(in_dir.glob(f"*.{e}"))
    
    Log.info(f"Processing {len(files)} images (Mod 4)...")
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(process_file, f, out_dir, args, bins): f for f in files}
        for fut in tqdm(as_completed(futures), total=len(futures)):
            results.append(fut.result())

    if args.report_json:
        save_json_report(args.report_json, results)

    if args.report_csv:
        fieldnames = ["file", "original_size", "final_size", "method", "output_file", "error"]
        save_csv_report(args.report_csv, results, fieldnames)
        Log.info(f"CSV report saved to {args.report_csv}")