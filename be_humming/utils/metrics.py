#!/usr/bin/env python3

import math
import re
from pathlib import Path
from PIL import Image, ImageChops

try:
    import numpy as np
except ImportError:
    np = None

try:
    from skimage.metrics import structural_similarity as ssim_func
except ImportError:
    ssim_func = None

try:
    import cv2
except ImportError:
    cv2 = None

from .logging import Log
from .shell import run_cmd

def files_identical(f1, f2):
    try:
        i1, i2 = Image.open(f1), Image.open(f2)
        if i1.mode != i2.mode or i1.size != i2.size:
            return False
        diff = ImageChops.difference(i1, i2)
        return not diff.getbbox()
    except Exception:
        return False

def compute_mse_psnr(orig_path, comp_path):
    if np is None:
        Log.warn("Numpy not found. Falling back to PIL-based PSNR (less precise).")
        try:
            o = Image.open(orig_path).convert("RGB")
            c = Image.open(comp_path).convert("RGB")
            if o.size != c.size:
                c = c.resize(o.size, Image.Resampling.LANCZOS)
            diff = ImageChops.difference(o, c)
            stat = Image.ImageStat.Stat(diff)
            rms = stat.rms  # per-channel RMS
            mse = sum((v ** 2 for v in rms)) / len(rms)
            if mse == 0:
                return 0.0, float("inf")
            psnr = 20 * math.log10(255.0 / math.sqrt(mse))
            return mse, psnr
        except Exception as e:
            Log.warn(f"PIL-based PSNR compute failed: {e}")
            return None, 0.0

    try:
        o = Image.open(orig_path).convert("RGB")
        c = Image.open(comp_path).convert("RGB")
        if o.size != c.size:
            c = c.resize(o.size, Image.Resampling.LANCZOS)

        oa = np.asarray(o, dtype=np.float64)
        ca = np.asarray(c, dtype=np.float64)
        mse = float(np.mean((oa - ca) ** 2))
        if mse == 0:
            return 0.0, float("inf")
        psnr = 20 * math.log10(255.0 / math.sqrt(mse))
        return mse, psnr
    except Exception as e:
        Log.warn(f"Numpy-based PSNR compute failed: {e}")
        return None, 0.0

def compute_ssim_skimage(orig_path, comp_path):
    if ssim_func is None or np is None:
        Log.warn("scikit-image or numpy not found. SSIM check skipped.")
        return None
    try:
        o = Image.open(orig_path).convert("RGB")
        c = Image.open(comp_path).convert("RGB")
        if o.size != c.size:
            c = c.resize(o.size, Image.Resampling.LANCZOS)
        oa = np.asarray(o, dtype=np.float32)
        ca = np.asarray(c, dtype=np.float32)
        h, w = oa.shape[:2]
        min_dim = min(h, w)
        if min_dim < 7:
            return 1.0  # Too small for SSIM window

        desired_win = 7
        win = min(desired_win, min_dim if (min_dim % 2 == 1) else (min_dim - 1))
        if win < 3: win = 3

        try:
            # Newer API
            score = ssim_func(oa, ca, channel_axis=2, win_size=win, data_range=255.0)
        except TypeError:
            # Older API
            score = ssim_func(oa, ca, multichannel=True, win_size=win, data_range=255.0)
        return float(score)
    except Exception as e:
        Log.warn(f"SSIM (skimage) compute failed: {e}")
        return None

def compute_ssim_cv2(original_path, compressed_path):
    if cv2 is None:
        Log.warn("OpenCV (cv2) not found. CV2-based SSIM check skipped.")
        return None
    try:
        original = cv2.imread(str(original_path))
        compressed = cv2.imread(str(compressed_path))

        if original is None or compressed is None:
            return 0.0

        if original.shape != compressed.shape:
            compressed = cv2.resize(compressed, (original.shape[1], original.shape[0]), interpolation=cv2.INTER_AREA)

        original_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
        compressed_gray = cv2.cvtColor(compressed, cv2.COLOR_BGR2GRAY)

        win_size = min(7, min(original_gray.shape) // 2)
        if win_size % 2 == 0: win_size -= 1
        if win_size < 3: win_size = 3

        return ssim_func(original_gray, compressed_gray, data_range=255, win_size=win_size)
    except Exception:
        return 0.0

def run_butteraugli(orig_path, comp_path, butter_bin):
    if not butter_bin:
        return None
    try:
        ok, out = run_cmd([butter_bin, str(orig_path), str(comp_path)], timeout=30)
        if not ok:
            Log.warn(f"Butteraugli run failed: {out}")
            return None

        m = re.search(r"([0-9]+(?:\.[0-9]+)?)", out)
        if m:
            return float(m.group(1))
        return None
    except Exception as e:
        Log.warn(f"Butteraugli failed: {e}")
        return None