import streamlit as st
import os
import numpy as np
import pandas as pd
from PIL import Image

# Import local modular package components
from src.dataset import DatasetScanner
from src.image_processing import ImageProcessor
from src.organoid_analyzer import OrganoidAnalyzer
from src.viewer_utils import ViewerUtils

# Page setup
st.set_page_config(
    page_title="Organoid Microscopy & Green Dye Analyzer",
    page_icon="🧫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Dark Glassmorphism UI)
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    .stAppHeader {
        background-color: rgba(14, 17, 23, 0.8);
    }
    .css-1d37wda, .stSidebar {
        background-color: #161b22 !important;
        border-right: 1px solid #30363d;
    }
    .metric-box {
        background: linear-gradient(135deg, rgba(35, 134, 54, 0.15), rgba(22, 27, 34, 0.8));
        border: 1px solid #238636;
        border-radius: 8px;
        padding: 14px;
        text-align: center;
        margin-bottom: 10px;
    }
    .metric-title {
        color: #8b949e;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-val {
        color: #3fb950;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .meta-badge {
        background-color: #21262d;
        color: #c9d1d9;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        border: 1px solid #30363d;
        display: inline-block;
        margin-right: 6px;
        margin-bottom: 6px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize dataset scanner
@st.cache_resource
def get_scanner():
    return DatasetScanner("data")

scanner = get_scanner()

# Header
st.title("🧫 Heidelberg Organoid Mikroskopi ve Yeşil Boya (Ölü Organoid) Analiz Paneli")
st.caption("Çok kanallı mikroskopi görüntü gezgini, floresan yeşil boya leke/obje tespiti ve hücresel görünürlük analitiği.")

# SIDEBAR: File Explorer & Image Controls
st.sidebar.header("📁 Dosya Gezgini")

folder_map = scanner.scan_directories()

if not folder_map:
    st.sidebar.error("❌ 'data' dizininde .tif uzantılı görsel bulunamadı!")
    st.stop()

# Folder selector
selected_folder = st.sidebar.selectbox(
    "Klasör Seçin:",
    options=list(folder_map.keys()),
    index=0
)

# File selector inside folder
files_in_folder = folder_map[selected_folder]
file_names = [os.path.basename(f) for f in files_in_folder]
selected_file_name = st.sidebar.selectbox(
    "Görsel Seçin:",
    options=file_names,
    index=0
)

selected_filepath = os.path.join("data", selected_folder, selected_file_name) if selected_folder != "Root" else os.path.join("data", selected_file_name)

# Display parsed metadata in sidebar
metadata = scanner.parse_filename_metadata(selected_filepath)

st.sidebar.markdown("---")
st.sidebar.subheader("ℹ️ Görsel Özellikleri")
st.sidebar.markdown(f"""
<span class="meta-badge">Örnek: <b>{metadata['sample_type']}</b></span>
<span class="meta-badge">Koşul: <b>{metadata['condition']}</b></span>
<span class="meta-badge">ID: <b>{metadata['sample_id']}</b></span>
<span class="meta-badge">Kanal: <b>{metadata['channels_hint']}</b></span>
""", unsafe_allow_html=True)

# Load Image
@st.cache_data
def load_img(path):
    return scanner.load_image(path)

img_pil, img_arr = load_img(selected_filepath)
h, w = img_arr.shape[:2]
st.sidebar.caption(f"📐 Çözünürlük: **{w} x {h} px** | Dosya: **{round(os.path.getsize(selected_filepath)/(1024*1024), 2)} MB**")

# Channel Extraction
r_ch, g_ch, b_ch = ImageProcessor.extract_channels(img_arr)

# Image Adjustments Sidebar Controls
st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ Kanal & İyileştirme Ayarları")

col_adj1, col_adj2 = st.sidebar.columns(2)
brightness = col_adj1.slider("Parlaklık", 0.5, 2.5, 1.0, 0.1)
contrast = col_adj2.slider("Kontrast", 0.5, 2.5, 1.0, 0.1)
gamma = st.sidebar.slider("Gama (Gamma)", 0.3, 3.0, 1.0, 0.1)

st.sidebar.markdown("**Görünür Kanallar:**")
show_red = st.sidebar.checkbox("Kırmızı Kanal (Red)", value=True)
show_green = st.sidebar.checkbox("Yeşil Kanal (Green Dye)", value=True)
show_blue = st.sidebar.checkbox("Mavi Kanal (Blue/DAPI)", value=True)

green_pseudocolor = st.sidebar.selectbox(
    "Yeşil Kanal Renklendirmesi (Pseudo-color):",
    options=['green', 'viridis', 'grayscale', 'cyan'],
    index=0
)

# Apply adjustments
r_adj = ImageProcessor.adjust_contrast_brightness(r_ch, brightness, contrast, gamma)
g_adj = ImageProcessor.adjust_contrast_brightness(g_ch, brightness, contrast, gamma)
b_adj = ImageProcessor.adjust_contrast_brightness(b_ch, brightness, contrast, gamma)

composite_adj = ImageProcessor.create_custom_composite(r_adj, g_adj, b_adj, show_red, show_green, show_blue)

# MAIN CONTENT TABS
tab_inspect, tab_analysis, tab_dataset, tab_gpu = st.tabs([
    "🔬 Görsel İnceleyici & Kanal Ayrıştırma",
    "🟢 Ölü Organoid (Yeşil Boya) Obje Analizi",
    "📊 Veriseti Özet Tablosu",
    "💻 GPU (GTX 1650 Ti) & Model Rehberi"
])

# TAB 1: Visual Inspector
with tab_inspect:
    st.subheader(f"🔍 Görsel: `{selected_file_name}`")
    
    col_main_img, col_channels = st.columns([1.4, 1.0])
    
    with col_main_img:
        st.markdown("##### Birleşik Görsel (Composite Overlay)")
        st.image(composite_adj, use_container_width=True, caption=f"RGB Birleşik Görünüm ({w}x{h} px)")
        
    with col_channels:
        st.markdown("##### Ayrıştırılmış Kanallar (Separated Channels)")
        
        sub_t1, sub_t2, sub_t3 = st.tabs(["🟢 Yeşil (Ölü Organoid Dye)", "🔴 Kırmızı", "🔵 Mavi"])
        
        with sub_t1:
            g_colored = ImageProcessor.apply_pseudocolor(g_adj, color_mode=green_pseudocolor)
            st.image(g_colored, use_container_width=True, caption="Yeşil Floresan Boya Kanalı")
            
        with sub_t2:
            r_colored = ImageProcessor.apply_pseudocolor(r_adj, color_mode='red')
            st.image(r_colored, use_container_width=True, caption="Kırmızı Kanal")
            
        with sub_t3:
            b_colored = ImageProcessor.apply_pseudocolor(b_adj, color_mode='blue')
            st.image(b_colored, use_container_width=True, caption="Mavi Kanal")
            
    st.markdown("---")
    st.markdown("##### 📈 Piksel Yoğunluk Histogramı (Intensity Distribution)")
    hist_dict = ImageProcessor.calculate_histograms(composite_adj)
    fig_hist = ViewerUtils.generate_histogram_plot(hist_dict)
    st.pyplot(fig_hist)


# TAB 2: Object Analysis (Dead Organoids / Green Stain)
with tab_analysis:
    st.subheader("🟢 Yeşil Boya Tutan Ölü Organoid Obje Segmentasyonu ve Sayımı")
    st.info("💡 **Bilgi:** Araştırmacı tarafından organoidlere verilen yeşil floresan boya ölü organoidler tarafından tutulmaktadır. Boyanın akıp sızdığı alanları elimine etmek için arka plan süzme (Top-hat morphology) ve eşikleme parametrelerini aşağıdan ayarlayabilirsiniz.")
    
    analyzer = OrganoidAnalyzer()
    
    col_params, col_viz = st.columns([1.0, 1.5])
    
    with col_params:
        st.markdown("#### ⚙️ Segmentasyon Parametreleri")
        
        detection_method = st.radio(
            "Segmentasyon Yöntemi:",
            ["🤖 Cellpose AI Segmentasyonu (Tavsiye Edilen)", "Eşikleme + Watershed", "LoG Blob (Leke) Tespiti"]
        )
        
        if detection_method == "🤖 Cellpose AI Segmentasyonu (Tavsiye Edilen)":
            cp_model_type = st.selectbox("Cellpose Model Tipi:", ["cyto3", "cyto2", "cyto", "nuclei"], index=0)
            cp_diameter = st.slider("Tahmini Organoid Çapı (px):", 10, 150, 60, step=5)
            cp_min_intensity = st.slider("Ölü Hücre Yeşil Yoğunluk Eşiği (0-255):", 5, 200, 35, step=5)
            
            with st.spinner("🤖 Cellpose AI modeli ile organoidler analiz ediliyor..."):
                summary_cp, overlay_img, df_organoids = analyzer.extract_organoid_features(
                    img_arr,
                    min_green_pixels_threshold=1,
                    min_green_intensity=cp_min_intensity,
                    diameter=float(cp_diameter),
                    model_type=cp_model_type
                )
            label_mask = None

        elif detection_method == "Eşikleme + Watershed":
            thresh_val = st.slider("Yeşil Yoğunluk Eşiği (Threshold 0-255):", 10, 200, 55, step=5)
            tophat_k = st.slider("Arka Plan Boya Sızıntısı Süzgeci (Top-Hat Kernel):", 0, 45, 15, step=2, 
                                 help="Akan/sızan arka plan yeşil boyasını siler. Organoidlerin boyutuna göre ayarlayın.")
            min_area = st.slider("Min Organoid Alanı (piksel):", 5, 500, 25, step=5)
            max_area = st.number_input("Max Organoid Alanı (piksel):", min_value=100, max_value=50000, value=15000, step=500)
            min_circ = st.slider("Min Dairesellik (Circularity 0-1):", 0.0, 1.0, 0.15, step=0.05, 
                                 help="Tam yuvarlak organoidler için 1.0'a yaklaştırın; sızmış düzensiz yapıları filtresiz bırakmak için düşürün.")
            use_ws = st.checkbox("Birbirine Değen Organoidleri Ayır (Watershed)", value=True)
            
            # Run threshold segmentation
            label_mask, df_organoids, overlay_img = analyzer.detect_dead_organoids_threshold(
                g_ch, intensity_threshold=thresh_val, min_area=min_area, max_area=max_area,
                min_circularity=min_circ, use_watershed=use_ws, tophat_kernel=tophat_k
            )
            
        else: # LoG Blob
            min_s = st.slider("Min Sigma (Küçük Lekeler):", 1.0, 10.0, 2.0, 0.5)
            max_s = st.slider("Max Sigma (Büyük Lekeler):", 5.0, 40.0, 15.0, 1.0)
            threshold_log = st.slider("Blob Hassasiyeti (Threshold):", 0.01, 0.3, 0.05, 0.01)
            
            df_organoids, overlay_img = analyzer.detect_blobs_log(
                g_ch, min_sigma=min_s, max_sigma=max_s, threshold=threshold_log
            )
            label_mask = None

        stats = analyzer.get_summary_statistics(df_organoids, g_ch)
        
    with col_viz:
        st.markdown("#### 🎯 Tespit Edilen Ölü Organoidler (Overlay)")
        st.image(overlay_img, use_container_width=True, caption=f"Yeşil boya tespiti yapılan {len(df_organoids)} organoid bölgesi.")
        
    st.markdown("---")
    st.markdown("### 📊 Sayısal Analiz ve Metrikler")
    
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">Tespit Edilen Ölü Organoid</div>
            <div class="metric-val">{stats['detected_organoid_count']}</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">Toplam Ölü Alan (px)</div>
            <div class="metric-val">{stats['total_dead_organoid_area_px']:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">Ölü Organoid Alan Oranı</div>
            <div class="metric-val">%{stats['area_coverage_percent']}</div>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-title">Ortalama Yeşil Yoğunluğu</div>
            <div class="metric-val">{stats['avg_organoid_green_intensity']}</div>
        </div>
        """, unsafe_allow_html=True)
        
    if not df_organoids.empty:
        st.markdown("#### 📄 Tespit Edilen Organoidlerin Liste Tablosu")
        st.dataframe(df_organoids, use_container_width=True)
        
        csv_bytes = ViewerUtils.df_to_csv_bytes(df_organoids)
        st.download_button(
            label="📥 Organoid Verilerini CSV Olarak İndir",
            data=csv_bytes,
            file_name=f"organoid_analysis_{selected_file_name}.csv",
            mime="text/csv"
        )


# TAB 3: Dataset Summary Table
with tab_dataset:
    st.subheader("📊 Tüm Veriseti Özet Tablosu")
    df_summary = scanner.get_image_summary_table()
    st.dataframe(df_summary, use_container_width=True)
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.markdown("**Örnek Tiplerine Göre Dağılım:**")
        st.bar_chart(df_summary['sample_type'].value_counts())
    with col_d2:
        st.markdown("**Deney Koşullarına (Condition) Göre Dağılım:**")
        st.bar_chart(df_summary['condition'].value_counts())


# TAB 4: GPU & Deep Learning Guide
with tab_gpu:
    st.subheader("💻 NVIDIA GTX 1650 Ti (4GB VRAM) & Derin Öğrenme Segmentasyonu")
    
    st.markdown("""
    ### ⚡ Donanım Değerlendirmesi:
    - **Ekran Kartı:** NVIDIA GTX 1650 Ti (4 GB VRAM)
    - **Sistem Belleği:** 32 GB RAM
    - **İşletim Sistemi:** Linux
    
    > **Sonuç:** GTX 1650 Ti (4 GB VRAM) biyomedikal hücre/organoid segmentasyon modellerini çalıştırmak için **tamamen yeterlidir**! 32 GB RAM de büyük TIFF dosyalarını bellekte işlemek için son derece konforludur.

    ---

    ### 🚀 Tavsiye Edilen Gelecek Aşama Derin Öğrenme Modelleri:

    #### 1. **Cellpose 2.0 / 3.0 (Tavsiye Edilen #1)**
    - **Neden?** Mikroskopi görüntülerinde düzensiz, akmış, sızmış floresan boya tutan organoid ve hücre zarlarını tespit etmede dünya standardıdır.
    - **Kurulum:**
      ```bash
      pip install cellpose[gui] torch torchvision --extra-index-url https://download.pytorch.org/whl/cu118
      ```
    - **GTX 1650 Ti Optimize Kullanımı (Python):**
      ```python
      from cellpose import models
      # 4GB VRAM için gpu=True ve varsayılan cyto2 veya cyto3 modeli kullanabilirsiniz
      model = models.Cellpose(gpu=True, model_type='cyto3')
      masks, flows, styles, diams = model.eval(image_green, diameter=None, channels=[0,0])
      ```

    #### 2. **Segment Anything (SAM) / MobileSAM / SAM2**
    - **Neden?** Sıfırdan eğitmeye gerek kalmadan organoid sınırlarını tıklama veya kutu işaretlemesi ile anında segmente eder.
    - **Memory Optimizer:** 4GB VRAM sınırına takılmamak için `MobileSAM` veya `vit_b` (base) SAM ağırlıkları tercih edilmelidir.

    #### 3. **StarDist**
    - **Neden?** Dairesel ve küresel organoid ve çekirdek yapılarını saymada çok hızlıdır.
    ```python
    from stardist.models import StarDist2D
    model = StarDist2D.from_pretrained('2D_versatile_fluo')
    labels, details = model.predict_instances(normalize(green_channel))
    ```
    """)

