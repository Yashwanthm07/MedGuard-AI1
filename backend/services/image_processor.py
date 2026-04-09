"""Image processing and validation service."""
import cv2
import numpy as np
from PIL import Image, ImageEnhance
import io
import base64
from typing import Tuple, Optional


class ImageProcessor:
    """Handles image validation, preprocessing, and feature extraction."""

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    VALID_FORMATS = {'image/jpeg', 'image/png', 'image/webp', 'image/bmp', 'image/gif'}

    @staticmethod
    def validate_image_file(image_data: bytes, mime_type: str) -> Tuple[bool, Optional[str]]:
        """
        Validate uploaded image.

        Returns: (is_valid, error_message)
        """
        # Check file size
        if len(image_data) > ImageProcessor.MAX_FILE_SIZE:
            return False, "Image size exceeds 10MB limit"

        # Check MIME type
        if mime_type not in ImageProcessor.VALID_FORMATS:
            return False, f"Unsupported image format: {mime_type}"

        # Try to open as image
        try:
            Image.open(io.BytesIO(image_data))
        except Exception as e:
            return False, f"Invalid image file: {str(e)}"

        return True, None

    @staticmethod
    def deskew_image(cv_image: np.ndarray) -> np.ndarray:
        """
        Deskew/rotate image if tilted (handles real-world phone images).
        
        Returns: Deskewed OpenCV image
        """
        try:
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY) if len(cv_image.shape) == 3 else cv_image
            
            # Find text regions
            coords = np.column_stack(np.where(gray > 0))
            
            if len(coords) == 0:
                return cv_image
            
            # Get rotation angle
            angle = cv2.minAreaRect(coords)[-1]
            
            # Adjust angle
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            
            # Skip if rotation is minimal
            if abs(angle) < 2:
                return cv_image
            
            # Rotate image
            (h, w) = gray.shape[:2]
            M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
            rotated = cv2.warpAffine(cv_image, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
            
            return rotated
        except Exception as e:
            import logging
            logging.warning(f"Deskew failed: {e}")
            return cv_image

    @staticmethod
    def load_image(image_base64: str) -> Tuple[Optional[Image.Image], Optional[np.ndarray]]:
        """
        Load image from base64 string.

        Returns: (PIL_Image, OpenCV_BGR_array)
        """
        try:
            image_data = base64.b64decode(image_base64)
            pil_image = Image.open(io.BytesIO(image_data))

            # Convert to BGR for OpenCV
            if pil_image.mode == 'RGBA':
                pil_image = pil_image.convert('RGB')

            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            return pil_image, cv_image
        except Exception as e:
            print(f"Error loading image: {e}")
            return None, None

    @staticmethod
    def preprocess_image(pil_image: Image.Image) -> Image.Image:
        """
        UPGRADE: Full preprocessing pipeline optimized for OCR.
        """
        img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        
        # Resize for better OCR
        height, width = img.shape[:2]

        # Downscale very large uploads to keep OCR latency stable.
        max_dim = 1800
        largest_dim = max(width, height)
        if largest_dim > max_dim and largest_dim > 0:
            scale = max_dim / float(largest_dim)
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            height, width = img.shape[:2]

        if width < 300 or height < 300:
            scale = max(300 / width, 300 / height) if width > 0 else 1.5
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        
        # Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Remove noise
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Adaptive threshold (much better for medicine text)
        thresh = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )
        
        # Enhance edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)
        
        return Image.fromarray(thresh)

    @staticmethod
    def get_edge_density(cv_image: np.ndarray) -> float:
        """
        Calculate edge density using Canny edge detection.

        Returns: Edge density percentage (0-100)
        """
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_pixels = np.count_nonzero(edges)
        total_pixels = edges.size

        density = (edge_pixels / total_pixels) * 100 if total_pixels > 0 else 0
        return float(density)

    @staticmethod
    def get_color_variance(cv_image: np.ndarray) -> float:
        """
        Calculate color variance (detects uniform/blank images).

        Returns: Color variance percentage (0-100)
        """
        # Convert to HSV for better color analysis
        hsv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)

        # Calculate variance for each channel
        h_var = np.var(hsv[:,:,0])
        s_var = np.var(hsv[:,:,1])
        v_var = np.var(hsv[:,:,2])

        # Normalize to 0-100 (FIXED MATH)
        avg_var = (h_var + s_var + v_var) / 3.0
        # Proper normalization: scale to 0-100 range
        variance_pct = min(100, avg_var / 50)  # 50 is typical max for real images

        return float(variance_pct)

    @staticmethod
    def get_text_density(cv_image: np.ndarray) -> float:
        """
        IMPROVED: Better text detection using morphological operations.

        Returns: Text density percentage (0-100)
        """
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        
        # Better text detection: threshold + morphology (not just edges)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(gray, kernel, iterations=1)
        
        # Threshold to find dark regions (text)
        _, thresh = cv2.threshold(dilated, 150, 255, cv2.THRESH_BINARY_INV)
        
        # Count text regions
        text_pixels = np.count_nonzero(thresh)
        total_pixels = thresh.size
        
        density = (text_pixels / total_pixels) * 100 if total_pixels > 0 else 0
        return float(min(100, density))

    @staticmethod
    def check_if_likely_medicine(cv_image: np.ndarray) -> Tuple[bool, float]:
        """
        Heuristic check if image likely contains medicine packaging.

        Returns: (is_likely_medicine, confidence_0_100)
        """
        edge_density = ImageProcessor.get_edge_density(cv_image)
        color_variance = ImageProcessor.get_color_variance(cv_image)
        text_density = ImageProcessor.get_text_density(cv_image)

        # Medicine packaging typically has:
        # - Moderate to high edge density (borders, text)
        # - Good color variance (not blank)
        # - Text density (labels)

        checks = []

        # Edge density check (medicine packaging typically 10-60%)
        if 10 <= edge_density <= 60:
            checks.append(True)
        else:
            checks.append(False)

        # Color variance check (not blank)
        if color_variance > 5:
            checks.append(True)
        else:
            checks.append(False)

        # Text density check (medicine labels have text)
        if text_density > 3:
            checks.append(True)
        else:
            checks.append(False)

        # IMPROVED: Weighted scoring instead of binary checks
        # Different features matter differently for medicine detection
        score = (
            edge_density * 0.3 +      # 30%: structure/borders
            color_variance * 0.3 +    # 30%: color information
            text_density * 0.4        # 40%: text labels (most important)
        )
        
        # Medicine packaging typically scores 20-80
        is_likely = score > 20
        confidence = min(100, score)
        
        # Additional check: reject overly uniform/blank images (generated)
        hsv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
        h_std = np.std(hsv[:,:,0])
        if h_std < 3:  # Too uniform = likely not medicine
            is_likely = False
            confidence = min(confidence, 30)

        return is_likely, float(confidence)
