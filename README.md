# JX Organoid Detection

A GPU-accelerated microscopy image analysis platform for automated organoid viability assessment and Natural Killer (NK) cell population quantification using deep learning instance segmentation.

Developed at Heidelberg University for CAR-T cell cytotoxicity research.

---

## Table of Contents

- [Overview](#overview)
- [Scientific Background](#scientific-background)
- [System Architecture](#system-architecture)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Starting After System Reboot](#starting-after-system-reboot)
- [Persistent Cache System](#persistent-cache-system)
- [Dataset Structure](#dataset-structure)
- [Methodology](#methodology)
- [Directory Structure](#directory-structure)
- [Technology Stack](#technology-stack)
- [License](#license)

---

## Overview

This platform provides automated, quantitative analysis of fluorescence microscopy images to assess organoid viability following CAR-T cell treatment. The system combines Cellpose deep learning instance segmentation with multi-channel fluorescence quantification to deliver:

- Per-organoid morphological feature extraction (area, perimeter, circularity, solidity, eccentricity)
- Green fluorescent dye uptake quantification for viability classification (LIVE vs DEAD)
- Plate-wide Natural Killer (NK) cell population analysis via red and orange fluorescence channels
- Interactive web-based visualization with bidirectional table-canvas interactivity

The application is served as a FastAPI web application at `http://localhost:8000` with a vanilla HTML/CSS/JavaScript frontend.

---

## Scientific Background

### Organoid Viability Assessment

Organoid cultures are treated with CAR-T cells targeting different antigens (CEA, WT, BK) and co-cultured with NK effector cells. Following co-culture, a green fluorescent viability dye is applied. Dead organoids exhibit membrane permeability and accumulate the dye intracellularly, producing green fluorescence. Live organoids with intact membranes exclude the dye.

The system uses Cellpose (cyto3 model) to perform instance segmentation of individual organoids, then quantifies green dye pixels within each segmented boundary to classify viability status.

### NK Cell Quantification

Natural Killer cells are labeled with distinct fluorescent markers:
- **Live NK cells**: Red fluorescence channel
- **Dead NK cells**: Orange fluorescence channel (red-shifted green overlay)

NK cell viability is assessed plate-wide across the entire field of view, independent of organoid boundaries.

---

## System Architecture

```
Browser (localhost:8000)
    |
    v
FastAPI Server (server.py)
    |
    +-- Dataset Scanner (src/dataset.py)
    +-- Image Processor (src/image_processing.py)
    +-- Organoid Analyzer (src/organoid_analyzer.py)
    |       |
    |       +-- Cellpose GPU (cyto3 model)
    |       +-- OpenCV contour analysis
    |       +-- scikit-image regionprops
    |
    +-- In-Memory Cache (RAW_ARR_CACHE, SEGMENTATION_CACHE, OVERLAY_CACHE)
    +-- Persistent Disk Cache (cache/ directory)
```

---

## Features

### Core Analysis

- **Cellpose AI Segmentation**: Instance segmentation of organoids using the cyto3 deep learning model with GPU acceleration
- **True Green Pixel Detection**: Three-condition filter requiring green channel dominance over both red and blue channels by a minimum of 12 intensity units, eliminating false positives from autofluorescence and channel crosstalk
- **Morphological Feature Extraction**: Area, perimeter, equivalent diameter, bounding box dimensions, circularity, contour roughness, solidity, and eccentricity for each segmented organoid
- **NK Cell Population Analysis**: Plate-wide quantification of live (red) and dead (orange) Natural Killer cells with mortality rate calculation

### Performance

- **Single-Run Cellpose Caching**: GPU segmentation executes once per image; subsequent threshold adjustments update viability status in under 1 millisecond
- **Overlay Regeneration**: Annotated contour overlays regenerate from cached masks in under 5 milliseconds
- **Persistent Disk Cache**: Segmentation masks and feature tables are saved to disk and automatically reloaded on server restart, enabling instant results during presentations

### Interactive Visualization

- **Zoom and Pan**: Mouse wheel zoom (cursor-centric) and drag-to-pan with smooth transforms
- **Organoid Inspector Card**: Click any organoid on the image or in the table to view a cropped preview with all morphological features
- **Crop-to-Zoom**: Click the crop preview image to zoom and center the main canvas on that organoid
- **Bidirectional Interactivity**: Selecting an organoid on the canvas highlights the corresponding table row, and vice versa
- **Channel Filters**: Toggle between composite, green, red, and orange channel views
- **Threshold Tuning**: Adjustable minimum green pixel count for viability classification with instant visual feedback
- **Cache Management**: Visual cache status indicator with option to clear cache and force re-analysis

### Export and Reporting

- **CSV Export**: Download per-organoid feature tables as CSV files
- **Multi-Image Comparison**: Side-by-side comparison matrix with embedded thumbnails
- **HTML Report Export**: Standalone HTML comparison reports with base64-embedded images

---

## Installation

### Prerequisites

- Python 3.10 or later
- NVIDIA GPU with CUDA support (tested on GeForce GTX 1650 Ti, 4 GB VRAM)
- CUDA Toolkit compatible with your PyTorch version

### Setup

```bash
git clone https://github.com/mrtemroztrk/JX-organoid-detection.git
cd JX-organoid-detection

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### Verify GPU Availability

```bash
python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

---

## Usage

### Start the Server

```bash
cd /home/mrtemroztrk/Projects/Heidelberg/JX
source .venv/bin/activate
python server.py
```

The server starts on `http://localhost:8000`. Open this URL in your web browser.

### Analysis Workflow

1. Select an image from the file tree on the left sidebar
2. The system automatically runs Cellpose segmentation (first time) or loads cached results (subsequent runs)
3. Organoid contours appear on the image: purple for dead, turquoise for live
4. The feature table on the right displays per-organoid metrics
5. Adjust the green pixel threshold to tune viability classification in real time
6. Click organoids on the image or table rows for detailed inspection
7. Use channel filter buttons (Composite, Green, Red, Orange) to examine specific fluorescence channels
8. Export results as CSV or generate comparison reports

---

## Starting After System Reboot

After restarting your computer, run the following commands to start the application:

```bash
cd /home/mrtemroztrk/Projects/Heidelberg/JX
source .venv/bin/activate
python server.py
```

Then open `http://localhost:8000` in your browser. All previously analyzed images will load instantly from the persistent disk cache without requiring GPU computation.

---

## Persistent Cache System

The application implements a two-tier caching strategy:

### In-Memory Cache (Runtime)
- Raw image arrays, segmentation masks, overlay images, and feature DataFrames are stored in Python dictionaries
- Provides sub-millisecond access during a single server session

### Disk Cache (Persistent)
- After the first Cellpose analysis of each image, segmentation masks are saved as compressed NumPy archives (.npz) and feature tables as CSV files in the `cache/` directory
- A manifest file (`cache/manifest.json`) maps cache keys to original image paths
- On server startup, all cached results are automatically loaded into memory

### Cache Management

The web interface displays a cache status badge next to the Cellpose button:
- **No Cache**: Image has not been analyzed yet
- **Cached (Disk)**: Results loaded from disk on server startup
- **Cached (Memory)**: Results available in live memory

To force re-analysis, click the **Clear Cache and Re-run** button. This deletes both in-memory and disk cache for the current image and re-executes Cellpose segmentation from scratch.

---

## Dataset Structure

The dataset contains 18 fluorescence microscopy overlay images from three patient-derived organoid lines:

| Organoid Line | Source | Images |
|---|---|---|
| BK52 | Patient-derived colorectal | 6 images |
| M3 | Patient-derived colorectal | 6 images |
| ORG166 | Patient-derived colorectal | 6 images |

Each line is imaged under different CAR-T cell conditions:
- **WT**: Wild-type T cells (negative control)
- **CEA**: Anti-CEA CAR-T cells
- **BK**: Anti-BK CAR-T cells
- **9805**: Anti-9805 CAR-T cells
- **BG**: Background control

Images are stored as multi-channel TIFF files in BGR format within the `data/` directory.

---

## Methodology

### Instance Segmentation

Cellpose cyto3 performs instance segmentation by predicting spatial gradient flows that converge at cell centers. Each converged region defines one organoid mask. The model operates on GPU with gradient computation disabled (`torch.no_grad()`) to minimize VRAM consumption.

### Green Dye Quantification

For each segmented organoid, pixels within the mask boundary are evaluated for green fluorescence. A pixel is classified as truly green only when all three conditions are satisfied:

1. Green channel intensity >= 20
2. Green channel > Red channel + 12
3. Green channel > Blue channel + 12

This multi-condition filter prevents false-positive counts from autofluorescence, optical crosstalk between channels, and background noise.

### Viability Classification

An organoid is classified as DEAD if the count of truly green pixels within its boundary meets or exceeds the user-defined threshold (default: 1 pixel). The threshold can be adjusted in real time through the web interface without re-running segmentation.

### Contour Visualization

- **Dead organoids**: Purple contour outline (RGB 192, 132, 252)
- **Live organoids**: Turquoise contour outline (RGB 6, 182, 212)

### NK Cell Pixel Classification

Live NK cells (red fluorescence):
- R >= 40, R > G + 15, R > B + 15

Dead NK cells (orange fluorescence):
- R >= 40, G >= 25, R > B + 20, |R - G| < 70

### Morphological Features

| Feature | Description |
|---|---|
| Area (px) | Number of pixels within the segmented mask |
| Perimeter (px) | Arc length of the outer contour |
| Equivalent Diameter (px) | Diameter of a circle with equal area |
| Width, Height (px) | Bounding box dimensions |
| Circularity | 4 * pi * Area / Perimeter^2 |
| Contour Roughness | Perimeter / minimum possible perimeter for given area |
| Solidity | Area / convex hull area |
| Eccentricity | Ratio of focal distance to major axis length of fitted ellipse |

---

## Directory Structure

```
JX/
|-- server.py                  Main FastAPI server entry point
|-- app.py                     Streamlit application (legacy)
|-- requirements.txt           Python package dependencies
|-- src/
|   |-- __init__.py
|   |-- organoid_analyzer.py   Core analysis engine (Cellpose, features, NK cells)
|   |-- dataset.py             Dataset directory scanner and metadata
|   |-- image_processing.py    Channel isolation and color filtering
|   |-- viewer_utils.py        Visualization helper utilities
|-- static/
|   |-- index.html             Web application interface
|   |-- style.css              Design system and styling
|   |-- app.js                 Client-side application logic
|-- scripts/
|   |-- run_cellpose.py        Standalone Cellpose execution script
|   |-- run_full_dataset_batch.py  Batch analysis across all images
|   |-- extract_organoid_features.py  Feature extraction script
|   |-- cellpose_organoid_viability.py  Viability analysis script
|   |-- channel_isolator.py    Single-channel extraction utility
|   |-- count_green_dead_cells.py  Green pixel counting script
|   |-- count_red_nk_pixels.py  Red NK cell quantification script
|-- data/                      Microscopy TIFF images (3 organoid lines, 18 images)
|-- cache/                     Persistent segmentation cache (auto-generated)
|-- output/                    Batch analysis results and exports
```

---

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python 3.10+, FastAPI, Uvicorn |
| Deep Learning | Cellpose (cyto3), PyTorch (CUDA) |
| Image Processing | OpenCV, NumPy, scikit-image |
| Data Handling | pandas |
| Frontend | HTML5, CSS3, JavaScript (vanilla) |
| GPU | NVIDIA CUDA (tested: GTX 1650 Ti, 4 GB VRAM) |

---

## License

This project was developed for research purposes at Heidelberg University.
