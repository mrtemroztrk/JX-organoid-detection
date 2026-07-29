#!/usr/bin/env python3
"""
Cellpose Organoid Viability & Green Dye Analysis Script
Combines Cellpose AI organoid segmentation with green fluorescence internal dye checking.

Usage:
    python scripts/cellpose_organoid_viability.py --image "data/BK52 single image/Overlay_BK52_9806_BGR.tif"
    python scripts/cellpose_organoid_viability.py --folder "data/BK52 single image"
"""

import sys
import os
import argparse
import cv2

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append('/home/mrtemroztrk/.local/lib/python3.14/site-packages')

from src.dataset import DatasetScanner
from src.organoid_analyzer import OrganoidAnalyzer

def process_file(img_path, analyzer, output_dir, threshold):
    print(f"\n[*] Evaluating Cellpose Organoid Viability: {img_path}")
    scanner = DatasetScanner()
    _, arr = scanner.load_image(img_path)

    summary, overlay, df_res = analyzer.analyze_organoid_viability_cellpose(arr, min_green_pixels_threshold=int(threshold))
    print(f"  └── 🤖 Total Organoids (Cellpose): {summary['total_organoid_count']}")
    print(f"  └── 🟢 Dead Organoids (Green Positive): {summary['dead_organoid_count']}")
    print(f"  └── 🔴 Live Organoids: {summary['live_organoid_count']}")
    print(f"  └── 📊 Organoid Mortality Rate: {summary['mortality_rate_percent']}%")

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.basename(img_path)
    out_img = os.path.join(output_dir, f"viability_{filename}")
    out_csv = os.path.join(output_dir, f"viability_{os.path.splitext(filename)[0]}.csv")

    cv2.imwrite(out_img, cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
    df_res.to_csv(out_csv, index=False)
    print(f"  └── Saved annotated image to: {out_img}")
    print(f"  └── Saved detailed CSV to: {out_csv}")

def main():
    parser = argparse.ArgumentParser(description="Cellpose Organoid Viability Analyzer")
    parser.add_argument("--image", type=str, default=None, help="Path to single TIF image")
    parser.add_argument("--folder", type=str, default="data/BK52 single image", help="Path to image folder")
    parser.add_argument("--green_threshold", type=float, default=35.0, help="Green dye intensity threshold for Dead classification")
    parser.add_argument("--output_dir", type=str, default="output/cellpose_viability", help="Output directory")
    args = parser.parse_args()

    analyzer = OrganoidAnalyzer()

    if args.image:
        process_file(args.image, analyzer, args.output_dir, args.green_threshold)
    elif args.folder:
        files = [os.path.join(args.folder, f) for f in os.listdir(args.folder) if f.lower().endswith(('.tif', '.tiff'))]
        for f in sorted(files):
            process_file(f, analyzer, args.output_dir, args.green_threshold)

if __name__ == "__main__":
    main()
