#!/usr/bin/env python3
"""
Cellpose AI Organoid & Cell Segmentation Script
Usage:
    python scripts/run_cellpose.py --image "data/BK52 single image/Overlay_BK52_9806_BGR.tif"
    python scripts/run_cellpose.py --folder "data/M3 single image"
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
    print(f"\n[*] Processing image with Cellpose: {img_path}")
    scanner = DatasetScanner()
    _, arr = scanner.load_image(img_path)
    
    summary, overlay, df_res = analyzer.extract_organoid_features(arr)
    count = summary['total_organoid_count']
    print(f"  └──  Cellpose detected {count} organoids/cells!")

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.basename(img_path)
    out_img = os.path.join(output_dir, f"cellpose_{filename}")
    out_csv = os.path.join(output_dir, f"cellpose_{os.path.splitext(filename)[0]}.csv")

    cv2.imwrite(out_img, cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
    df_res.to_csv(out_csv, index=False)
    print(f"  └── Saved annotated image to: {out_img}")
    print(f"  └── Saved statistics to: {out_csv}")

def main():
    parser = argparse.ArgumentParser(description="Cellpose AI Organoid Segmentation Runner")
    parser.add_argument("--image", type=str, default=None, help="Path to single TIF image")
    parser.add_argument("--folder", type=str, default="data/BK52 single image", help="Path to folder of images")
    parser.add_argument("--output_dir", type=str, default="output/cellpose", help="Output directory")
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
