#!/usr/bin/env python3
"""
Organoid Object-by-Object Feature Extraction Script
Extracts size (Area, Perimeter, Diameter), shape & contour irregularity (Circularity, Roughness, Solidity, Eccentricity),
and multi-channel fluorescence intensities (Green, Red, Blue) for each individual organoid.

Usage:
    python scripts/extract_organoid_features.py --image "data/BK52 single image/Overlay_BK52_9806_BGR.tif"
    python scripts/extract_organoid_features.py --folder "data/BK52 single image"
"""

import sys
import os
import argparse
import cv2

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append('/home/mrtemroztrk/.local/lib/python3.14/site-packages')

from src.dataset import DatasetScanner
from src.organoid_analyzer import OrganoidAnalyzer

def process_file(img_path, analyzer, output_dir, green_threshold):
    print(f"\n[*] Extracting per-organoid features: {img_path}")
    scanner = DatasetScanner()
    _, arr = scanner.load_image(img_path)

    summary, overlay, df_res = analyzer.extract_organoid_features(arr, min_green_pixels_threshold=int(green_threshold))
    print(f"  └── 🤖 Total Organoids: {summary['total_organoid_count']} ({summary['dead_organoid_count']} Dead, {summary['live_organoid_count']} Live)")
    print(f"  └── 📊 Mortality Rate: {summary['mortality_rate_percent']}%")

    if not df_res.empty:
        print("\n  Sample Organoid Object Features (First 3 Organoids):")
        cols_preview = ['Organoid_ID', 'Status', 'Area_px', 'Circularity', 'Contour_Roughness', 'Green_Mean_Intensity']
        print(df_res[cols_preview].head(3).to_string(index=False))

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.basename(img_path)
    out_img = os.path.join(output_dir, f"features_{filename}")
    out_csv = os.path.join(output_dir, f"features_{os.path.splitext(filename)[0]}.csv")

    cv2.imwrite(out_img, cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
    df_res.to_csv(out_csv, index=False)
    print(f"\n  └── Saved annotated overlay image: {out_img}")
    print(f"  └── Saved object-by-object CSV table: {out_csv}")

def main():
    parser = argparse.ArgumentParser(description="Organoid Object Feature Extraction")
    parser.add_argument("--image", type=str, default=None, help="Path to single TIF image")
    parser.add_argument("--folder", type=str, default="data/BK52 single image", help="Path to image folder")
    parser.add_argument("--green_threshold", type=float, default=35.0, help="Green intensity threshold for Dead classification")
    parser.add_argument("--output_dir", type=str, default="output/organoid_features", help="Output directory")
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
