import sys
import os
import io
import json
import base64
import cv2
import numpy as np
import pandas as pd
from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
if '/home/mrtemroztrk/.local/lib/python3.14/site-packages' not in sys.path:
    sys.path.append('/home/mrtemroztrk/.local/lib/python3.14/site-packages')

from src.dataset import DatasetScanner
from src.image_processing import ImageProcessor
from src.organoid_analyzer import OrganoidAnalyzer

app = FastAPI(title="Heidelberg Organoid & Cell Analysis Workbench", version="5.4.0")

BASE_DIR = "/home/mrtemroztrk/Projects/Heidelberg/JX"
scanner = DatasetScanner(os.path.join(BASE_DIR, "data"))
analyzer = OrganoidAnalyzer()

static_dir = os.path.join(BASE_DIR, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Fast In-Memory Caching for Images & Overlays to guarantee instant response (<50ms)
RAW_ARR_CACHE = {}
OVERLAY_CACHE = {}
SESSION_DF_CACHE = {}

def get_cached_raw_image(abs_path: str):
    """Loads and caches raw RGB image array in memory."""
    if abs_path not in RAW_ARR_CACHE:
        _, arr = scanner.load_image(abs_path)
        RAW_ARR_CACHE[abs_path] = arr
    return RAW_ARR_CACHE[abs_path]

@app.get("/", response_class=HTMLResponse)
def index():
    html_path = os.path.join(static_dir, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Server starting... Please refresh page.</h1>"

@app.get("/api/dataset")
def get_dataset():
    """Returns dataset tree and image list with metadata."""
    folder_map = scanner.scan_directories()
    df_summary = scanner.get_image_summary_table()
    return {
        "folder_map": folder_map,
        "summary": df_summary.to_dict(orient="records")
    }

@app.get("/api/batch_results")
def get_batch_results():
    """Returns pre-cached batch analysis results for all 18 dataset images."""
    json_path = "/home/mrtemroztrk/Projects/Heidelberg/JX/output/dataset_batch_results.json"
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data:
                    return data
        except Exception as e:
            print("Error loading batch_results.json:", str(e))
    return []

@app.get("/api/image")
def get_processed_image(path: str = Query(...), mode: str = Query("original"), max_dim: int = Query(1600)):
    """Returns image with specific channel isolation instantly from memory cache."""
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        arr = get_cached_raw_image(abs_path)
        isolated = ImageProcessor.isolate_color_channel(arr, target_color=mode)

        h, w = isolated.shape[:2]
        if max(h, w) > max_dim:
            scale = max_dim / float(max(h, w))
            isolated = cv2.resize(isolated, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

        _, encoded = cv2.imencode('.jpg', cv2.cvtColor(isolated, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
        return Response(content=encoded.tobytes(), media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class AnalysisRequest(BaseModel):
    path: str
    min_green_pixels: int = 1
    force_reanalyze: bool = False

SEGMENTATION_CACHE = {}

@app.post("/api/analyze/cellpose_viability")
def analyze_cellpose_viability(req: AnalysisRequest):
    """
    Runs Cellpose ONCE per image. Threshold changes update instantly from memory cache (<5ms).
    """
    abs_path = os.path.abspath(req.path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File not found")

    arr = get_cached_raw_image(abs_path)
    orig_h, orig_w = arr.shape[:2]

    # Check if Cellpose segmentation mask is already cached in memory
    if not req.force_reanalyze and abs_path in SEGMENTATION_CACHE:
        cached_seg = SEGMENTATION_CACHE[abs_path]
        masks = cached_seg['masks']
        df_results = cached_seg['df'].copy()

        # Instantly update viability statuses in <1ms without re-running Cellpose!
        df_results['Status'] = df_results['Green_Pixel_Count'].apply(
            lambda g: "DEAD" if g >= req.min_green_pixels else "LIVE"
        )
        df_results['Status_TR'] = df_results['Status']

        total_cnt = len(df_results)
        dead_cnt = int(np.sum(df_results['Status'] == 'DEAD'))
        live_cnt = total_cnt - dead_cnt
        mortality_pct = round((dead_cnt / total_cnt * 100.0), 1) if total_cnt > 0 else 0.0

        # Recompute NK cell stats from the same image
        nk_stats = analyzer.quantify_nk_cells_plate(arr)

        summary = {
            'total_organoid_count': total_cnt,
            'dead_organoid_count': dead_cnt,
            'live_organoid_count': live_cnt,
            'mortality_rate_percent': mortality_pct,
            'from_cache': True,
            'live_nk_red_pixels': nk_stats['live_nk_red_pixels'],
            'dead_nk_orange_pixels': nk_stats['dead_nk_orange_pixels'],
            'total_nk_pixels': nk_stats['total_nk_pixels'],
            'nk_mortality_rate_percent': nk_stats['nk_mortality_rate_percent'],
            'live_nk_coverage_percent': nk_stats['live_nk_coverage_percent'],
            'dead_nk_coverage_percent': nk_stats['dead_nk_coverage_percent'],
            'original_width': orig_w,
            'original_height': orig_h
        }

        # Generate updated overlay instantly (<5ms)
        overlay = analyzer.generate_overlay_from_masks(arr, masks, min_green_pixels_threshold=req.min_green_pixels)
        OVERLAY_CACHE[(abs_path, "viability")] = overlay
        SESSION_DF_CACHE[abs_path] = {'arr': arr, 'overlay': overlay, 'df': df_results, 'summary': summary}

        return {
            "summary": summary,
            "organoids": df_results.to_dict(orient="records")
        }

    # First-time analysis: Run Cellpose AI segmentation ONCE
    summary, overlay, df_results, masks = analyzer.extract_organoid_features(
        arr, min_green_pixels_threshold=req.min_green_pixels, return_masks=True
    )
    summary['from_cache'] = False
    summary['original_width'] = orig_w
    summary['original_height'] = orig_h

    SEGMENTATION_CACHE[abs_path] = {
        'masks': masks,
        'df': df_results,
        'arr': arr
    }
    OVERLAY_CACHE[(abs_path, "viability")] = overlay
    SESSION_DF_CACHE[abs_path] = {'arr': arr, 'overlay': overlay, 'df': df_results, 'summary': summary}

    return {
        "summary": summary,
        "organoids": df_results.to_dict(orient="records")
    }

@app.get("/api/image/overlay")
def get_overlay_image(path: str = Query(...), type: str = Query("viability"), max_dim: int = Query(1600)):
    """Returns annotated overlay image instantly."""
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File not found")

    cache_key = (abs_path, type)
    if cache_key in OVERLAY_CACHE:
        overlay = OVERLAY_CACHE[cache_key]
    else:
        arr = get_cached_raw_image(abs_path)
        if type == "nk_red":
            _, overlay = analyzer.quantify_red_nk_cells(arr)
        elif type == "orange":
            _, overlay = analyzer.quantify_orange_pixels(arr)
        else:
            _, overlay, _ = analyzer.extract_organoid_features(arr)
        OVERLAY_CACHE[cache_key] = overlay

    h, w = overlay.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / float(max(h, w))
        overlay = cv2.resize(overlay, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    _, encoded = cv2.imencode('.jpg', cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return Response(content=encoded.tobytes(), media_type="image/jpeg")

class ManualAddRequest(BaseModel):
    path: str
    x: int
    y: int
    radius: int = 15
    green_threshold: float = 35.0

@app.post("/api/organoid/add_manual")
def add_manual_organoid(req: ManualAddRequest):
    """Manually adds an organoid at click coordinates (x, y)."""
    abs_path = os.path.abspath(req.path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File not found")

    if abs_path not in SESSION_DF_CACHE:
        arr = get_cached_raw_image(abs_path)
        summary, overlay, df = analyzer.extract_organoid_features(arr, min_green_intensity=int(req.green_threshold))
        SESSION_DF_CACHE[abs_path] = {'arr': arr, 'overlay': overlay, 'df': df, 'summary': summary}
        OVERLAY_CACHE[(abs_path, "viability")] = overlay
    
    session = SESSION_DF_CACHE[abs_path]
    arr = session['arr']
    df = session['df']

    h_img, w_img = arr.shape[:2]
    mask = np.zeros((h_img, w_img), dtype=np.uint8)
    cv2.circle(mask, (req.x, req.y), req.radius, 1, -1)

    area = int(np.sum(mask))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    perimeter = float(cv2.arcLength(contours[0], True)) if contours else 0.0

    eq_diameter = round(2.0 * np.sqrt(area / np.pi), 2)
    circularity = round((4.0 * np.pi * area) / (perimeter ** 2), 3) if perimeter > 0 else 1.0
    min_perimeter = 2.0 * np.sqrt(np.pi * area)
    contour_roughness = round(perimeter / min_perimeter, 3) if min_perimeter > 0 else 1.0

    r_ch, g_ch, b_ch = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    green_pixels = g_ch[mask == 1]
    red_pixels = r_ch[mask == 1]
    blue_pixels = b_ch[mask == 1]

    g_mean = round(float(np.mean(green_pixels)), 1) if len(green_pixels) > 0 else 0.0
    g_max = int(np.max(green_pixels)) if len(green_pixels) > 0 else 0
    green_dye_pixels_count = int(np.sum(green_pixels >= req.green_threshold)) if len(green_pixels) > 0 else 0
    green_dye_ratio_pct = round((green_dye_pixels_count / len(green_pixels)) * 100.0, 1) if len(green_pixels) > 0 else 0.0

    r_mean = round(float(np.mean(red_pixels)), 1) if len(red_pixels) > 0 else 0.0
    b_mean = round(float(np.mean(blue_pixels)), 1) if len(blue_pixels) > 0 else 0.0

    is_dead = (green_dye_pixels_count > 0) or (g_mean >= req.green_threshold)
    status = "DEAD" if is_dead else "LIVE"

    new_id = int(df['Organoid_ID'].max() + 1) if not df.empty else 1
    new_record = {
        'Organoid_ID': new_id,
        'Status': status,
        'Status_TR': 'ÖLÜ' if is_dead else 'CANLI',
        'Area_px': area,
        'Perimeter_px': round(perimeter, 1),
        'Eq_Diameter_px': eq_diameter,
        'Width_px': req.radius * 2,
        'Height_px': req.radius * 2,
        'Circularity': circularity,
        'Contour_Roughness': contour_roughness,
        'Solidity': 1.0,
        'Eccentricity': 0.0,
        'Green_Pixel_Count': green_dye_pixels_count,
        'Green_Dye_Coverage_Percent': green_dye_ratio_pct,
        'Green_Mean_Intensity': g_mean,
        'Green_Max_Intensity': g_max,
        'Red_Mean_Intensity': r_mean,
        'Blue_Mean_Intensity': b_mean,
        'Centroid_X': req.x,
        'Centroid_Y': req.y
    }

    df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
    session['df'] = df

    color_contour = (239, 68, 68) if is_dead else (0, 150, 255)
    cv2.circle(session['overlay'], (req.x, req.y), req.radius, color_contour, 2, cv2.LINE_AA)

    total_cnt = len(df)
    dead_cnt = int(np.sum(df['Status'] == 'DEAD'))
    live_cnt = total_cnt - dead_cnt
    mortality_pct = round((dead_cnt / total_cnt * 100.0), 1) if total_cnt > 0 else 0.0

    session['summary'] = {
        'total_organoid_count': total_cnt,
        'dead_organoid_count': dead_cnt,
        'live_organoid_count': live_cnt,
        'mortality_rate_percent': mortality_pct
    }

    return {
        "new_organoid": new_record,
        "summary": session['summary'],
        "organoids": df.to_dict(orient="records")
    }

class DeleteRequest(BaseModel):
    path: str
    organoid_id: int

@app.post("/api/organoid/delete")
def delete_organoid(req: DeleteRequest):
    """Deletes an organoid by ID."""
    abs_path = os.path.abspath(req.path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File not found")

    if abs_path not in SESSION_DF_CACHE:
        raise HTTPException(status_code=400, detail="Image session not initialized")

    session = SESSION_DF_CACHE[abs_path]
    df = session['df']
    df = df[df['Organoid_ID'] != req.organoid_id].reset_index(drop=True)
    session['df'] = df

    total_cnt = len(df)
    dead_cnt = int(np.sum(df['Status'] == 'DEAD')) if not df.empty else 0
    live_cnt = total_cnt - dead_cnt
    mortality_pct = round((dead_cnt / total_cnt * 100.0), 1) if total_cnt > 0 else 0.0

    session['summary'] = {
        'total_organoid_count': total_cnt,
        'dead_organoid_count': dead_cnt,
        'live_organoid_count': live_cnt,
        'mortality_rate_percent': mortality_pct
    }

    return {
        "deleted_id": req.organoid_id,
        "summary": session['summary'],
        "organoids": df.to_dict(orient="records")
    }

@app.get("/api/image/highlight_organoid")
def highlight_single_organoid(path: str = Query(...), organoid_id: int = Query(...), crop_pad: int = Query(70)):
    """Draws target crosshairs & crop box around selected organoid ID."""
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File not found")

    arr = get_cached_raw_image(abs_path)

    if abs_path in SEGMENTATION_CACHE:
        masks = SEGMENTATION_CACHE[abs_path]['masks']
        df = SEGMENTATION_CACHE[abs_path]['df']
    elif abs_path in SESSION_DF_CACHE:
        df = SESSION_DF_CACHE[abs_path]['df']
        masks = None
    else:
        summary, overlay, df, masks = analyzer.extract_organoid_features(arr, return_masks=True)

    row = df[df['Organoid_ID'] == organoid_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="Organoid ID not found")

    r = row.iloc[0]
    cx, cy = int(r['Centroid_X']), int(r['Centroid_Y'])
    w_obj, h_obj = int(r['Width_px']), int(r['Height_px'])
    is_dead = (r['Status'] == 'DEAD' or r.get('Status_TR') == 'ÖLÜ')

    contour_color = (192, 132, 252) if is_dead else (6, 182, 212) # Purple for Dead, Turquoise for Live
    overlay = arr.copy()

    if masks is not None and np.any(masks == organoid_id):
        mask_uint8 = (masks == organoid_id).astype(np.uint8)
        contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            cv2.drawContours(overlay, contours, -1, contour_color, 3)

    # Draw glowing gold target box around object
    top_left = (max(0, cx - w_obj // 2 - 8), max(0, cy - h_obj // 2 - 8))
    bottom_right = (min(arr.shape[1], cx + w_obj // 2 + 8), min(arr.shape[0], cy + h_obj // 2 + 8))
    cv2.rectangle(overlay, top_left, bottom_right, (255, 215, 0), 2)

    # Crop with proportional padding around organoid
    pad = max(crop_pad, max(w_obj, h_obj) // 2 + 30)
    y1, y2 = max(0, cy - pad), min(arr.shape[0], cy + pad)
    x1, x2 = max(0, cx - pad), min(arr.shape[1], cx + pad)
    crop = overlay[y1:y2, x1:x2]
    crop_resized = cv2.resize(crop, (400, 400), interpolation=cv2.INTER_NEAREST)

    _, encoded = cv2.imencode('.jpg', cv2.cvtColor(crop_resized, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 95])
    return Response(content=encoded.tobytes(), media_type="image/jpeg")

class ComparisonExportRequest(BaseModel):
    selected_files: List[str]

@app.post("/api/export_comparison_html")
def export_comparison_html(req: ComparisonExportRequest):
    """Generates a standalone HTML comparison report with embedded base64 image thumbnails."""
    json_path = "/home/mrtemroztrk/Projects/Heidelberg/JX/output/dataset_batch_results.json"
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Batch results not found.")

    with open(json_path, 'r', encoding='utf-8') as f:
        all_results = json.load(f)

    if req.selected_files:
        selected_records = [r for r in all_results if r['filename'] in req.selected_files or r['filepath'] in req.selected_files or os.path.basename(r['filepath']) in req.selected_files]
    else:
        selected_records = all_results

    if not selected_records:
        selected_records = all_results

    columns_html = []
    for r in selected_records:
        abs_p = os.path.abspath(r['filepath'])
        b64_str = ""
        if os.path.exists(abs_p):
            try:
                arr = get_cached_raw_image(abs_p)
                h, w = arr.shape[:2]
                scale = 320.0 / float(max(h, w))
                thumb = cv2.resize(arr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                _, enc = cv2.imencode('.jpg', cv2.cvtColor(thumb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
                b64_str = f"data:image/jpeg;base64,{base64.b64encode(enc).decode('utf-8')}"
            except Exception as e:
                pass

        img_tag = f"<img src='{b64_str}' style='width:180px; height:130px; object-fit:cover; border-radius:6px; border:1px solid #30363d; margin-bottom:8px;'><br>" if b64_str else ""
        columns_html.append(f"<th>{img_tag}<b>{r['filename']}</b><br><span class='tag'>{r['folder']}</span></th>")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Organoid Microscopy Comparison Report</title>
    <style>
        body {{ font-family: 'Inter', system-ui, sans-serif; background-color: #0b0e14; color: #e6edf3; padding: 24px; }}
        h1 {{ color: #ffffff; font-size: 1.6rem; margin-bottom: 6px; }}
        p {{ color: #8b949e; font-size: 0.9rem; margin-bottom: 24px; }}
        .comparison-table {{ width: 100%; border-collapse: collapse; margin-top: 16px; background-color: #121721; border-radius: 8px; overflow: hidden; }}
        .comparison-table th, .comparison-table td {{ padding: 14px 16px; border: 1px solid #212836; text-align: left; font-size: 0.85rem; }}
        .comparison-table th {{ background-color: #161b22; color: #58a6ff; font-weight: 700; width: 220px; text-align: center; }}
        .highlight {{ color: #3fb950; font-weight: 700; }}
        .stat-value {{ font-size: 1.1rem; font-weight: 700; color: #ffffff; }}
        .tag {{ background-color: #21262d; border: 1px solid #30363d; border-radius: 4px; padding: 2px 6px; font-size: 0.75rem; color: #c9d1d9; }}
    </style>
</head>
<body>
    <h1>Organoid Microscopy Multi-Image Spec Comparison Report</h1>
    <p>Generated comparison matrix with image previews for {len(selected_records)} selected sample images.</p>

    <table class="comparison-table">
        <thead>
            <tr>
                <th style="text-align:left;">FEATURE / METRIC</th>
                {''.join(columns_html)}
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><b>Sample Type</b></td>
                {''.join([f"<td><span class='tag'>{r['sample_type']}</span></td>" for r in selected_records])}
            </tr>
            <tr>
                <td><b>Treatment Condition</b></td>
                {''.join([f"<td><span class='tag'>{r['condition']}</span></td>" for r in selected_records])}
            </tr>
            <tr>
                <td><b>Sample ID</b></td>
                {''.join([f"<td>{r['sample_id']}</td>" for r in selected_records])}
            </tr>
            <tr>
                <td><b>Total Organoids (Cellpose)</b></td>
                {''.join([f"<td class='stat-value'>{r['total_organoids']:,}</td>" for r in selected_records])}
            </tr>
            <tr>
                <td><b>Dead Organoids (Green +)</b></td>
                {''.join([f"<td class='highlight'>{r['dead_organoids']:,}</td>" for r in selected_records])}
            </tr>
            <tr>
                <td><b>Live Organoids</b></td>
                {''.join([f"<td>{r['live_organoids']:,}</td>" for r in selected_records])}
            </tr>
            <tr>
                <td><b>Mortality Rate (%)</b></td>
                {''.join([f"<td class='highlight'>{r['mortality_rate_percent']}%</td>" for r in selected_records])}
            </tr>
            <tr>
                <td><b>Avg Organoid Area (px)</b></td>
                {''.join([f"<td>{r['avg_organoid_area_px']} px</td>" for r in selected_records])}
            </tr>
            <tr>
                <td><b>Avg Circularity (0-1)</b></td>
                {''.join([f"<td>{r['avg_circularity']}</td>" for r in selected_records])}
            </tr>
            <tr>
                <td><b>Avg Contour Roughness</b></td>
                {''.join([f"<td>{r['avg_contour_roughness']}</td>" for r in selected_records])}
            </tr>
            <tr>
                <td><b>NK Cell Red Pixels</b></td>
                {''.join([f"<td style='color:#f85149; font-weight:700;'>{r['nk_red_pixel_count']:,} px ({r['nk_red_coverage_percent']}%)</td>" for r in selected_records])}
            </tr>
            <tr>
                <td><b>Orange Pixels</b></td>
                {''.join([f"<td style='color:#d29922; font-weight:700;'>{r['orange_pixel_count']:,} px ({r['orange_coverage_percent']}%)</td>" for r in selected_records])}
            </tr>
        </tbody>
    </table>
</body>
</html>"""

    return Response(content=html_content, media_type="text/html", headers={"Content-Disposition": "attachment; filename=organoid_comparison_report.html"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
