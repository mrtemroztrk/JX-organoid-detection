import sys
import os
import numpy as np
import cv2
import pandas as pd
from skimage.measure import regionprops_table
from skimage.feature import blob_log
from scipy import ndimage as ndi
from skimage.segmentation import watershed
from skimage.morphology import remove_small_objects

if '/home/mrtemroztrk/.local/lib/python3.14/site-packages' not in sys.path:
    sys.path.append('/home/mrtemroztrk/.local/lib/python3.14/site-packages')

try:
    import torch
    from cellpose import models as cp_models
    CELLPOSE_AVAILABLE = True
except Exception as e:
    CELLPOSE_AVAILABLE = False
    print("Cellpose load info:", e)

try:
    import omnipose
    OMNIPOSE_AVAILABLE = True
except Exception:
    OMNIPOSE_AVAILABLE = False


class OrganoidAnalyzer:

    def __init__(self):
        self.cp_model = None
        self._gpu_oom = False

    def load_segmentation_model(self, model_type: str = 'cyto3', prefer_omnipose: bool = False):
        if not CELLPOSE_AVAILABLE:
            raise RuntimeError("Cellpose/Omnipose package is not available.")

        if self.cp_model is not None:
            return self.cp_model

        use_gpu = torch.cuda.is_available() and not self._gpu_oom
        if use_gpu:
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass

        cpmod = cp_models

        if OMNIPOSE_AVAILABLE and prefer_omnipose and model_type in ('bact_omni', 'bact_phase', 'bact_fluor'):
            print(f"[*] Using Omnipose model '{model_type}' (GPU: {use_gpu})...")

        print(f"[*] Initializing Cellpose model '{model_type}' (GPU: {use_gpu})...")

        kw = dict(gpu=use_gpu, model_type=model_type)
        if hasattr(cpmod, 'CellposeModel'):
            model_class = cpmod.CellposeModel
        else:
            model_class = cpmod.Cellpose

        try:
            self.cp_model = model_class(**kw)
        except Exception as e:
            print(f"[!] GPU init failed ({e}). Falling back to CPU...")
            kw['gpu'] = False
            self.cp_model = model_class(**kw)

        return self.cp_model

    def _segment_with_fallback(self, img_green: np.ndarray, diameter: float = 60.0,
                                model_type: str = 'cyto3') -> np.ndarray:
        h, w = img_green.shape[:2]
        scale = 1.0
        if max(h, w) > 1200:
            scale = 1200.0 / float(max(h, w))
            img_eval = cv2.resize(img_green, (int(w * scale), int(h * scale)),
                                  interpolation=cv2.INTER_AREA)
        else:
            img_eval = img_green

        if img_eval.ndim == 2:
            img_eval = np.stack([img_eval] * 3, axis=-1)
        elif img_eval.shape[2] > 3:
            img_eval = img_eval[:, :, :3]

        model = self.load_segmentation_model(model_type=model_type)

        try:
            with torch.no_grad():
                eval_res = model.eval(img_eval, diameter=diameter, channels=[0, 0])
        except Exception as e:
            if "out of memory" in str(e).lower():
                print("[!] CUDA OOM. Switching to CPU and smaller model...")
                self._gpu_oom = True
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                self.cp_model = None
                model = self.load_segmentation_model(model_type='cyto2', prefer_omnipose=False)
                with torch.no_grad():
                    eval_res = model.eval(img_eval, diameter=diameter, channels=[0, 0])
            else:
                print(f"[!] Cellpose eval error: {e}. Falling back to threshold segmentation.")
                return None

        masks_small = eval_res[0] if isinstance(eval_res, (tuple, list)) else eval_res
        if scale != 1.0:
            masks = cv2.resize(masks_small, (w, h), interpolation=cv2.INTER_NEAREST)
        else:
            masks = masks_small

        return masks

    def extract_organoid_features(self, img_rgb: np.ndarray,
                                  min_green_pixels_threshold: int = 1,
                                  min_green_intensity: int = 10,
                                  diameter: float = None,
                                  model_type: str = 'cyto3',
                                  return_masks: bool = False):
        masks = self._segment_with_fallback(img_rgb, diameter=diameter or 60.0,
                                            model_type=model_type)
        if masks is None:
            g_ch = img_rgb[:, :, 1]
            masks = self._threshold_fallback(g_ch)
            if masks is None:
                res = (
                    {'total_organoid_count': 0, 'dead_organoid_count': 0,
                     'live_organoid_count': 0, 'mortality_rate_percent': 0.0},
                    img_rgb.copy(),
                    pd.DataFrame()
                )
                return res + (None,) if return_masks else res

        total_count = int(masks.max())
        overlay = img_rgb.copy()
        records = []
        dead_count = 0
        live_count = 0

        r_ch, g_ch, b_ch = img_rgb[:, :, 0], img_rgb[:, :, 1], img_rgb[:, :, 2]

        if total_count > 0:
            props = regionprops_table(masks, intensity_image=g_ch,
                                      properties=('label', 'area', 'perimeter', 'solidity',
                                                  'eccentricity', 'convex_area'))
            df_props = pd.DataFrame(props)

            for organoid_id in range(1, total_count + 1):
                mask_id = (masks == organoid_id)
                mask_uint8 = mask_id.astype(np.uint8)
                area = int(np.sum(mask_id))
                if area < 5:
                    continue

                prop_row = (df_props[df_props['label'] == organoid_id].iloc[0]
                            if not df_props.empty and organoid_id in df_props['label'].values
                            else None)

                contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL,
                                               cv2.CHAIN_APPROX_SIMPLE)
                perimeter = float(cv2.arcLength(contours[0], True)) if contours else 0.0
                eq_diameter = round(2.0 * np.sqrt(area / np.pi), 2)
                x, y, w_box, h_box = cv2.boundingRect(contours[0]) if contours else (0, 0, 0, 0)

                circularity = round((4.0 * np.pi * area) / (perimeter ** 2), 3) if perimeter > 0 else 0.0
                min_perimeter = 2.0 * np.sqrt(np.pi * area)
                contour_roughness = round(perimeter / min_perimeter, 3) if min_perimeter > 0 else 1.0
                solidity = round(float(prop_row['solidity']), 3) if prop_row is not None else 1.0
                eccentricity = round(float(prop_row['eccentricity']), 3) if prop_row is not None else 0.0

                green_pixels = g_ch[mask_id]
                red_pixels = r_ch[mask_id]
                blue_pixels = b_ch[mask_id]

                # True Green Dye Pixels: Green channel must be >= threshold AND dominant over Red & Blue!
                true_green_mask = (green_pixels >= max(20, min_green_intensity)) & \
                                  (green_pixels.astype(np.int16) > red_pixels.astype(np.int16) + 12) & \
                                  (green_pixels.astype(np.int16) > blue_pixels.astype(np.int16) + 12)
                green_dye_pixels_count = int(np.sum(true_green_mask))

                green_dye_ratio_pct = round(
                    (green_dye_pixels_count / len(green_pixels)) * 100.0, 1
                ) if len(green_pixels) > 0 else 0.0

                g_mean = round(float(np.mean(green_pixels)), 1) if len(green_pixels) > 0 else 0.0
                g_max = int(np.max(green_pixels)) if len(green_pixels) > 0 else 0
                r_mean = round(float(np.mean(red_pixels)), 1) if len(red_pixels) > 0 else 0.0
                b_mean = round(float(np.mean(blue_pixels)), 1) if len(blue_pixels) > 0 else 0.0

                is_dead = (green_dye_pixels_count >= min_green_pixels_threshold)
                if is_dead:
                    dead_count += 1
                    status, status_tr = "DEAD", "DEAD"
                    contour_color = (192, 132, 252)  # Bright Purple/Magenta for Dead
                else:
                    live_count += 1
                    status, status_tr = "LIVE", "LIVE"
                    contour_color = (6, 182, 212)    # Vibrant Turquoise/Cyan for Live

                cv2.drawContours(overlay, contours, -1, contour_color, 2)

                records.append({
                    'Organoid_ID': organoid_id,
                    'Status': status,
                    'Status_TR': status_tr,
                    'Area_px': area,
                    'Perimeter_px': round(perimeter, 1),
                    'Eq_Diameter_px': eq_diameter,
                    'Width_px': w_box,
                    'Height_px': h_box,
                    'Circularity': circularity,
                    'Contour_Roughness': contour_roughness,
                    'Solidity': solidity,
                    'Eccentricity': eccentricity,
                    'Green_Pixel_Count': green_dye_pixels_count,
                    'Green_Dye_Coverage_Percent': green_dye_ratio_pct,
                    'Green_Mean_Intensity': g_mean,
                    'Green_Max_Intensity': g_max,
                    'Red_Mean_Intensity': r_mean,
                    'Blue_Mean_Intensity': b_mean,
                    'Centroid_X': x + w_box // 2,
                    'Centroid_Y': y + h_box // 2
                })

        mortality_rate = round((dead_count / total_count * 100.0), 1) if total_count > 0 else 0.0

        # Plate-level Natural Killer (NK) Cell Population & Viability (Live Red vs Dead Orange)
        nk_stats = self.quantify_nk_cells_plate(img_rgb)

        summary = {
            'total_organoid_count': total_count,
            'dead_organoid_count': dead_count,
            'live_organoid_count': live_count,
            'mortality_rate_percent': mortality_rate,
            'live_nk_red_pixels': nk_stats['live_nk_red_pixels'],
            'dead_nk_orange_pixels': nk_stats['dead_nk_orange_pixels'],
            'total_nk_pixels': nk_stats['total_nk_pixels'],
            'nk_mortality_rate_percent': nk_stats['nk_mortality_rate_percent'],
            'live_nk_coverage_percent': nk_stats['live_nk_coverage_percent'],
            'dead_nk_coverage_percent': nk_stats['dead_nk_coverage_percent']
        }
        res = (summary, overlay, pd.DataFrame(records))
        return res + (masks,) if return_masks else res

    def quantify_nk_cells_plate(self, img_rgb: np.ndarray) -> dict:
        """
        Quantifies Live NK Cells (Red Pixels) vs Dead NK Cells (Orange Pixels) across the entire plate field-of-view.
        """
        r_ch = img_rgb[:, :, 0].astype(np.int16)
        g_ch = img_rgb[:, :, 1].astype(np.int16)
        b_ch = img_rgb[:, :, 2].astype(np.int16)

        total_pixels = img_rgb.shape[0] * img_rgb.shape[1]

        # Live NK Cells: Red fluorescence channel dominance over Green and Blue
        live_nk_red_mask = (r_ch >= 40) & (r_ch > g_ch + 15) & (r_ch > b_ch + 15)
        live_nk_red_count = int(np.sum(live_nk_red_mask))

        # Dead NK Cells: Orange fluorescence (High Red + Medium Green, low Blue)
        dead_nk_orange_mask = (r_ch >= 40) & (g_ch >= 25) & (r_ch > b_ch + 20) & (np.abs(r_ch - g_ch) < 70)
        dead_nk_orange_count = int(np.sum(dead_nk_orange_mask))

        total_nk_pixels = live_nk_red_count + dead_nk_orange_count
        nk_mortality_rate = round((dead_nk_orange_count / total_nk_pixels * 100.0), 1) if total_nk_pixels > 0 else 0.0

        live_nk_coverage_pct = round((live_nk_red_count / total_pixels) * 100.0, 2)
        dead_nk_coverage_pct = round((dead_nk_orange_count / total_pixels) * 100.0, 2)

        return {
            'live_nk_red_pixels': live_nk_red_count,
            'dead_nk_orange_pixels': dead_nk_orange_count,
            'total_nk_pixels': total_nk_pixels,
            'nk_mortality_rate_percent': nk_mortality_rate,
            'live_nk_coverage_percent': live_nk_coverage_pct,
            'dead_nk_coverage_percent': dead_nk_coverage_pct
        }

    def generate_overlay_from_masks(self, img_rgb: np.ndarray, masks: np.ndarray,
                                       min_green_pixels_threshold: int = 1,
                                       min_green_intensity: int = 10) -> np.ndarray:
        """
        Generates annotated overlay image instantly from pre-segmented Cellpose mask (<5ms).
        Outlines DEAD organoids in PURPLE and LIVE organoids in TURQUOISE.
        """
        overlay = img_rgb.copy()
        if masks is None or masks.max() == 0:
            return overlay

        r_ch = img_rgb[:, :, 0]
        g_ch = img_rgb[:, :, 1]
        b_ch = img_rgb[:, :, 2]
        total_count = int(masks.max())

        for organoid_id in range(1, total_count + 1):
            mask_id = (masks == organoid_id)
            if not np.any(mask_id):
                continue

            green_pixels = g_ch[mask_id]
            red_pixels = r_ch[mask_id]
            blue_pixels = b_ch[mask_id]

            true_green_mask = (green_pixels >= max(20, min_green_intensity)) & \
                              (green_pixels.astype(np.int16) > red_pixels.astype(np.int16) + 12) & \
                              (green_pixels.astype(np.int16) > blue_pixels.astype(np.int16) + 12)
            green_dye_pixels_count = int(np.sum(true_green_mask))

            is_dead = (green_dye_pixels_count >= min_green_pixels_threshold)

            contour_color = (192, 132, 252) if is_dead else (6, 182, 212) # Purple for Dead, Turquoise for Live
            mask_uint8 = mask_id.astype(np.uint8)
            contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                cv2.drawContours(overlay, contours, -1, contour_color, 2)

        return overlay

    def analyze_organoid_viability_cellpose(self, img_rgb: np.ndarray,
                                            min_green_pixels_threshold: int = 1,
                                            min_green_intensity: int = 10,
                                            diameter: float = None,
                                            model_type: str = 'cyto3'):
        return self.extract_organoid_features(
            img_rgb,
            min_green_pixels_threshold=min_green_pixels_threshold,
            min_green_intensity=min_green_intensity,
            diameter=diameter,
            model_type=model_type
        )

    def detect_dead_organoids_threshold(self, green_channel: np.ndarray,
                                         intensity_threshold: int = 55,
                                         min_area: int = 25,
                                         max_area: int = 15000,
                                         min_circularity: float = 0.15,
                                         use_watershed: bool = True,
                                         tophat_kernel: int = 15):
        orig_h, orig_w = green_channel.shape
        scale = 1.0
        if max(orig_h, orig_w) > 1200:
            scale = 1200.0 / float(max(orig_h, orig_w))
            g_small = cv2.resize(green_channel, (int(orig_w * scale), int(orig_h * scale)),
                                 interpolation=cv2.INTER_AREA)
        else:
            g_small = green_channel

        if tophat_kernel > 0:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (tophat_kernel, tophat_kernel))
            g_small = cv2.morphologyEx(g_small, cv2.MORPH_TOPHAT, k)

        _, binary = cv2.threshold(g_small, intensity_threshold, 255, cv2.THRESH_BINARY)
        binary = binary.astype(np.uint8)

        if use_watershed:
            dist = cv2.distanceTransform(binary, cv2.DIST_L2, 3)
            dist_norm = cv2.normalize(dist, None, 0, 1.0, cv2.NORM_MINMAX)
            _, markers = cv2.threshold(dist_norm, 0.3, 255, cv2.THRESH_BINARY)
            markers = ndi.label(markers.astype(int))[0]
            mask = watershed(-dist, markers, mask=binary.astype(bool))
            label_mask_small = mask.astype(np.int32)
        else:
            label_mask_small, _ = ndi.label(binary.astype(bool))

        if scale != 1.0:
            label_mask = cv2.resize(label_mask_small.astype(np.float32), (orig_w, orig_h),
                                    interpolation=cv2.INTER_NEAREST).astype(np.int32)
        else:
            label_mask = label_mask_small

        props = regionprops_table(label_mask, intensity_image=green_channel,
                                  properties=('label', 'area', 'perimeter', 'solidity',
                                              'eccentricity', 'convex_area', 'centroid'))
        df = pd.DataFrame(props)

        if df.empty:
            return label_mask, df, np.stack([green_channel] * 3, axis=-1)

        if len(df) > 0:
            areas = df['area'].values
            perims = df['perimeter'].values
            circs = np.where(perims > 0, (4 * np.pi * areas) / (perims ** 2), 0.0)
            valid = (areas >= min_area) & (areas <= max_area) & (circs >= min_circularity)
            df = df.iloc[np.where(valid)[0]].copy()

        filtered_labels = set(df['label'].values)
        label_mask_filtered = np.zeros_like(label_mask)
        for lbl in filtered_labels:
            label_mask_filtered[label_mask == lbl] = lbl

        overlay = np.stack([green_channel] * 3, axis=-1).astype(np.uint8)
        records = []
        g_ch = green_channel

        for _, row in df.iterrows():
            lbl = int(row['label'])
            mask_id = (label_mask == lbl)
            mask_uint8 = mask_id.astype(np.uint8)
            area = int(row['area'])
            perimeter = float(row['perimeter']) if row['perimeter'] else 0.0
            eq_diameter = round(2.0 * np.sqrt(area / np.pi), 2)

            contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                x, y, w_box, h_box = cv2.boundingRect(contours[0])
                M = cv2.moments(mask_uint8)
                cx = int(M["m10"] / M["m00"]) if M["m00"] > 0 else x + w_box // 2
                cy = int(M["m01"] / M["m00"]) if M["m00"] > 0 else y + h_box // 2

                green_pixels = g_ch[mask_id]
                green_dye_count = int(np.sum(green_pixels >= intensity_threshold))
                green_dye_ratio = round((green_dye_count / len(green_pixels)) * 100.0, 1) if len(green_pixels) > 0 else 0.0
                g_mean = round(float(np.mean(green_pixels)), 1) if len(green_pixels) > 0 else 0.0
                g_max = int(np.max(green_pixels)) if len(green_pixels) > 0 else 0

                is_dead = green_dye_count > 0
                color = (239, 68, 68) if is_dead else (0, 150, 255)
                cv2.drawContours(overlay, contours, -1, color, 2)
                status = "DEAD" if is_dead else "LIVE"
                status_tr = "DEAD" if is_dead else "LIVE"

                records.append({
                    'Organoid_ID': lbl, 'Status': status, 'Status_TR': status_tr,
                    'Area_px': area, 'Perimeter_px': round(perimeter, 1),
                    'Eq_Diameter_px': eq_diameter, 'Width_px': w_box, 'Height_px': h_box,
                    'Circularity': round((4 * np.pi * area) / (perimeter ** 2), 3) if perimeter > 0 else 0.0,
                    'Contour_Roughness': round(perimeter / (2 * np.sqrt(np.pi * area)), 3) if area > 0 else 1.0,
                    'Solidity': round(float(row['solidity']), 3), 'Eccentricity': round(float(row['eccentricity']), 3),
                    'Green_Pixel_Count': green_dye_count,
                    'Green_Dye_Coverage_Percent': green_dye_ratio,
                    'Green_Mean_Intensity': g_mean, 'Green_Max_Intensity': g_max,
                    'Red_Mean_Intensity': round(float(np.mean(overlay[:, :, 0][mask_id])), 1) if area > 0 else 0.0,
                    'Blue_Mean_Intensity': round(float(np.mean(overlay[:, :, 2][mask_id])), 1) if area > 0 else 0.0,
                    'Centroid_X': cx, 'Centroid_Y': cy
                })

        return label_mask_filtered, pd.DataFrame(records), overlay

    def detect_blobs_log(self, green_channel: np.ndarray,
                          min_sigma: float = 2.0,
                          max_sigma: float = 15.0,
                          threshold: float = 0.05):
        blobs = blob_log(green_channel, min_sigma=min_sigma, max_sigma=max_sigma,
                         threshold=threshold)
        overlay = np.stack([green_channel] * 3, axis=-1).astype(np.uint8)
        records = []

        for i, (y, x, r) in enumerate(blobs):
            radius = int(r * np.sqrt(2))
            cv2.circle(overlay, (int(x), int(y)), radius, (192, 38, 211), 2)
            cv2.circle(overlay, (int(x), int(y)), 2, (236, 72, 153), -1)

            y0, y1 = max(0, int(y) - radius), min(green_channel.shape[0], int(y) + radius)
            x0, x1 = max(0, int(x) - radius), min(green_channel.shape[1], int(x) + radius)
            mask_patch = np.zeros_like(green_channel, dtype=bool)
            YY, XX = np.ogrid[y0:y1, x0:x1]
            dist_mask = ((YY - int(y)) ** 2 + (XX - int(x)) ** 2) <= radius ** 2
            mask_patch[y0:y1, x0:x1] = dist_mask
            area = int(np.sum(mask_patch))

            green_pixels = green_channel[mask_patch]
            g_mean = round(float(np.mean(green_pixels)), 1) if len(green_pixels) > 0 else 0.0
            g_max = int(np.max(green_pixels)) if len(green_pixels) > 0 else 0
            green_dye_count = int(np.sum(green_pixels >= 55))
            is_dead = green_dye_count > 0

            records.append({
                'Organoid_ID': i + 1,
                'Status': 'DEAD' if is_dead else 'LIVE',
                'Status_TR': 'ÖLÜ' if is_dead else 'CANLI',
                'Area_px': area,
                'Eq_Diameter_px': round(radius * 2, 2),
                'Green_Pixel_Count': green_dye_count,
                'Green_Mean_Intensity': g_mean,
                'Green_Max_Intensity': g_max,
                'Centroid_X': int(x),
                'Centroid_Y': int(y)
            })

        return pd.DataFrame(records), overlay

    def get_summary_statistics(self, df_organoids: pd.DataFrame,
                                green_channel: np.ndarray):
        if df_organoids.empty:
            return {
                'detected_organoid_count': 0,
                'total_dead_organoid_area_px': 0,
                'area_coverage_percent': '0.00',
                'avg_organoid_green_intensity': '0.0'
            }

        total_px = green_channel.shape[0] * green_channel.shape[1]
        total_area = int(df_organoids['Area_px'].sum()) if 'Area_px' in df_organoids.columns else 0
        coverage = round((total_area / total_px) * 100.0, 2) if total_px > 0 else 0.0
        avg_green = round(float(df_organoids['Green_Mean_Intensity'].mean()), 1) if 'Green_Mean_Intensity' in df_organoids.columns else 0.0

        return {
            'detected_organoid_count': len(df_organoids),
            'total_dead_organoid_area_px': total_area,
            'area_coverage_percent': f'{coverage:.2f}',
            'avg_organoid_green_intensity': f'{avg_green:.1f}'
        }

    def _threshold_fallback(self, green_channel: np.ndarray) -> np.ndarray:
        binary = cv2.adaptiveThreshold(green_channel, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 31, 2)
        kernel = np.ones((3, 3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
        label_mask, _ = ndi.label(binary.astype(bool))
        label_mask = remove_small_objects(label_mask, min_size=25)
        return label_mask.astype(np.int32)

    def quantify_red_nk_cells(self, img_rgb: np.ndarray, min_saturation: int = 40, min_value: int = 30):
        hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
        mask1 = cv2.inRange(hsv, np.array([0, min_saturation, min_value]), np.array([12, 255, 255]))
        mask2 = cv2.inRange(hsv, np.array([160, min_saturation, min_value]), np.array([180, 255, 255]))
        red_mask = cv2.bitwise_or(mask1, mask2)

        total_pixels = img_rgb.shape[0] * img_rgb.shape[1]
        red_pixel_count = int(np.count_nonzero(red_mask))
        red_coverage_pct = round((red_pixel_count / total_pixels) * 100.0, 3)

        red_channel = img_rgb[:, :, 0]
        mean_red_intensity = float(np.mean(red_channel[red_mask > 0])) if red_pixel_count > 0 else 0.0

        overlay = img_rgb.copy()
        overlay[red_mask > 0] = [255, 0, 128]

        results = {
            'red_pixel_count': red_pixel_count,
            'red_coverage_percent': red_coverage_pct,
            'mean_red_intensity': round(mean_red_intensity, 1),
            'total_field_pixels': total_pixels
        }
        return results, overlay

    def quantify_orange_pixels(self, img_rgb: np.ndarray, min_saturation: int = 40, min_value: int = 30):
        hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
        orange_mask = cv2.inRange(hsv, np.array([10, min_saturation, min_value]), np.array([32, 255, 255]))

        total_pixels = img_rgb.shape[0] * img_rgb.shape[1]
        orange_pixel_count = int(np.count_nonzero(orange_mask))
        orange_coverage_pct = round((orange_pixel_count / total_pixels) * 100.0, 3)

        green_ch = img_rgb[:, :, 1].astype(np.float32)
        red_ch = img_rgb[:, :, 0].astype(np.float32)
        orange_intensity = (green_ch + red_ch) / 2.0
        mean_orange_intensity = float(np.mean(orange_intensity[orange_mask > 0])) if orange_pixel_count > 0 else 0.0

        overlay = img_rgb.copy()
        overlay[orange_mask > 0] = [255, 165, 0]

        results = {
            'orange_pixel_count': orange_pixel_count,
            'orange_coverage_percent': orange_coverage_pct,
            'mean_orange_intensity': round(mean_orange_intensity, 1),
            'total_field_pixels': total_pixels
        }
        return results, overlay
