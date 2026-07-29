import matplotlib.pyplot as plt
import io
from PIL import Image
import pandas as pd
import numpy as np

class ViewerUtils:
    """
    Utility functions for generating UI visualizations, charts, and exportable reports.
    """
    
    @staticmethod
    def generate_histogram_plot(histograms_dict):
        """
        Creates a matplotlib plot figure for R, G, B histograms.
        """
        fig, ax = plt.subplots(figsize=(6, 2.5), dpi=100)
        fig.patch.set_facecolor('#0e1117')
        ax.set_facecolor('#161b22')
        
        color_map = {'Red': '#ff4d4d', 'Green': '#2ecc71', 'Blue': '#3498db', 'Grayscale': '#bdc3c7'}
        
        for name, hist in histograms_dict.items():
            c = color_map.get(name, '#ffffff')
            ax.plot(hist, color=c, alpha=0.85, label=name, linewidth=1.5)
            
        ax.set_xlim([0, 256])
        ax.set_title("Channel Pixel Intensity Histogram", color="#ffffff", fontsize=10, pad=8)
        ax.set_xlabel("Pixel Value (0 - 255)", color="#a3b1c6", fontsize=8)
        ax.set_ylabel("Pixel Count", color="#a3b1c6", fontsize=8)
        ax.tick_params(colors='#a3b1c6', labelsize=7)
        for spine in ax.spines.values():
            spine.set_color('#30363d')
            
        ax.legend(facecolor='#161b22', edgecolor='#30363d', labelcolor='#ffffff', fontsize=8)
        fig.tight_layout()
        return fig

    @staticmethod
    def df_to_csv_bytes(df: pd.DataFrame):
        """
        Converts pandas DataFrame to CSV bytes for download button.
        """
        return df.to_csv(index=False).encode('utf-8')
