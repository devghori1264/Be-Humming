#!/usr/bin/env python3

import argparse
import os
import sys
from pathlib import Path
from .utils.logging import Log

from .mods import perceptual
from .mods import lossless
from .mods import jpeg_binary_search
from .mods import hybrid_perceptual

def main():
    parser = argparse.ArgumentParser(
        description="Be-Humming: The Ultimate Image Compression Toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  be-humming --input /imgs --output /out perceptual-best-of --ssim 0.98
  be-humming --input /pngs --output /out lossless-first --target-kb 500
  be-humming --input /jpegs --output /out jpeg-binary-search --target-psnr 40
  be-humming --input /src --output /out hybrid-perceptual --use-butter
"""
    )

    parser.add_argument("--input", "-i", required=True, help="Input folder with images")
    parser.add_argument("--output", "-o", required=True, help="Output folder")
    parser.add_argument("--workers", "-w", type=int, default=os.cpu_count(), help="Number of parallel workers")
    parser.add_argument("--report-json", type=str, default=None, help="Path to save JSON report")
    parser.add_argument("--report-csv", type=str, default=None, help="Path to save CSV report")

    subparsers = parser.add_subparsers(dest="Mod", required=True, help="The compression Mod to use.")

    p_s1 = subparsers.add_parser("perceptual-best-of", help="Fast, multi-format (JPEG, WebP, AVIF), 'best-of' (smallest) compressor. (Based on Script 1)")
    p_s1.add_argument("--resize", type=int, default=None, help="Optional: Max dimension (width/height) to resize images to.")
    p_s1.add_argument("--quality", type=int, default=85, help="Target quality for WebP (0-100)")
    p_s1.add_argument("--quality-avif", type=int, default=30, help="Target CQ quality for AVIF (0-63, lower is better)")
    p_s1.add_argument("--ssim", type=float, default=0.98, help="Minimum SSIM score to maintain (0.0-1.0)")
    p_s1.add_argument('--no-webp', dest='webp', action='store_false', help="Disable WebP conversion")
    p_s1.add_argument('--no-avif', dest='avif', action='store_false', help="Disable AVIF conversion")
    p_s1.set_defaults(webp=True, avif=True, func=perceptual.run)

    p_s2 = subparsers.add_parser("lossless-first", help="Lossless-first PNG optimizer (Oxipng, Zopfli, WebP). (Based on Script 2)")
    p_s2.add_argument("--target-kb", type=int, default=None, help="Target max file size in KB. If no lossless candidate meets this, will force lossy WebP.")
    p_s2.add_argument("--allow-lossy", action="store_true", help="Allow lossy fallback (WebP) even without --target-kb")
    p_s2.add_argument("--lossy-quality", type=int, default=85, help="Quality for lossy WebP (if enabled)")
    p_s2.add_argument("--oxipng-level", type=int, default=4, help="Oxipng optimization level (0-6)")
    p_s2.add_argument("--zopfli-iter", type=int, default=15, help="Zopfli iterations")
    p_s2.set_defaults(func=lossless.run)

    p_s3 = subparsers.add_parser("jpeg-binary-search", help="JPEG-only binary search for lowest quality that meets perceptual threshold. (Based on Script 3)")
    p_s3.add_argument("--max-side", type=int, default=3000, help="Max side (px) for orientation-aware resize (R2)")
    p_s3.add_argument("--min-q", type=int, default=30, help="Minimum JPEG quality to search")
    p_s3.add_argument("--max-q", type=int, default=95, help="Maximum JPEG quality to search")
    p_s3.add_argument("--fallback-q", type=int, default=95, help="Fallback JPEG quality if search fails")
    p_s3.add_argument("--use-ssim", action="store_true", help="Use SSIM (scikit-image) as primary perceptual metric")
    p_s3.add_argument("--target-ssim", type=float, default=0.995, help="SSIM threshold (when --use-ssim)")
    p_s3.add_argument("--target-psnr", type=float, default=38.0, help="PSNR threshold (used when SSIM unavailable or not used)")
    p_s3.add_argument("--target-size-kb", type=int, default=450, help="Preferred target size (KB).")
    p_s3.add_argument("--keep-exif", action="store_true", help="Preserve EXIF data")
    p_s3.add_argument("--extensions", default="jpg,jpeg,JPG,JPEG", help="Comma-separated extensions to include")
    p_s3.set_defaults(func=jpeg_binary_search.run)


    p_s4 = subparsers.add_parser("hybrid-perceptual", help="Ultimate: Binary search for smallest perceptual-lossless JPEG, WebP, AND AVIF, then picks the smallest. (Based on Script 4)")
    p_s4.add_argument("--mode", choices=["jpeg", "best"], default="best", help="jpeg = keep as jpeg; best = pick smallest of jpeg/webp/avif")
    p_s4.add_argument("--min-q", type=int, default=30, help="Minimum quality to search")
    p_s4.add_argument("--max-q", type=int, default=95, help="Maximum quality to search")
    p_s4.add_argument("--target-psnr", type=float, default=38.0)
    p_s4.add_argument("--use-ssim", action="store_true", help="Use SSIM (requires scikit-image)")
    p_s4.add_argument("--target-ssim", type=float, default=0.995)
    p_s4.add_argument("--use-butter", action="store_true", help="Use butteraugli if binary is available (highest precision)")
    p_s4.add_argument("--target-butter", type=float, default=1.0, help="Butteraugli threshold (lower better, <1.0 is ~visually-lossless)")
    p_S4.add_argument("--target-size-kb", type=int, default=450, help="Desired target size per image in KB.")
    p_s4.add_argument("--keep-exif", action="store_true", help="Preserve EXIF in JPEG outputs")
    p_s4.add_argument("--extensions", default="jpg,jpeg,png,JPG,JPEG,PNG", help="Comma-separated extensions to include")
    p_s4.set_defaults(func=hybrid_perceptual.run)

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()
    if args.Mod == "perceptual-best-of" and cv2 is None:
        Log.error("The 'perceptual-best-of' Mod requires OpenCV. Please run: pip install opencv-python-headless")
        sys.exit(1)

    Log.info(f"Starting Be-Humming with Mod: {Log.HEADER}{args.Mod}{Log.ENDC}")
    try:
        args.func(args)
    except Exception as e:
        Log.error(f"A critical error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()