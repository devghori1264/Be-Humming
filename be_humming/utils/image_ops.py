#!/usr/bin/env python3

import shutil
from pathlib import Path
from PIL import Image, ImageOps

def resize_max_dimension(in_file, out_file, max_dim):
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

def resize_orientation_aware_r2(in_path, out_path, max_side=3000):
    try:
        img = Image.open(in_path)
        img = ImageOps.exif_transpose(img)
        w, h = img.size

        if w >= h:
            if w > max_side:
                new_h = int(h * (max_side / w))
                img = img.resize((max_side, new_h), Image.Resampling.LANCZOS)
                img.save(out_path)
                return True, out_path
        else:
            if h > max_side:
                new_w = int(w * (max_side / h))
                img = img.resize((new_w, max_side), Image.Resampling.LANCZOS)
                img.save(out_path)
                return True, out_path

        shutil.copy2(in_path, out_path)
        return False, out_path
    except Exception as e:
        return False, str(e)

def smart_resize_width_only(in_path, out_path, max_width=3000):
    try:
        img = Image.open(in_path)
        width, height = img.size
        if width > max_width:
            new_h = int(height * (max_width / width))
            img = img.resize((max_width, new_h), Image.Resampling.LANCZOS)
            img.save(out_path)
            return True, out_path
        else:
            shutil.copy2(in_path, out_path)
            return False, out_path
    except Exception as e:
        return False, str(e)