#!/usr/bin/env python3
"""
Full Dataset Batch Analyzer Script
Processes all 18 microscopic TIFF images in the dataset (`BK52`, `M3`, `ORG166`).
Extracts Cellpose organoid viability, NK Red cell pixels, Orange pixels, and per-organoid features.
Saves batch summary to JSON & CSV for instant Web UI comparison.

Usage:
    python scripts/run_full_dataset_batch.py
"""

import sys
import os
import json
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append('/home/mrtemroztrk/.local/lib/python3.14/site-packages')

from src.dataset import DatasetScanner
from src.organoid_analyzer import OrganoidAnalyzer

def main():
    print("=" * 70)
    print("      HEIDELBERG FULL DATASET BATCH ANALYZER (ALL 18 IMAGES)     ")
    print("=" * 70)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scanner = DatasetScanner(os.path.join(base_dir, "data"))
    images = scanner.get_all_images()
    print(f"[*] Found {len(images)} images to process.")

    analyzer = OrganoidAnalyzer()
    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    summary_records = []
    all_organoid_features = []

    for idx, img_path in enumerate(images, 1):
        filename = os.path.basename(img_path)
        meta = scanner.parse_filename_metadata(img_path)
        print(f"\n[{idx}/{len(images)}] Processing: {filename} ({meta['folder']})")

        _, arr = scanner.load_image(img_path)

        # 1. Cellpose Organoid Viability & Object Features
        viability_summary, _, df_features = analyzer.extract_organoid_features(arr)
        if not df_features.empty:
            df_features['filename'] = filename
            df_features['folder'] = meta['folder']
            df_features['sample_type'] = meta['sample_type']
            df_features['condition'] = meta['condition']
            all_organoid_features.append(df_features)

        # 2. Red NK Cell Pixels
        nk_results, _ = analyzer.quantify_red_nk_cells(arr)

        # 3. Orange Fluorescent Pixels
        orange_results, _ = analyzer.quantify_orange_pixels(arr)

        # Compute organoid averages
        avg_area = round(float(df_features['Area_px'].mean()), 1) if not df_features.empty else 0.0
        avg_circ = round(float(df_features['Circularity'].mean()), 3) if not df_features.empty else 0.0
        avg_roughness = round(float(df_features['Contour_Roughness'].mean()), 3) if not df_features.empty else 1.0

        record = {
            'filename': str(filename),
            'filepath': str(img_path),
            'folder': str(meta['folder']),
            'sample_type': str(meta['sample_type']),
            'condition': str(meta['condition']),
            'sample_id': str(meta['sample_id']),
            'total_organoids': int(viability_summary['total_organoid_count']),
            'dead_organoids': int(viability_summary['dead_organoid_count']),
            'live_organoids': int(viability_summary['live_organoid_count']),
            'mortality_rate_percent': float(viability_summary['mortality_rate_percent']),
            'avg_organoid_area_px': float(avg_area),
            'avg_circularity': float(avg_circ),
            'avg_contour_roughness': float(avg_roughness),
            'nk_red_pixel_count': int(nk_results['red_pixel_count']),
            'nk_red_coverage_percent': float(nk_results['red_coverage_percent']),
            'mean_red_intensity': float(nk_results['mean_red_intensity']),
            'orange_pixel_count': int(orange_results['orange_pixel_count']),
            'orange_coverage_percent': float(orange_results['orange_coverage_percent']),
            'mean_orange_intensity': float(orange_results['mean_orange_intensity'])
        }
        summary_records.append(record)

        print(f"  └── 🤖 Total Organoids: {record['total_organoids']} | Dead: {record['dead_organoids']} | Live: {record['live_organoids']} ({record['mortality_rate_percent']}% Mortality)")
        print(f"  └── 🔴 NK Red Pixels: {record['nk_red_pixel_count']:,} px ({record['nk_red_coverage_percent']}%)")
        print(f"  └── 🟠 Orange Pixels: {record['orange_pixel_count']:,} px ({record['orange_coverage_percent']}%)")

    # Save Batch Summary
    df_summary = pd.DataFrame(summary_records)
    csv_path = os.path.join(output_dir, "dataset_batch_summary.csv")
    json_path = os.path.join(output_dir, "dataset_batch_results.json")
    
    df_summary.to_csv(csv_path, index=False)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(summary_records, f, indent=2)

    # Save All Organoid Features Combined
    if all_organoid_features:
        df_all_features = pd.concat(all_organoid_features, ignore_index=True)
        all_features_csv = os.path.join(output_dir, "all_organoid_features.csv")
        df_all_features.to_csv(all_features_csv, index=False)
        print(f"\n[*] Extracted features for total {len(df_all_features)} organoid objects across dataset!")

    print("\n" + "=" * 70)
    print(f"✅ BATCH ANALYSIS COMPLETE!")
    print(f"  └── Batch Summary CSV: {csv_path}")
    print(f"  └── Batch Summary JSON: {json_path}")
    print("=" * 70)

if __name__ == "__main__":
    main()
