import sys
import numpy as np
import cv2

# Ensure user site-packages are in sys.path
if '/home/mrtemroztrk/.local/lib/python3.14/site-packages' not in sys.path:
    sys.path.append('/home/mrtemroztrk/.local/lib/python3.14/site-packages')

class ImageProcessor:
    """
    Intelligent image processing for microscopy channel isolation and enhancement.
    Isolates specific color channels (Green, Red, Orange/Yellow) by highlighting target colors
    and dimming/desaturating the non-target background.
    """

    @staticmethod
    def isolate_color_channel(img_rgb: np.ndarray, target_color: str = 'green', dim_factor: float = 0.25):
        """
        Isolates a specific color hue (green, red, orange/yellow) from the RGB image.
        Target colors remain bright and vibrant; background/other colors are dimmed to dark grayscale.

        target_color options: 'green', 'red', 'orange', 'original'
        """
        if target_color == 'original' or img_rgb.ndim != 3 or img_rgb.shape[2] < 3:
            return img_rgb

        # Convert RGB to HSV for precise color isolation
        hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

        # Define Hue ranges in OpenCV HSV format (H: 0-180, S: 0-255, V: 0-255)
        if target_color == 'green':
            # Green hue ~ 35 to 85, with minimum saturation & value
            mask = cv2.inRange(hsv, np.array([30, 30, 30]), np.array([90, 255, 255]))
        elif target_color == 'red':
            # Red hue wraps around 0/180
            mask1 = cv2.inRange(hsv, np.array([0, 40, 30]), np.array([12, 255, 255]))
            mask2 = cv2.inRange(hsv, np.array([160, 40, 30]), np.array([180, 255, 255]))
            mask = cv2.bitwise_or(mask1, mask2)
        elif target_color == 'orange':
            # Orange / Yellow hue ~ 10 to 35
            mask = cv2.inRange(hsv, np.array([10, 40, 30]), np.array([32, 255, 255]))
        else:
            return img_rgb

        # Smooth mask boundaries slightly
        mask_float = cv2.GaussianBlur(mask, (5, 5), 0).astype(np.float32) / 255.0
        mask_3d = np.stack([mask_float] * 3, axis=-1)

        # Convert original image to dark desaturated grayscale background
        gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
        dimmed_gray = (gray.astype(np.float32) * dim_factor).astype(np.uint8)
        background = np.stack([dimmed_gray] * 3, axis=-1)

        # Blend: Target colors retain original brightness; background is dimmed grayscale
        result = (img_rgb.astype(np.float32) * mask_3d + background.astype(np.float32) * (1.0 - mask_3d))
        return np.clip(result, 0, 255).astype(np.uint8)

    @staticmethod
    def adjust_contrast_brightness(channel: np.ndarray, brightness: float = 1.0, contrast: float = 1.0, gamma: float = 1.0):
        """Adjust brightness, contrast, and gamma of a single channel."""
        img = channel.astype(np.float32)
        img = img * contrast + (brightness - 1.0) * 128
        img = np.power(img / 255.0, gamma) * 255.0
        return np.clip(img, 0, 255).astype(np.uint8)

    @staticmethod
    def extract_channels(img_array: np.ndarray):
        """Splits RGB array into R, G, B channels."""
        if img_array.ndim == 2:
            return img_array, img_array, img_array
        h, w, c = img_array.shape
        r = img_array[:, :, 0] if c > 0 else np.zeros((h, w), dtype=img_array.dtype)
        g = img_array[:, :, 1] if c > 1 else np.zeros((h, w), dtype=img_array.dtype)
        b = img_array[:, :, 2] if c > 2 else np.zeros((h, w), dtype=img_array.dtype)
        return r, g, b

    @staticmethod
    def create_custom_composite(r: np.ndarray, g: np.ndarray, b: np.ndarray,
                                show_r: bool = True, show_g: bool = True, show_b: bool = True) -> np.ndarray:
        """Creates an RGB composite image from R, G, B single-channel arrays based on channel visibility."""
        h, w = r.shape[:2]
        r_out = r if show_r else np.zeros((h, w), dtype=np.uint8)
        g_out = g if show_g else np.zeros((h, w), dtype=np.uint8)
        b_out = b if show_b else np.zeros((h, w), dtype=np.uint8)
        return np.stack([r_out, g_out, b_out], axis=-1).astype(np.uint8)

    @staticmethod
    def apply_pseudocolor(channel: np.ndarray, color_mode: str = 'green') -> np.ndarray:
        """Applies pseudocolor / colormap visualization to a single-channel microscopy image."""
        if channel.ndim == 3 and channel.shape[2] == 3:
            channel = cv2.cvtColor(channel, cv2.COLOR_RGB2GRAY)
        
        h, w = channel.shape[:2]
        zeros = np.zeros((h, w), dtype=np.uint8)

        if color_mode == 'green':
            return np.stack([zeros, channel, zeros], axis=-1)
        elif color_mode == 'red':
            return np.stack([channel, zeros, zeros], axis=-1)
        elif color_mode == 'blue':
            return np.stack([zeros, zeros, channel], axis=-1)
        elif color_mode == 'cyan':
            return np.stack([zeros, channel, channel], axis=-1)
        elif color_mode == 'viridis':
            colormap_bgr = cv2.applyColorMap(channel, cv2.COLORMAP_VIRIDIS)
            return cv2.cvtColor(colormap_bgr, cv2.COLOR_BGR2RGB)
        else: # grayscale
            return np.stack([channel, channel, channel], axis=-1)

    @staticmethod
    def calculate_histograms(img_array: np.ndarray) -> dict:
        """Calculates intensity histogram data (256 bins) for R, G, and B channels."""
        histograms = {}
        if img_array.ndim == 3 and img_array.shape[2] >= 3:
            colors = [('Red', 0), ('Green', 1), ('Blue', 2)]
            for name, idx in colors:
                channel = img_array[:, :, idx]
                hist, _ = np.histogram(channel, bins=256, range=(0, 256))
                histograms[name] = hist
        else:
            flat = img_array.ravel()
            hist, _ = np.histogram(flat, bins=256, range=(0, 256))
            histograms['Grayscale'] = hist

        return histograms

