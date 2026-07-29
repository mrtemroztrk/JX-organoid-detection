import os
import glob
from PIL import Image
import numpy as np
import pandas as pd

class DatasetScanner:
    """
    Scans and manages organoid microscopic TIFF image dataset.
    """
    def __init__(self, data_dir: str = "data"):
        self.data_dir = os.path.abspath(data_dir)

    def scan_directories(self):
        """Returns map of folder names to list of image file paths."""
        if not os.path.exists(self.data_dir):
            return {}
        
        folder_map = {}
        for root, dirs, files in os.walk(self.data_dir):
            tif_files = [f for f in files if f.lower().endswith(('.tif', '.tiff'))]
            if tif_files:
                rel_folder = os.path.relpath(root, self.data_dir)
                folder_name = "Root" if rel_folder == "." else rel_folder
                folder_map[folder_name] = sorted([os.path.join(root, f) for f in tif_files])
        return folder_map

    def get_all_images(self):
        """Returns flat list of all tif image paths."""
        return sorted(glob.glob(os.path.join(self.data_dir, "**/*.tif"), recursive=True))

    def parse_filename_metadata(self, filepath: str):
        """
        Parses metadata embedded in the filename.
        e.g., Overlay_BK52_CEA_9805_BGR.tif -> Sample: BK52, Treatment: CEA, Marker: 9805, Channels: BGR
        """
        filename = os.path.basename(filepath)
        name_no_ext = os.path.splitext(filename)[0]
        tokens = name_no_ext.split('_')
        
        metadata = {
            'filename': filename,
            'path': filepath,
            'folder': os.path.basename(os.path.dirname(filepath)),
            'sample_type': 'Unknown',
            'condition': 'Control/Standard',
            'sample_id': '-',
            'channels_hint': 'BGR'
        }
        
        for token in tokens:
            if token in ['BK52', 'M3', 'ORG166']:
                metadata['sample_type'] = token
            elif token in ['CEA', 'WT', 'BK']:
                metadata['condition'] = token
            elif token in ['9805', '9806']:
                metadata['sample_id'] = token
            elif token in ['BGR', 'BG']:
                metadata['channels_hint'] = token
                
        return metadata

    def get_image_summary_table(self):
        """Generates a summary DataFrame of all images in the dataset."""
        images = self.get_all_images()
        records = []
        for img_path in images:
            meta = self.parse_filename_metadata(img_path)
            try:
                with Image.open(img_path) as img:
                    width, height = img.size
                    mode = img.mode
                    file_size_mb = round(os.path.getsize(img_path) / (1024 * 1024), 2)
                    meta['resolution'] = f"{width} x {height}"
                    meta['mode'] = mode
                    meta['size_mb'] = file_size_mb
            except Exception as e:
                meta['resolution'] = "Error"
                meta['mode'] = "Error"
                meta['size_mb'] = 0
            records.append(meta)
        return pd.DataFrame(records)

    def load_image(self, filepath: str):
        """
        Loads TIFF image as numpy array (RGB/uint8).
        """
        img = Image.open(filepath)
        arr = np.array(img)
        return img, arr
