"""
Validate template auto-scaling works correctly.
Checks that PNG templates can be loaded, scaled, and maintain proper dimensions.

Run: python tools/test_template_scaling.py
Requires: opencv-python, numpy
"""
import cv2
import numpy as np
import os
import sys

RESOLUTION_PRESETS = {
    "720p":  (1280, 720, 1.0),
    "1080p": (1920, 1080, 1.5),
    "1440p": (2560, 1440, 2.0),
    "4k":    (3840, 2160, 3.0),
}

def scale_template(img, scale):
    if scale == 1.0 or img is None:
        return img
    h, w = img.shape[:2]
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    return cv2.resize(img, (new_w, new_h), interpolation=interp)

def alpha_to_mask(img):
    if img is not None and img.shape[2] == 4:
        if np.min(img[:, :, 3]) == 0:
            _, mask = cv2.threshold(img[:, :, 3], 1, 255, cv2.THRESH_BINARY)
            return mask
    return None


def main():
    assets_dir = os.path.join(os.path.dirname(__file__), '..', 'assets')
    template_dirs = ['templates', 'npc', 'shop', 'item_properties', 'chests', 'gamble']

    # Collect all template PNGs
    all_pngs = []
    for subdir in template_dirs:
        dirpath = os.path.join(assets_dir, subdir)
        if not os.path.isdir(dirpath):
            continue
        for root, _, files in os.walk(dirpath):
            for f in files:
                if f.lower().endswith('.png'):
                    all_pngs.append(os.path.join(root, f))

    print(f"Found {len(all_pngs)} template PNGs\n")

    # Test scaling for each resolution
    errors = []
    for res_name, (w, h, scale) in RESOLUTION_PRESETS.items():
        if scale == 1.0:
            continue

        print(f"--- Testing {res_name} ({scale}x) ---")
        scaled_ok = 0
        alpha_ok = 0
        alpha_total = 0

        for png_path in all_pngs:
            img = cv2.imread(png_path, cv2.IMREAD_UNCHANGED)
            if img is None:
                errors.append(f"Failed to load: {png_path}")
                continue

            orig_h, orig_w = img.shape[:2]
            orig_channels = img.shape[2] if len(img.shape) == 3 else 1
            has_alpha = orig_channels == 4

            # Scale it
            scaled = scale_template(img, scale)
            new_h, new_w = scaled.shape[:2]
            new_channels = scaled.shape[2] if len(scaled.shape) == 3 else 1

            # Validate dimensions
            expected_w = max(1, int(orig_w * scale))
            expected_h = max(1, int(orig_h * scale))
            if new_w != expected_w or new_h != expected_h:
                rel = os.path.relpath(png_path, assets_dir)
                errors.append(f"{res_name} {rel}: got {new_w}x{new_h}, expected {expected_w}x{expected_h}")
                continue

            # Validate channels preserved
            if new_channels != orig_channels:
                rel = os.path.relpath(png_path, assets_dir)
                errors.append(f"{res_name} {rel}: channels changed {orig_channels} -> {new_channels}")
                continue

            scaled_ok += 1

            # Validate alpha mask still works
            if has_alpha:
                alpha_total += 1
                orig_mask = alpha_to_mask(img)
                scaled_mask = alpha_to_mask(scaled)
                if (orig_mask is not None) == (scaled_mask is not None):
                    alpha_ok += 1
                    if scaled_mask is not None:
                        # Mask should match scaled dimensions
                        if scaled_mask.shape != (new_h, new_w):
                            rel = os.path.relpath(png_path, assets_dir)
                            errors.append(f"{res_name} {rel}: mask shape {scaled_mask.shape} != image {(new_h, new_w)}")
                else:
                    rel = os.path.relpath(png_path, assets_dir)
                    errors.append(f"{res_name} {rel}: alpha mask existence changed after scaling")

        print(f"  Templates scaled: {scaled_ok}/{len(all_pngs)}")
        if alpha_total > 0:
            print(f"  Alpha masks OK:   {alpha_ok}/{alpha_total}")

        # Show some example dimensions
        sample = all_pngs[:3]
        for png_path in sample:
            img = cv2.imread(png_path, cv2.IMREAD_UNCHANGED)
            if img is None:
                continue
            scaled = scale_template(img, scale)
            rel = os.path.relpath(png_path, assets_dir)
            oh, ow = img.shape[:2]
            nh, nw = scaled.shape[:2]
            ch = img.shape[2] if len(img.shape) == 3 else 1
            alpha = "BGRA" if ch == 4 else "BGR"
            print(f"  {rel}: {ow}x{oh} -> {nw}x{nh} ({alpha})")
        print()

    print("=" * 60)
    if errors:
        print(f"FAILED ({len(errors)} errors):")
        for e in errors:
            print(f"  X {e}")
    else:
        print("ALL CHECKS PASSED")
        print(f"  - All {len(all_pngs)} templates scale correctly at 1.5x, 2x, 3x")
        print(f"  - Channel count preserved (BGR/BGRA)")
        print(f"  - Alpha masks preserved and dimensions match")
    print("=" * 60)


if __name__ == '__main__':
    main()
