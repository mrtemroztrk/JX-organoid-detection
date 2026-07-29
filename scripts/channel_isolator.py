#!/usr/bin/env python3
"""
Microscopy Channel Isolator Script
Generates isolated target color views (Green, Red, Orange) with desaturated dimmed background.

Usage:
    python scripts/channel_isolator.py --image "data/BK52 single image/Overlay_BK52_9806_BGR.tif"
"""

import sys
import os
import argparse
import cv2

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append('/home/mrtemroztrk/.local/lib/python3.14/site-packages')

from src.dataset import DatasetScanner
from src.image_processing import ImageProcessor

def main():
    parser = argparse.ArgumentParser(description="Microscopy Channel Isolation Tool")
    parser.add_argument("--image", type=str, required=True, help="Path to input TIF image")
    parser.add_argument("--output_dir", type=str, default="output/channels", help="Output directory")
    args = parser.parse_args()

    scanner = DatasetScanner()
    _, arr = scanner.load_image(args.image)
    filename = os.path.basename(args.image)

    os.makedirs(args.output_dir, exist_ok=True)
    print(f"[*] Processing channel isolations for: {args.image}")

    modes = ['green', 'red', 'orange', 'original']
    for mode in modes:
        isolated = ImageProcessor.isolate_color_channel(arr, target_color=mode)
        out_path = os.path.join(args.output_dir, f"{os.path.splitext(filename)[0]}_{mode}.jpg")
        cv2.imwrite(out_path, cv2.cvtColor(isolated, cv2.COLOR_RGB2BGR))
        print(f"  └── Saved {mode.upper()} isolated view to: {out_path}")

if __name__ == "__main__":
    main()
