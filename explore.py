#!/usr/bin/env python3
"""
Organoid Microscopy Image Dataset Explorer (CLI Tool)
Usage:
    python explore.py
    python explore.py --data_dir ./data --summary
"""

import sys
import os
import argparse

# Add local package directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.dataset import DatasetScanner
from src.organoid_analyzer import OrganoidAnalyzer
from src.image_processing import ImageProcessor

def main():
    parser = argparse.ArgumentParser(description="Organoid Microscopy Image Explorer CLI")
    parser.add_argument("--data_dir", type=str, default="data", help="Path to data directory")
    parser.add_argument("--summary", action="store_true", help="Print summary table of all images")
    parser.add_argument("--analyze", type=str, default=None, help="Path to a specific image to analyze green dye")
    args = parser.parse_args()

    scanner = DatasetScanner(args.data_dir)
    print("=" * 60)
    print("      HEIDELBERG ORGANOID MICROSCOPY DATASET EXPLORER     ")
    print("=" * 60)

    images = scanner.get_all_images()
    print(f"[*] Found {len(images)} microscopic TIFF images in '{args.data_dir}'\n")

    folder_map = scanner.scan_directories()
    for folder, files in folder_map.items():
        print(f"📁 Folder: {folder} ({len(files)} files)")
        for f in files:
            meta = scanner.parse_filename_metadata(f)
            print(f"   └── 📄 {meta['filename']} | Sample: {meta['sample_type']} | Cond: {meta['condition']} | ID: {meta['sample_id']}")

    if args.summary or not args.analyze:
        print("\n" + "=" * 60)
        print("SUMMARY TABLE:")
        print("=" * 60)
        df_summary = scanner.get_image_summary_table()
        print(df_summary.to_string(index=False))

    if args.analyze:
        print("\n" + "=" * 60)
        print(f"GREEN DYE ANALYSIS FOR: {args.analyze}")
        print("=" * 60)
        img, arr = scanner.load_image(args.analyze)
        r, g, b = ImageProcessor.extract_channels(arr)
        analyzer = OrganoidAnalyzer()
        labels, df_props, overlay = analyzer.detect_dead_organoids_threshold(g)
        stats = analyzer.get_summary_statistics(df_props, g)
        
        print("\n📊 Statistics Summary:")
        for k, v in stats.items():
            print(f"  • {k}: {v}")

if __name__ == "__main__":
    main()
