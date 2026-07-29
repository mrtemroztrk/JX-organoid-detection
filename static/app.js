document.addEventListener('DOMContentLoaded', () => {
    let currentPath = null;
    let currentMode = 'original';
    let currentView = 'overlay'; // 'raw' vs 'overlay'
    let currentOrganoids = [];
    let selectedComparisonFiles = new Set();
    let batchResultsCache = [];
    let isAddMode = false;

    // Table Filtering & Sorting state
    let searchQuery = '';
    let filterStatus = 'ALL';
    let sortField = 'Organoid_ID';
    let sortAsc = true;

    // Zoom & Pan state
    let scale = 1.0;
    let panX = 0;
    let panY = 0;
    let isDragging = false;
    let startX = 0;
    let startY = 0;
    let selectedOrganoid = null;

    // DOM Elements
    const fileTreeEl = document.getElementById('file-tree');
    const filenameEl = document.getElementById('current-filename');
    const badgesEl = document.getElementById('meta-badges');
    const mainImgEl = document.getElementById('main-image');
    const imageWrapperEl = document.getElementById('image-wrapper');
    const viewerContainerEl = document.getElementById('viewer-container');
    const placeholderEl = document.getElementById('viewer-placeholder');
    const statusEl = document.getElementById('analysis-status');
    const metricsBarEl = document.getElementById('metrics-bar');

    // Organoid Metrics Elements
    const totalOrganoidsEl = document.getElementById('metric-total-organoids');
    const deadOrganoidsEl = document.getElementById('metric-dead-organoids');
    const mortalityRateEl = document.getElementById('metric-mortality-rate');
    const liveOrganoidsEl = document.getElementById('metric-live-organoids');

    // Plate-Wide NK Cell Metrics Elements (Live Red vs Dead Orange)
    const metricLiveNkRedEl = document.getElementById('metric-live-nk-red');
    const metricLiveNkSubEl = document.getElementById('metric-live-nk-sub');
    const metricDeadNkOrangeEl = document.getElementById('metric-dead-nk-orange');
    const metricDeadNkSubEl = document.getElementById('metric-dead-nk-sub');
    const metricNkMortalityRateEl = document.getElementById('metric-nk-mortality-rate');

    const tableDrawerEl = document.getElementById('table-drawer');
    const tableBodyEl = document.getElementById('table-body');
    const btnDownloadCsv = document.getElementById('btn-download-csv');
    const btnToggleTable = document.getElementById('btn-toggle-table');
    const tableSearchEl = document.getElementById('table-search');
    const filterStatusEl = document.getElementById('filter-status');
    const minGreenPixelsInput = document.getElementById('min-green-pixels-input');

    const btnViewRaw = document.getElementById('btn-view-raw');
    const btnViewOverlay = document.getElementById('btn-view-overlay');

    // Detail Card Inspector Elements
    const detailCardEl = document.getElementById('organoid-detail-card');
    const detailCardIdEl = document.getElementById('detail-card-id');
    const detailCardStatusEl = document.getElementById('detail-card-status');
    const detailCropImgEl = document.getElementById('detail-crop-img');
    const btnCloseDetailCard = document.getElementById('btn-close-detail-card');
    const hoverTooltipEl = document.getElementById('hover-tooltip');

    const detailAreaEl = document.getElementById('detail-area');
    const detailDiameterEl = document.getElementById('detail-diameter');
    const detailCircularityEl = document.getElementById('detail-circularity');
    const detailGreenPxEl = document.getElementById('detail-green-px');
    const detailGreenMeanEl = document.getElementById('detail-green-mean');
    const detailCentroidEl = document.getElementById('detail-centroid');

    const btnOpenComparison = document.getElementById('btn-open-comparison');
    const comparisonModalEl = document.getElementById('comparison-modal');
    const btnCloseModal = document.getElementById('btn-close-modal');
    const matrixContainerEl = document.getElementById('comparison-matrix-container');
    const btnExportComparisonHtml = document.getElementById('btn-export-comparison-html');

    const btnModeAdd = document.getElementById('btn-mode-add');
    const btnScientificBasis = document.getElementById('btn-scientific-basis');
    const scientificModalEl = document.getElementById('scientific-modal');
    const btnCloseSciModal = document.getElementById('btn-close-sci-modal');

    const btnZoomIn = document.getElementById('btn-zoom-in');
    const btnZoomOut = document.getElementById('btn-zoom-out');
    const btnResetZoom = document.getElementById('btn-reset-zoom');
    const btnFullscreen = document.getElementById('btn-fullscreen');

    const modeBtns = document.querySelectorAll('.mode-btn');
    const btnRunViability = document.getElementById('btn-run-viability');
    const btnCountRed = document.getElementById('btn-count-red');
    const btnCountOrange = document.getElementById('btn-count-orange');

    // Terminal DOM Elements
    const terminalBoxEl = document.getElementById('terminal-box');
    const terminalDotEl = document.getElementById('terminal-dot');
    const terminalTagEl = document.getElementById('terminal-status-tag');
    const terminalProgressEl = document.getElementById('terminal-progress');
    const terminalLogsEl = document.getElementById('terminal-logs');
    const btnClearTerminal = document.getElementById('btn-clear-terminal');
    const btnToggleTerminal = document.getElementById('btn-toggle-terminal');

    // System Terminal Logger Utility
    function logTerminal(message, type = 'info') {
        if (!terminalLogsEl) return;
        const timeStr = new Date().toLocaleTimeString('en-US', { hour12: false });
        const div = document.createElement('div');
        div.className = `log-entry ${type}`;
        div.textContent = `[${timeStr}] ${message}`;
        terminalLogsEl.appendChild(div);
        terminalLogsEl.scrollTop = terminalLogsEl.scrollHeight;
    }

    function setTerminalStatus(statusText, isRunning = false, type = 'running') {
        if (!terminalTagEl) return;
        terminalTagEl.textContent = statusText.toUpperCase();
        terminalTagEl.className = `terminal-tag tag-${type}`;

        if (isRunning) {
            terminalDotEl.classList.add('running');
            terminalProgressEl.classList.remove('hidden');
        } else {
            terminalDotEl.classList.remove('running');
            terminalProgressEl.classList.add('hidden');
        }
    }

    if (btnClearTerminal) {
        btnClearTerminal.addEventListener('click', () => {
            terminalLogsEl.innerHTML = '<div class="log-entry system-msg">[SYSTEM] Console cleared. Engine ready.</div>';
        });
    }

    if (btnToggleTerminal) {
        btnToggleTerminal.addEventListener('click', () => {
            terminalBoxEl.classList.toggle('collapsed');
            btnToggleTerminal.textContent = terminalBoxEl.classList.contains('collapsed') ? 'Expand' : 'Collapse';
        });
    }

    // Prevent Native Browser Image Dragging
    mainImgEl.addEventListener('dragstart', (e) => e.preventDefault());

    // 1. Cursor-Centric Zoom & Pan Transform Update
    function updateTransform() {
        imageWrapperEl.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
    }

    function resetZoom() {
        scale = 1.0;
        panX = 0;
        panY = 0;
        updateTransform();
    }

    btnZoomIn.addEventListener('click', () => { scale = Math.min(10.0, scale + 0.3); updateTransform(); });
    btnZoomOut.addEventListener('click', () => { scale = Math.max(0.5, scale - 0.3); updateTransform(); });
    btnResetZoom.addEventListener('click', resetZoom);

    btnFullscreen.addEventListener('click', () => {
        if (!document.fullscreenElement) {
            viewerContainerEl.requestFullscreen().catch(err => alert(`Fullscreen error: ${err.message}`));
        } else {
            document.exitFullscreen();
        }
    });

    // Smooth Cursor-Centric Mouse Wheel Zoom
    viewerContainerEl.addEventListener('wheel', (e) => {
        if (placeholderEl.classList.contains('hidden') === false) return;
        e.preventDefault();

        const rect = viewerContainerEl.getBoundingClientRect();
        const mouseX = e.clientX - rect.left - rect.width / 2;
        const mouseY = e.clientY - rect.top - rect.height / 2;

        const delta = e.deltaY < 0 ? 0.18 : -0.18;
        const newScale = Math.min(Math.max(0.5, scale + delta), 10.0);

        if (newScale !== scale) {
            panX -= (mouseX - panX) * (newScale / scale - 1);
            panY -= (mouseY - panY) * (newScale / scale - 1);
            scale = newScale;
            updateTransform();
        }
    }, { passive: false });

    // Smooth Drag Pan
    viewerContainerEl.addEventListener('mousedown', (e) => {
        if (isAddMode || e.target.closest('#organoid-detail-card')) return;
        
        isDragging = true;
        startX = e.clientX - panX;
        startY = e.clientY - panY;
        viewerContainerEl.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        e.preventDefault();
        panX = e.clientX - startX;
        panY = e.clientY - startY;
        updateTransform();
    });

    const stopDragging = () => {
        if (isDragging) {
            isDragging = false;
            viewerContainerEl.style.cursor = isAddMode ? 'crosshair' : 'grab';
        }
    };

    window.addEventListener('mouseup', stopDragging);
    window.addEventListener('mouseleave', stopDragging);
    viewerContainerEl.addEventListener('mouseleave', stopDragging);

    // Double-click to quick-zoom or reset
    viewerContainerEl.addEventListener('dblclick', (e) => {
        if (isAddMode) return;
        if (scale > 1.0) {
            resetZoom();
        } else {
            scale = 2.5;
            updateTransform();
        }
    });

    viewerContainerEl.style.cursor = 'grab';

    // 2. View Mode Toggle (RAW vs CELLPOSE OVERLAY)
    if (btnViewRaw) {
        btnViewRaw.addEventListener('click', () => {
            currentView = 'raw';
            btnViewRaw.classList.add('active');
            if (btnViewOverlay) btnViewOverlay.classList.remove('active');
            updateImageSrc();
            statusEl.textContent = 'View Mode: RAW (Unannotated Microscopy Image)';
            logTerminal('Switched view mode to RAW image.', 'info');
        });
    }

    if (btnViewOverlay) {
        btnViewOverlay.addEventListener('click', () => {
            currentView = 'overlay';
            btnViewOverlay.classList.add('active');
            if (btnViewRaw) btnViewRaw.classList.remove('active');
            updateImageSrc();
            statusEl.textContent = 'View Mode: Cellpose AI Overlay (Blue: LIVE, Red: DEAD)';
            logTerminal('Switched view mode to Cellpose AI Overlay.', 'info');
        });
    }

    // Interactive Table Drawer Toggle Button
    if (btnToggleTable) {
        btnToggleTable.addEventListener('click', () => {
            tableDrawerEl.classList.toggle('hidden');
            btnToggleTable.classList.toggle('active');
        });
    }

    // User-Adjustable Green Pixel Count Threshold Listener
    // INSTANT CLIENT-SIDE RE-THRESHOLDING (Zero Cellpose Re-run!)
    if (minGreenPixelsInput) {
        minGreenPixelsInput.addEventListener('input', () => {
            const minPixels = parseInt(minGreenPixelsInput.value) || 1;
            recalculateInstantThreshold(minPixels);
        });
    }

    function recalculateInstantThreshold(minPixels) {
        if (!currentOrganoids || currentOrganoids.length === 0) {
            runCellposeViabilityInstant(false);
            return;
        }

        // 1. Instantly re-threshold local organoid statuses in <1ms!
        let deadCount = 0;
        let liveCount = 0;

        currentOrganoids.forEach(o => {
            const greenPx = o.Green_Pixel_Count !== undefined ? o.Green_Pixel_Count : 0;
            const isDead = (greenPx >= minPixels);
            o.Status = isDead ? 'DEAD' : 'LIVE';
            o.Status_TR = o.Status;
            if (isDead) deadCount++; else liveCount++;
        });

        const totalCount = currentOrganoids.length;
        const mortalityRate = totalCount > 0 ? ((deadCount / totalCount) * 100).toFixed(1) : "0.0";

        // 2. Instantly update metrics cards & feature table in <1ms!
        totalOrganoidsEl.textContent = totalCount.toLocaleString();
        deadOrganoidsEl.textContent = deadCount.toLocaleString();
        mortalityRateEl.textContent = `${mortalityRate}% Organoid Mortality`;
        liveOrganoidsEl.textContent = liveCount.toLocaleString();

        renderFeatureTable(currentOrganoids);

        statusEl.textContent = `Instant Threshold Updated (Min Green Pixels: >=${minPixels}): ${deadCount} DEAD (Red), ${liveCount} LIVE (Blue). Zero Cellpose re-evaluation.`;
        logTerminal(`[INSTANT THRESHOLD] Applied min_green_pixels >= ${minPixels}. ${deadCount} DEAD, ${liveCount} LIVE (${mortalityRate}% mortality) updated in <1ms.`, 'success');

        // 3. Request updated overlay image from cached mask (<5ms)
        runCellposeViabilityInstant(false);
    }

    // 3. Fetch Dataset & Pre-cached Batch Results
    async function loadDataset() {
        try {
            logTerminal('Scanning data directory for microscopy TIFF images...', 'info');
            const [datasetRes, batchRes] = await Promise.all([
                fetch('/api/dataset'),
                fetch('/api/batch_results')
            ]);
            
            const data = await datasetRes.json();
            batchResultsCache = await batchRes.json();

            fileTreeEl.innerHTML = '';
            let fileCount = 0;

            for (const [folder, files] of Object.entries(data.folder_map)) {
                const folderDiv = document.createElement('div');
                folderDiv.className = 'folder-item';
                
                const folderHeader = document.createElement('div');
                folderHeader.className = 'folder-name';
                folderHeader.textContent = `${folder} (${files.length})`;
                folderDiv.appendChild(folderHeader);

                files.forEach(filepath => {
                    fileCount++;
                    const filename = filepath.split('/').pop();
                    const fileRow = document.createElement('div');
                    fileRow.className = 'file-row';

                    const chk = document.createElement('input');
                    chk.type = 'checkbox';
                    chk.className = 'file-checkbox';
                    chk.value = filename;
                    chk.addEventListener('change', (e) => {
                        if (e.target.checked) {
                            selectedComparisonFiles.add(filename);
                        } else {
                            selectedComparisonFiles.delete(filename);
                        }
                        updateComparisonButtonText();
                    });

                    const fileDiv = document.createElement('div');
                    fileDiv.className = 'file-item';
                    fileDiv.textContent = filename;
                    
                    fileDiv.addEventListener('click', () => {
                        document.querySelectorAll('.file-item').forEach(el => el.classList.remove('active'));
                        fileDiv.classList.add('active');
                        selectImage(filepath, filename);
                    });
                    
                    fileRow.appendChild(chk);
                    fileRow.appendChild(fileDiv);
                    folderDiv.appendChild(fileRow);
                });
                
                fileTreeEl.appendChild(folderDiv);
            }

            logTerminal(`Dataset scan complete. Found ${fileCount} images across ${Object.keys(data.folder_map).length} directories.`, 'success');

            const firstFile = document.querySelector('.file-item');
            if (firstFile) firstFile.click();

        } catch (err) {
            fileTreeEl.innerHTML = `<div style="color:#f85149; padding:10px;">Failed to load dataset: ${err.message}</div>`;
            logTerminal(`Dataset load error: ${err.message}`, 'error');
        }
    }

    function updateComparisonButtonText() {
        btnOpenComparison.textContent = `Multi-Image Comparison (${selectedComparisonFiles.size})`;
    }

    // 4. Select Image (Each image gets its own isolated table & metrics!)
    function selectImage(path, filename) {
        currentPath = path;
        currentOrganoids = [];
        filenameEl.textContent = filename;
        statusEl.textContent = 'Loading image...';
        detailCardEl.classList.add('hidden');
        isAddMode = false;
        btnModeAdd.classList.remove('active');
        viewerContainerEl.style.cursor = 'grab';
        resetZoom();

        logTerminal(`Selected image: ${filename}`, 'info');

        let badgesHtml = '';
        if (filename.includes('BK52')) badgesHtml += `<span class="badge">BK52</span>`;
        if (filename.includes('M3')) badgesHtml += `<span class="badge">M3</span>`;
        if (filename.includes('ORG166')) badgesHtml += `<span class="badge">ORG166</span>`;
        if (filename.includes('CEA')) badgesHtml += `<span class="badge">CEA</span>`;
        if (filename.includes('WT')) badgesHtml += `<span class="badge">WT</span>`;
        if (filename.includes('BK')) badgesHtml += `<span class="badge">BK</span>`;
        badgesEl.innerHTML = badgesHtml;

        placeholderEl.classList.add('hidden');
        imageWrapperEl.classList.remove('hidden');
        updateImageSrc();

        const cached = batchResultsCache.find(r => r.filename === filename || r.filepath === path);
        if (cached) {
            metricsBarEl.classList.remove('hidden');
            totalOrganoidsEl.textContent = cached.total_organoids.toLocaleString();
            deadOrganoidsEl.textContent = cached.dead_organoids.toLocaleString();
            mortalityRateEl.textContent = `${cached.mortality_rate_percent}% Organoid Mortality`;
            liveOrganoidsEl.textContent = cached.live_organoids.toLocaleString();

            if (metricLiveNkRedEl && cached.nk_red_pixel_count !== undefined) {
                metricLiveNkRedEl.textContent = cached.nk_red_pixel_count.toLocaleString();
            }
            if (metricDeadNkOrangeEl && cached.orange_pixel_count !== undefined) {
                metricDeadNkOrangeEl.textContent = cached.orange_pixel_count.toLocaleString();
            }
        }

        runCellposeViabilityInstant();
    }

    async function runCellposeViabilityInstant(forceReanalyze = false) {
        if (!currentPath) return;
        const minPixels = parseInt(minGreenPixelsInput ? minGreenPixelsInput.value : 1) || 1;
        
        let progressTimer = null;
        let secondsElapsed = 0;

        if (forceReanalyze) {
            setTerminalStatus('CELLPOSE RUNNING', true, 'running');
            logTerminal(`[CELLPOSE AI EXECUTION STARTED] Evaluating vector flows on NVIDIA GTX 1650 Ti GPU...`, 'info');

            progressTimer = setInterval(() => {
                secondsElapsed += 2;
                const estRemaining = Math.max(0, 16 - secondsElapsed);
                const pct = Math.min(95, Math.round((secondsElapsed / 16) * 100));
                statusEl.textContent = `🤖 Cellpose AI Running... ${pct}% completed (${secondsElapsed}s elapsed, ~${estRemaining}s remaining)`;
                logTerminal(`[CELLPOSE RUNNING] Evaluating spatial vector flows (${secondsElapsed}s elapsed, ~${estRemaining}s remaining)...`, 'info');
            }, 2000);
        } else {
            setTerminalStatus('COMPUTING', true, 'running');
        }
        
        try {
            const startTime = performance.now();
            const res = await fetch('/api/analyze/cellpose_viability', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    path: currentPath,
                    min_green_pixels: minPixels,
                    force_reanalyze: forceReanalyze
                })
            });
            const result = await res.json();
            const elapsed = Math.round(performance.now() - startTime);
            const summary = result.summary;

            if (progressTimer) clearInterval(progressTimer);

            updateImageSrc();

            metricsBarEl.classList.remove('hidden');
            totalOrganoidsEl.textContent = summary.total_organoid_count.toLocaleString();
            deadOrganoidsEl.textContent = summary.dead_organoid_count.toLocaleString();
            mortalityRateEl.textContent = `${summary.mortality_rate_percent}% Organoid Mortality`;
            liveOrganoidsEl.textContent = summary.live_organoid_count.toLocaleString();

            // Populate Plate-Wide Natural Killer (NK) Cell Viability Metrics
            if (metricLiveNkRedEl && summary.live_nk_red_pixels !== undefined) {
                metricLiveNkRedEl.textContent = summary.live_nk_red_pixels.toLocaleString();
                if (metricLiveNkSubEl) metricLiveNkSubEl.textContent = `${summary.live_nk_coverage_percent}% Plate Area`;
            }

            if (metricDeadNkOrangeEl && summary.dead_nk_orange_pixels !== undefined) {
                metricDeadNkOrangeEl.textContent = summary.dead_nk_orange_pixels.toLocaleString();
                if (metricDeadNkSubEl) metricDeadNkSubEl.textContent = `${summary.dead_nk_coverage_percent}% Plate Area`;
            }

            if (metricNkMortalityRateEl && summary.nk_mortality_rate_percent !== undefined) {
                metricNkMortalityRateEl.textContent = `${summary.nk_mortality_rate_percent}%`;
            }

            renderFeatureTable(result.organoids);
            statusEl.textContent = `Cellpose Complete: ${summary.total_organoid_count} Organoids (${summary.dead_organoid_count} DEAD, ${summary.live_organoid_count} LIVE). Plate NK Cells: ${summary.live_nk_red_pixels.toLocaleString()} Live Red vs ${summary.dead_nk_orange_pixels.toLocaleString()} Dead Orange (${summary.nk_mortality_rate_percent}% NK Mortality).`;

            setTerminalStatus('READY', false, 'done');
            if (summary.from_cache) {
                logTerminal(`[CACHE HIT] Loaded pre-segmented mask in ${elapsed}ms. Viability re-thresholded with min_green_pixels=${minPixels} (${summary.dead_organoid_count} DEAD, ${summary.live_organoid_count} LIVE).`, 'success');
            } else {
                logTerminal(`[ANALYSIS COMPLETE] Delineated ${summary.total_organoid_count} organoids on GPU. Plate NK Cells: ${summary.live_nk_red_pixels.toLocaleString()} LIVE Red, ${summary.dead_nk_orange_pixels.toLocaleString()} DEAD Orange (${summary.nk_mortality_rate_percent}% NK Mortality).`, 'success');
            }

        } catch (err) {
            if (progressTimer) clearInterval(progressTimer);
            setTerminalStatus('ERROR', false, 'idle');
            statusEl.textContent = `Cellpose analysis error: ${err.message}`;
            logTerminal(`Cellpose error: ${err.message}`, 'error');
        }
    }

    // 5. Update Image Source
    function updateImageSrc() {
        if (!currentPath) return;
        placeholderEl.classList.add('hidden');
        imageWrapperEl.classList.remove('hidden');

        const timestamp = new Date().getTime();
        if (currentView === 'raw') {
            mainImgEl.src = `/api/image?path=${encodeURIComponent(currentPath)}&mode=${currentMode}&t=${timestamp}`;
        } else {
            mainImgEl.src = `/api/image/overlay?path=${encodeURIComponent(currentPath)}&type=viability&t=${timestamp}`;
        }
    }

    // 6. Channel Mode Switcher
    modeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            modeBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentMode = btn.dataset.mode;
            updateImageSrc();
            logTerminal(`Applied channel filter: ${currentMode.toUpperCase()}`, 'info');
        });
    });

    // 7. Interactive Feature Table Filtering & Sorting
    function filterAndSortOrganoids(organoids) {
        if (!organoids) return [];
        let result = [...organoids];

        // Filter by Status
        if (filterStatus === 'DEAD') {
            result = result.filter(o => o.Status === 'DEAD' || o.Status_TR === 'DEAD' || o.Status_TR === 'ÖLÜ');
        } else if (filterStatus === 'LIVE') {
            result = result.filter(o => o.Status === 'LIVE' || o.Status_TR === 'LIVE' || o.Status_TR === 'CANLI');
        }

        // Filter by Search Query
        if (searchQuery.trim() !== '') {
            const q = searchQuery.toLowerCase().trim();
            result = result.filter(o =>
                o.Organoid_ID.toString().includes(q) ||
                (o.Status && o.Status.toLowerCase().includes(q)) ||
                (o.Area_px && o.Area_px.toString().includes(q)) ||
                (o.Circularity && o.Circularity.toString().includes(q)) ||
                (o.Contour_Roughness && o.Contour_Roughness.toString().includes(q))
            );
        }

        // Sort
        if (sortField) {
            result.sort((a, b) => {
                let valA = a[sortField];
                let valB = b[sortField];
                if (valA === undefined || valA === null) valA = 0;
                if (valB === undefined || valB === null) valB = 0;

                if (typeof valA === 'string') valA = valA.toLowerCase();
                if (typeof valB === 'string') valB = valB.toLowerCase();

                if (valA < valB) return sortAsc ? -1 : 1;
                if (valA > valB) return sortAsc ? 1 : -1;
                return 0;
            });
        }

        return result;
    }

    function renderFeatureTable(organoids) {
        currentOrganoids = organoids || [];
        const filtered = filterAndSortOrganoids(currentOrganoids);
        tableBodyEl.innerHTML = '';

        if (!filtered || filtered.length === 0) {
            tableBodyEl.innerHTML = '<tr><td colspan="8" class="table-empty">No organoids match the current filter.</td></tr>';
            return;
        }

        filtered.forEach(obj => {
            const tr = document.createElement('tr');
            tr.dataset.organoidId = obj.Organoid_ID;
            const isDead = (obj.Status === 'DEAD' || obj.Status_TR === 'ÖLÜ' || obj.Status_TR === 'DEAD');
            const statusClass = isDead ? 'status-dead' : 'status-live';
            const statusText = isDead ? 'DEAD' : 'LIVE';
            const greenPxCount = obj.Green_Pixel_Count !== undefined ? obj.Green_Pixel_Count : 0;

            tr.innerHTML = `
                <td><b>#${obj.Organoid_ID}</b></td>
                <td class="${statusClass}"><b>${statusText}</b></td>
                <td>${obj.Area_px.toLocaleString()} px</td>
                <td>${obj.Eq_Diameter_px} px</td>
                <td>${obj.Circularity}</td>
                <td><b style="color:#2ecc71;">${greenPxCount.toLocaleString()}</b></td>
                <td>${obj.Green_Mean_Intensity}</td>
                <td>
                    <button class="btn-delete-row" title="Delete Organoid">Delete</button>
                </td>
            `;

            tr.addEventListener('click', (e) => {
                if (e.target.classList.contains('btn-delete-row')) return;
                document.querySelectorAll('#features-table tr').forEach(r => r.classList.remove('selected-row'));
                tr.classList.add('selected-row');
                openOrganoidDetailCard(obj);
            });

            const delBtn = tr.querySelector('.btn-delete-row');
            delBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteOrganoid(obj.Organoid_ID);
            });

            tableBodyEl.appendChild(tr);
        });

        tableDrawerEl.classList.remove('hidden');
        if (btnToggleTable) btnToggleTable.classList.add('active');
    }

    // Attach Sorting Listeners to Table Headers
    document.querySelectorAll('#features-table th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
            const field = th.dataset.sort;
            if (sortField === field) {
                sortAsc = !sortAsc;
            } else {
                sortField = field;
                sortAsc = true;
            }
            renderFeatureTable(currentOrganoids);
        });
    });

    // Attach Search & Filter Listeners
    if (tableSearchEl) {
        tableSearchEl.addEventListener('input', (e) => {
            searchQuery = e.target.value;
            renderFeatureTable(currentOrganoids);
        });
    }

    if (filterStatusEl) {
        filterStatusEl.addEventListener('change', (e) => {
            filterStatus = e.target.value;
            renderFeatureTable(currentOrganoids);
        });
    }

    // Delete Organoid by ID
    async function deleteOrganoid(organoidId) {
        if (!currentPath) return;

        try {
            setTerminalStatus('DELETING', true, 'running');
            logTerminal(`Deleting Organoid #${organoidId}...`, 'warn');
            const res = await fetch('/api/organoid/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: currentPath, organoid_id: organoidId })
            });
            const result = await res.json();
            const summary = result.summary;

            totalOrganoidsEl.textContent = summary.total_organoid_count.toLocaleString();
            deadOrganoidsEl.textContent = summary.dead_organoid_count.toLocaleString();
            mortalityRateEl.textContent = `${summary.mortality_rate_percent}% Organoid Mortality`;
            liveOrganoidsEl.textContent = summary.live_organoid_count.toLocaleString();

            renderFeatureTable(result.organoids);
            statusEl.textContent = `Organoid #${organoidId} deleted. Recalculated mortality rate: ${summary.mortality_rate_percent}%`;
            setTerminalStatus('READY', false, 'done');
            logTerminal(`Organoid #${organoidId} removed. Updated mortality rate: ${summary.mortality_rate_percent}%`, 'success');
        } catch (err) {
            setTerminalStatus('ERROR', false, 'idle');
            statusEl.textContent = `Delete error: ${err.message}`;
            logTerminal(`Delete error: ${err.message}`, 'error');
        }
    }

    // Open Organoid Detail Inspector Card with Crop Zoom & Feature Values
    function openOrganoidDetailCard(obj) {
        if (!obj || !currentPath) return;
        selectedOrganoid = obj;

        const isDead = (obj.Status === 'DEAD' || obj.Status_TR === 'ÖLÜ' || obj.Status_TR === 'DEAD');
        const statusText = isDead ? 'DEAD' : 'LIVE';

        detailCardIdEl.textContent = `Organoid #${obj.Organoid_ID}`;
        detailCardStatusEl.textContent = statusText;
        detailCardStatusEl.className = `status-tag ${isDead ? 'status-dead' : 'status-live'}`;

        const timestamp = new Date().getTime();
        detailCropImgEl.src = `/api/image/highlight_organoid?path=${encodeURIComponent(currentPath)}&organoid_id=${obj.Organoid_ID}&t=${timestamp}`;

        detailAreaEl.textContent = `${(obj.Area_px || 0).toLocaleString()} px`;
        detailDiameterEl.textContent = `${obj.Eq_Diameter_px || 0} px`;
        detailCircularityEl.textContent = obj.Circularity || 0;
        detailGreenPxEl.textContent = (obj.Green_Pixel_Count || 0).toLocaleString();
        detailGreenMeanEl.textContent = obj.Green_Mean_Intensity || 0;
        detailCentroidEl.textContent = `(${obj.Centroid_X || 0}, ${obj.Centroid_Y || 0})`;

        detailCardEl.classList.remove('hidden');

        // Select and scroll to row in feature table
        tableDrawerEl.classList.remove('hidden');
        if (btnToggleTable) btnToggleTable.classList.add('active');

        document.querySelectorAll('#features-table tbody tr').forEach(r => r.classList.remove('selected-row'));
        const targetTr = document.querySelector(`#features-table tbody tr[data-organoid-id="${obj.Organoid_ID}"]`);
        if (targetTr) {
            targetTr.classList.add('selected-row');
            targetTr.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

        logTerminal(`Inspecting Organoid #${obj.Organoid_ID} (${statusText}, Area: ${obj.Area_px} px, Green Pks: ${obj.Green_Pixel_Count || 0})`, 'info');
    }

    if (btnCloseDetailCard) {
        btnCloseDetailCard.addEventListener('click', () => {
            detailCardEl.classList.add('hidden');
        });
    }

    // Click on crop preview image -> zoom & center main canvas on that organoid
    if (detailCropImgEl) {
        detailCropImgEl.style.cursor = 'zoom-in';
        detailCropImgEl.addEventListener('click', () => {
            if (!selectedOrganoid || !mainImgEl.naturalWidth) return;

            const obj = selectedOrganoid;
            const cx = obj.Centroid_X || 0;
            const cy = obj.Centroid_Y || 0;

            const rect = viewerContainerEl.getBoundingClientRect();
            const containerW = rect.width;
            const containerH = rect.height;

            // Compute display scale factor (natural image px -> displayed px at scale=1)
            const displayedW = mainImgEl.clientWidth;
            const displayedH = mainImgEl.clientHeight;
            const imgScaleX = displayedW / mainImgEl.naturalWidth;
            const imgScaleY = displayedH / mainImgEl.naturalHeight;

            // Target zoom level
            scale = 3.5;

            // Position of the organoid centroid in displayed-pixel space (at scale=1)
            const objDisplayX = cx * imgScaleX;
            const objDisplayY = cy * imgScaleY;

            // Pan so that the organoid centroid is at the center of the viewer container
            panX = (containerW / 2) - (objDisplayX * scale);
            panY = (containerH / 2) - (objDisplayY * scale);

            updateTransform();
            logTerminal(`Zoomed to Organoid #${obj.Organoid_ID} at (${cx}, ${cy}) — scale ${scale}x`, 'info');
        });
    }

    // 8. Interactive Canvas Hover & Click Handlers:
    // Mouseover Hover Badge on Canvas
    mainImgEl.addEventListener('mousemove', (e) => {
        if (!currentOrganoids || currentOrganoids.length === 0 || isAddMode) {
            if (hoverTooltipEl) hoverTooltipEl.classList.add('hidden');
            return;
        }

        const rect = mainImgEl.getBoundingClientRect();
        const scaleX = mainImgEl.naturalWidth / rect.width;
        const scaleY = mainImgEl.naturalHeight / rect.height;

        const clickX = Math.round((e.clientX - rect.left) * scaleX);
        const clickY = Math.round((e.clientY - rect.top) * scaleY);

        let closest = null;
        let minDistance = Infinity;

        currentOrganoids.forEach(obj => {
            const cx = obj.Centroid_X;
            const cy = obj.Centroid_Y;
            if (cx === undefined || cy === undefined) return;
            const dist = Math.sqrt((cx - clickX) ** 2 + (cy - clickY) ** 2);
            const objRadius = Math.max(obj.Width_px || 40, obj.Height_px || 40) / 2 + 20;

            if (dist < minDistance && dist <= objRadius) {
                minDistance = dist;
                closest = obj;
            }
        });

        if (closest && hoverTooltipEl) {
            const containerRect = viewerContainerEl.getBoundingClientRect();
            const posX = e.clientX - containerRect.left + 15;
            const posY = e.clientY - containerRect.top + 15;

            const isDead = (closest.Status === 'DEAD' || closest.Status_TR === 'ÖLÜ' || closest.Status_TR === 'DEAD');
            hoverTooltipEl.style.left = `${posX}px`;
            hoverTooltipEl.style.top = `${posY}px`;
            hoverTooltipEl.innerHTML = `<b>#${closest.Organoid_ID}</b> (${isDead ? 'DEAD' : 'LIVE'})<br>Area: ${closest.Area_px} px | Green Pks: ${closest.Green_Pixel_Count || 0}`;
            hoverTooltipEl.classList.remove('hidden');
            viewerContainerEl.style.cursor = 'pointer';
        } else {
            if (hoverTooltipEl) hoverTooltipEl.classList.add('hidden');
            viewerContainerEl.style.cursor = 'grab';
        }
    });

    mainImgEl.addEventListener('mouseleave', () => {
        if (hoverTooltipEl) hoverTooltipEl.classList.add('hidden');
    });

    // Canvas Click Handler
    btnModeAdd.addEventListener('click', () => {
        isAddMode = !isAddMode;
        if (isAddMode) {
            btnModeAdd.classList.add('active');
            viewerContainerEl.style.cursor = 'crosshair';
            statusEl.textContent = 'Add Mode Active: Click on image to add a custom organoid.';
            logTerminal('Manual Add Mode enabled. Click anywhere on the image canvas.', 'info');
        } else {
            btnModeAdd.classList.remove('active');
            viewerContainerEl.style.cursor = 'grab';
            statusEl.textContent = 'Click on any organoid on the image to open inspector card & highlight table row.';
            logTerminal('Manual Add Mode disabled.', 'info');
        }
    });

    mainImgEl.addEventListener('click', async (e) => {
        if (!currentPath) return;

        const rect = mainImgEl.getBoundingClientRect();
        const scaleX = mainImgEl.naturalWidth / rect.width;
        const scaleY = mainImgEl.naturalHeight / rect.height;

        const clickX = Math.round((e.clientX - rect.left) * scaleX);
        const clickY = Math.round((e.clientY - rect.top) * scaleY);

        if (isAddMode) {
            // Mode A: Add Manual Organoid
            statusEl.textContent = `Adding manual organoid at pixel position (${clickX}, ${clickY})...`;
            setTerminalStatus('ADDING', true, 'running');
            logTerminal(`Adding manual organoid at (${clickX}, ${clickY})...`, 'info');

            try {
                const res = await fetch('/api/organoid/add_manual', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: currentPath, x: clickX, y: clickY, radius: 18 })
                });
                const result = await res.json();
                const summary = result.summary;

                updateImageSrc();

                totalOrganoidsEl.textContent = summary.total_organoid_count.toLocaleString();
                deadOrganoidsEl.textContent = summary.dead_organoid_count.toLocaleString();
                mortalityRateEl.textContent = `${summary.mortality_rate_percent}% Organoid Mortality`;
                liveOrganoidsEl.textContent = summary.live_organoid_count.toLocaleString();

                renderFeatureTable(result.organoids);
                statusEl.textContent = `Organoid #${result.new_organoid.Organoid_ID} added manually. Area: ${result.new_organoid.Area_px} px`;
                setTerminalStatus('READY', false, 'done');
                logTerminal(`Organoid #${result.new_organoid.Organoid_ID} created manually.`, 'success');
            } catch (err) {
                setTerminalStatus('ERROR', false, 'idle');
                statusEl.textContent = `Error adding organoid: ${err.message}`;
                logTerminal(`Add error: ${err.message}`, 'error');
            }
        } else {
            // Mode B: Interactive Canvas Click -> Open Inspector Card + Highlight Table Row!
            if (!currentOrganoids || currentOrganoids.length === 0) return;

            let closestOrganoid = null;
            let minDistance = Infinity;

            currentOrganoids.forEach(obj => {
                const cx = obj.Centroid_X;
                const cy = obj.Centroid_Y;
                if (cx === undefined || cy === undefined) return;

                const dist = Math.sqrt((cx - clickX) ** 2 + (cy - clickY) ** 2);
                const objRadius = Math.max(obj.Width_px || 40, obj.Height_px || 40) / 2 + 25;

                if (dist < minDistance && dist <= objRadius) {
                    minDistance = dist;
                    closestOrganoid = obj;
                }
            });

            if (closestOrganoid) {
                openOrganoidDetailCard(closestOrganoid);
                statusEl.textContent = `Selected Organoid #${closestOrganoid.Organoid_ID} (${closestOrganoid.Status}, Area: ${closestOrganoid.Area_px} px, Green Pks: ${closestOrganoid.Green_Pixel_Count || 0})`;
            }
        }
    });

    // 9. Scientific Basis Modal
    btnScientificBasis.addEventListener('click', () => {
        scientificModalEl.classList.remove('hidden');
        if (window.MathJax && window.MathJax.typesetPromise) {
            window.MathJax.typesetPromise();
        }
    });
    btnCloseSciModal.addEventListener('click', () => { scientificModalEl.classList.add('hidden'); });

    // 10. CSV Download
    btnDownloadCsv.addEventListener('click', () => {
        if (!currentOrganoids || currentOrganoids.length === 0) return;
        const headers = Object.keys(currentOrganoids[0]).join(',');
        const rows = currentOrganoids.map(obj => Object.values(obj).join(',')).join('\n');
        const csvContent = "data:text/csv;charset=utf-8," + encodeURIComponent(headers + '\n' + rows);
        const link = document.createElement("a");
        link.setAttribute("href", csvContent);
        link.setAttribute("download", `organoid_features_${filenameEl.textContent}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        logTerminal(`Downloaded CSV feature report: organoid_features_${filenameEl.textContent}.csv`, 'success');
    });

    // 11. Cellpose Rerun
    btnRunViability.addEventListener('click', () => { runCellposeViabilityInstant(true); });

    // 12. NK Cell Red Pixel Count (Live Red NK Cells)
    btnCountRed.addEventListener('click', async () => {
        if (!currentPath) return;
        statusEl.textContent = 'Quantifying Live NK Cell Red Pixels...';
        btnCountRed.disabled = true;
        setTerminalStatus('QUANTIFYING', true, 'running');
        logTerminal('Quantifying Live Red NK Cell pixels across field of view...', 'info');

        try {
            const res = await fetch('/api/analyze/red_nk_cells', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: currentPath })
            });
            const result = await res.json();

            const timestamp = new Date().getTime();
            mainImgEl.src = `/api/image/overlay?path=${encodeURIComponent(currentPath)}&type=nk_red&t=${timestamp}`;

            statusEl.textContent = `Live NK Cell Red Pixel Quantification: ${result.red_pixel_count.toLocaleString()} Red Pixels (${result.red_coverage_percent}% Field Area Coverage)`;
            setTerminalStatus('READY', false, 'done');
            logTerminal(`Live NK Red Pixel Quantification complete: ${result.red_pixel_count.toLocaleString()} px (${result.red_coverage_percent}% coverage).`, 'success');
        } catch (err) {
            setTerminalStatus('ERROR', false, 'idle');
            statusEl.textContent = `Quantification error: ${err.message}`;
            logTerminal(`Quantification error: ${err.message}`, 'error');
        } finally {
            btnCountRed.disabled = false;
        }
    });

    // 13. Orange Fluorescent Pixel Count (Dead Orange NK Cells)
    if (btnCountOrange) {
        btnCountOrange.addEventListener('click', async () => {
            if (!currentPath) return;
            statusEl.textContent = 'Quantifying Dead NK Cell Orange Pixels...';
            btnCountOrange.disabled = true;
            setTerminalStatus('QUANTIFYING', true, 'running');
            logTerminal('Quantifying Dead Orange NK Cell pixels across field of view...', 'info');

            try {
                const res = await fetch('/api/analyze/orange_pixels', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: currentPath })
                });
                const result = await res.json();

                const timestamp = new Date().getTime();
                mainImgEl.src = `/api/image/overlay?path=${encodeURIComponent(currentPath)}&type=orange&t=${timestamp}`;

                statusEl.textContent = `Dead NK Cell Orange Pixel Quantification: ${result.orange_pixel_count.toLocaleString()} Orange Pixels (${result.orange_coverage_percent}% Field Area Coverage)`;
                setTerminalStatus('READY', false, 'done');
                logTerminal(`Dead NK Orange Pixel Quantification complete: ${result.orange_pixel_count.toLocaleString()} px (${result.orange_coverage_percent}% coverage).`, 'success');
            } catch (err) {
                setTerminalStatus('ERROR', false, 'idle');
                statusEl.textContent = `Quantification error: ${err.message}`;
                logTerminal(`Quantification error: ${err.message}`, 'error');
            } finally {
                btnCountOrange.disabled = false;
            }
        });
    }

    // 14. Multi-Image Spec Comparison Matrix Modal
    btnOpenComparison.addEventListener('click', async () => {
        if (!batchResultsCache || batchResultsCache.length === 0) {
            try {
                const res = await fetch('/api/batch_results');
                batchResultsCache = await res.json();
            } catch (e) {}
        }

        renderComparisonMatrix();
        comparisonModalEl.classList.remove('hidden');
        logTerminal('Opened Multi-Image Spec Comparison Matrix.', 'info');
    });

    btnCloseModal.addEventListener('click', () => { comparisonModalEl.classList.add('hidden'); });

    function renderComparisonMatrix() {
        let selectedRecords = batchResultsCache;
        
        if (selectedComparisonFiles.size > 0) {
            selectedRecords = batchResultsCache.filter(r => 
                selectedComparisonFiles.has(r.filename) || selectedComparisonFiles.has(r.filepath)
            );
        }

        if (!selectedRecords || selectedRecords.length === 0) {
            selectedRecords = batchResultsCache;
        }

        if (!selectedRecords || selectedRecords.length === 0) {
            matrixContainerEl.innerHTML = '<p>No image data cached in dataset.</p>';
            return;
        }

        let tableHtml = `<table class="matrix-table">
            <thead>
                <tr>
                    <th style="vertical-align:bottom;">FEATURE / METRIC</th>
                    ${selectedRecords.map(r => `
                        <th style="text-align:center;">
                            <img src="/api/image/overlay?path=${encodeURIComponent(r.filepath)}&type=viability&max_dim=400" 
                                 style="width:170px; height:125px; object-fit:cover; border-radius:6px; border:1px solid #30363d; margin-bottom:8px; display:block; margin-left:auto; margin-right:auto;" 
                                 alt="${r.filename}">
                            <b>${r.filename}</b><br><span class="badge">${r.folder}</span>
                        </th>
                    `).join('')}
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><b>Sample Type</b></td>
                    ${selectedRecords.map(r => `<td><span class="badge">${r.sample_type}</span></td>`).join('')}
                </tr>
                <tr>
                    <td><b>Treatment Condition</b></td>
                    ${selectedRecords.map(r => `<td><span class="badge">${r.condition}</span></td>`).join('')}
                </tr>
                <tr>
                    <td><b>Sample ID</b></td>
                    ${selectedRecords.map(r => `<td>${r.sample_id}</td>`).join('')}
                </tr>
                <tr>
                    <td><b>Total Organoids (Cellpose)</b></td>
                    ${selectedRecords.map(r => `<td class="stat-bold">${r.total_organoids.toLocaleString()}</td>`).join('')}
                </tr>
                <tr>
                    <td><b>Dead Organoids (Red)</b></td>
                    ${selectedRecords.map(r => `<td style="color:#f87171; font-weight:700;">${r.dead_organoids.toLocaleString()}</td>`).join('')}
                </tr>
                <tr>
                    <td><b>Live Organoids (Blue)</b></td>
                    ${selectedRecords.map(r => `<td style="color:#38bdf8; font-weight:700;">${r.live_organoids.toLocaleString()}</td>`).join('')}
                </tr>
                <tr>
                    <td><b>Organoid Mortality Rate (%)</b></td>
                    ${selectedRecords.map(r => `<td style="color:#f87171; font-weight:700;">${r.mortality_rate_percent}%</td>`).join('')}
                </tr>
                <tr>
                    <td><b>Live NK Cells (Red Pixels)</b></td>
                    ${selectedRecords.map(r => `<td style="color:#f87171; font-weight:700;">${(r.nk_red_pixel_count || 0).toLocaleString()}</td>`).join('')}
                </tr>
                <tr>
                    <td><b>Dead NK Cells (Orange Pixels)</b></td>
                    ${selectedRecords.map(r => `<td style="color:#fb923c; font-weight:700;">${(r.orange_pixel_count || 0).toLocaleString()}</td>`).join('')}
                </tr>
            </tbody>
        </table>`;

        matrixContainerEl.innerHTML = tableHtml;
    }

    // Export Standalone HTML Comparison Report Handler
    btnExportComparisonHtml.addEventListener('click', async () => {
        const filesToExport = selectedComparisonFiles.size > 0 ? Array.from(selectedComparisonFiles) : batchResultsCache.map(r => r.filename);

        try {
            const res = await fetch('/api/export_comparison_html', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ selected_files: filesToExport })
            });
            const htmlBlob = await res.blob();

            const link = document.createElement("a");
            link.href = URL.createObjectURL(htmlBlob);
            link.download = "organoid_nk_comparison_report.html";
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            logTerminal('Exported standalone HTML comparison report.', 'success');
        } catch (err) {
            alert(`Failed to export comparison report: ${err.message}`);
        }
    });

    // Initialize dataset
    loadDataset();
});
