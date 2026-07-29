#!/usr/bin/env python3
"""
Natural Killer (NK) Cell Red Fluorescence Pixel Quantification Script
Quantifies red fluorescence pixels for Natural Killer cells in microscopy images.

Usage:
    python scripts/count_red_nk_pixels.py --image "data/BK52 single image/Overlay_BK52_9806_BGR.tif"
    python scripts/count_red_nk_pixels.py --folder "data/BK52 single image"
"""

import sys
import os
import argparse
import cv2

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append('/home/mrtemroztrk/.local/lib/python3.14/site-packages')

from src.dataset import DatasetScanner
from src.organoid_analyzer import OrganoidAnalyzer

def process_file(img_path, analyzer, output_dir):
    print(f"\n[*] Quantifying Natural Killer (NK) Red Pixels: {img_path}")
    scanner = DatasetScanner()
    _, arr = scanner.load_image(img_path)

    results, overlay = analyzer.quantify_red_nk_cells(arr)
    print(f"  └── 🔴 Red Pixel Count (NK Cells): {results['red_pixel_count']:,} px")
    print(f"  └── 📐 Red Coverage Percentage: {results['red_coverage_percent']}%")
    print(f"  └── 💡 Mean Red Intensity: {results['mean_red_intensity']}")

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.basename(img_path)
    out_img = os.path.join(output_dir, f"nk_red_pixels_{filename}")
    out_csv = os.path.join(output_dir, f"nk_red_pixels_{os.path.splitext(filename)[0]}.csv")

    cv2.imwrite(out_img, cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
    import pandas as pd
    pd.DataFrame([results]).to_csv(out_csv, index=False)
    print(f"  └── Saved annotated image to: {out_img}")
    print(f"  └── Saved statistics to: {out_csv}")

def main():
    parser = argparse.ArgumentParser(description="NK Cell Red Pixel Quantification")
    parser.add_argument("--image", type=str, default=None, help="Path to single TIF image")
    parser.add_argument("--folder", type=str, default="data/BK52 single image", help="Path to image folder")
    parser.add_argument("--output_dir", type=str, default="output/nk_red_cells", help="Output directory")
    args = parser.parse_args()

    analyzer = OrganoidAnalyzer()

    if args.image:
        process_file(args.image, analyzer, args.output_dir)
    elif args.folder:
        files = [os.path.join(args.folder, f) for f in os.listdir(args.folder) if f.lower().endswith(('.tif', '.tiff'))]
        for f in sorted(files):
            process_file(f, analyzer, args.output_dir)

if __name__ == "__main__":
    main()
