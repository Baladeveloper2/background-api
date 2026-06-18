import logging
from io import BytesIO
from typing import Tuple, List, Any

logger = logging.getLogger("idp.preprocessing")

class ImagePreprocessor:
    def __init__(self):
        try:
            import cv2
            import numpy as np
            self.cv2 = cv2
            self.np = np
            logger.info("OpenCV and Numpy loaded successfully for Preprocessing.")
        except Exception as e:
            self.cv2 = None
            self.np = None
            logger.warning(f"OpenCV/Numpy not available: {e}. Visual checks will be mocked.")

    def correct_exif_orientation(self, img_bytes: bytes) -> bytes:
        if img_bytes[:4] == b'%PDF':
            return img_bytes
            
        try:
            from PIL import Image, ExifTags
            pil_img = Image.open(BytesIO(img_bytes))
            orientation = None
            for key, value in pil_img.getexif().items():
                if key in ExifTags.TAGS and ExifTags.TAGS[key] == 'Orientation':
                    orientation = value
                    break
            
            if orientation is not None:
                if orientation == 3:
                    pil_img = pil_img.rotate(180, expand=True)
                elif orientation == 6:
                    pil_img = pil_img.rotate(270, expand=True)
                elif orientation == 8:
                    pil_img = pil_img.rotate(90, expand=True)
                
                out_bytes = BytesIO()
                pil_img.save(out_bytes, format=pil_img.format or 'PNG')
                return out_bytes.getvalue()
        except Exception as e:
            logger.warning(f"EXIF orientation correction failed: {e}")
        return img_bytes

    def deskew(self, image):
        if not self.cv2 or not self.np:
            return image
        try:
            gray = self.cv2.cvtColor(image, self.cv2.COLOR_BGR2GRAY)
            edges = self.cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = self.cv2.HoughLines(edges, 1, self.np.pi / 180, 200)
            if lines is None:
                return image
            angles = []
            for line in lines[:20]:
                rho, theta = line[0]
                angle = (theta - self.np.pi / 2) * 180 / self.np.pi
                if -45 <= angle <= 45:
                    angles.append(angle)
            if not angles:
                return image
            median_angle = float(self.np.median(angles))
            if abs(median_angle) < 0.5:
                return image
            h, w = image.shape[:2]
            center = (w // 2, h // 2)
            M = self.cv2.getRotationMatrix2D(center, median_angle, 1.0)
            rotated = self.cv2.warpAffine(image, M, (w, h), flags=self.cv2.INTER_CUBIC, borderMode=self.cv2.BORDER_REPLICATE)
            return rotated
        except Exception as e:
            logger.warning(f"Deskew failed: {e}")
            return image

    def crop_to_boundary(self, img):
        if not self.cv2 or not self.np:
            return img
        try:
            gray = self.cv2.cvtColor(img, self.cv2.COLOR_BGR2GRAY)
            blurred = self.cv2.GaussianBlur(gray, (5, 5), 0)
            edged = self.cv2.Canny(blurred, 50, 150)
            contours, _ = self.cv2.findContours(edged, self.cv2.RETR_EXTERNAL, self.cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return img
            
            largest_contour = max(contours, key=self.cv2.contourArea)
            area = self.cv2.contourArea(largest_contour)
            img_area = img.shape[0] * img.shape[1]
            
            if area > 0.20 * img_area:
                x, y, w, h = self.cv2.boundingRect(largest_contour)
                margin = 15
                x_start = max(0, x - margin)
                y_start = max(0, y - margin)
                x_end = min(img.shape[1], x + w + margin)
                y_end = min(img.shape[0], h + y + margin)
                return img[y_start:y_end, x_start:x_end]
            return img
        except Exception as e:
            logger.warning(f"Boundary cropping failed: {e}")
            return img

    def remove_shadows(self, img):
        if not self.cv2 or not self.np:
            return img
        try:
            planes = self.cv2.split(img)
            bg_planes = []
            for plane in planes:
                dilated_img = self.cv2.dilate(plane, self.np.ones((7, 7), self.np.uint8))
                bg_img = self.cv2.medianBlur(dilated_img, 21)
                bg_planes.append(bg_img)
            
            diff_planes = []
            for plane, bg_plane in zip(planes, bg_planes):
                diff_img = 255 - self.cv2.absdiff(plane, bg_plane)
                norm_img = self.cv2.normalize(diff_img, None, alpha=0, beta=255, norm_type=self.cv2.NORM_MINMAX, dtype=self.cv2.CV_8UC1)
                diff_planes.append(norm_img)
            return self.cv2.merge(diff_planes)
        except Exception as e:
            logger.warning(f"Shadow removal failed: {e}")
            return img

    def denoise(self, image):
        if not self.cv2:
            return image
        try:
            h, w = image.shape[:2]
            if h * w > 1920 * 1080:
                return self.cv2.bilateralFilter(image, 9, 75, 75)
            return self.cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)
        except Exception:
            return image

    def enhance_contrast(self, img):
        if not self.cv2:
            return img
        try:
            if len(img.shape) == 3:
                lab = self.cv2.cvtColor(img, self.cv2.COLOR_BGR2LAB)
                l, a, b = self.cv2.split(lab)
                clahe = self.cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                cl = clahe.apply(l)
                limg = self.cv2.merge((cl, a, b))
                return self.cv2.cvtColor(limg, self.cv2.COLOR_LAB2BGR)
            else:
                clahe = self.cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                return clahe.apply(img)
        except Exception:
            return img

    def sharpen(self, image):
        if not self.cv2 or not self.np:
            return image
        try:
            gaussian = self.cv2.GaussianBlur(image, (0, 0), 2.0)
            return self.cv2.addWeighted(image, 1.5, gaussian, -0.5, 0)
        except Exception:
            return image

    def perspective_correction(self, image):
        if not self.cv2 or not self.np:
            return image
        try:
            gray = self.cv2.cvtColor(image, self.cv2.COLOR_BGR2GRAY)
            blur = self.cv2.GaussianBlur(gray, (5, 5), 0)
            edged = self.cv2.Canny(blur, 75, 200)
            contours, _ = self.cv2.findContours(edged, self.cv2.RETR_EXTERNAL, self.cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return image
            contours = sorted(contours, key=self.cv2.contourArea, reverse=True)[:5]
            screenCnt = None
            for c in contours:
                peri = self.cv2.arcLength(c, True)
                approx = self.cv2.approxPolyDP(c, 0.02 * peri, True)
                if len(approx) == 4:
                    screenCnt = approx
                    break
            if screenCnt is None:
                return image
                
            # Perform a 4-point warp (simplified)
            pts = screenCnt.reshape(4, 2)
            rect = self.np.zeros((4, 2), dtype="float32")
            s = pts.sum(axis=1)
            rect[0] = pts[self.np.argmin(s)]
            rect[2] = pts[self.np.argmax(s)]
            diff = self.np.diff(pts, axis=1)
            rect[1] = pts[self.np.argmin(diff)]
            rect[3] = pts[self.np.argmax(diff)]
            
            (tl, tr, br, bl) = rect
            widthA = self.np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
            widthB = self.np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
            maxWidth = max(int(widthA), int(widthB))
            
            heightA = self.np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
            heightB = self.np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
            maxHeight = max(int(heightA), int(heightB))
            
            dst = self.np.array([
                [0, 0],
                [maxWidth - 1, 0],
                [maxWidth - 1, maxHeight - 1],
                [0, maxHeight - 1]], dtype="float32")
                
            M = self.cv2.getPerspectiveTransform(rect, dst)
            return self.cv2.warpPerspective(image, M, (maxWidth, maxHeight))
        except Exception as e:
            logger.warning(f"Perspective correction failed: {e}")
            return image

    def remove_background(self, image):
        if not self.cv2 or not self.np:
            return image
        try:
            # Simple thresholding approach for document background removal
            gray = self.cv2.cvtColor(image, self.cv2.COLOR_BGR2GRAY)
            _, mask = self.cv2.threshold(gray, 240, 255, self.cv2.THRESH_BINARY_INV)
            result = self.cv2.bitwise_and(image, image, mask=mask)
            # Create white background
            bg = self.np.ones_like(image, self.np.uint8) * 255
            self.cv2.bitwise_not(bg, bg, mask=mask)
            return result + bg
        except Exception:
            return image

    def super_resolution(self, image):
        # Stub for super resolution, e.g., using cv2.dnn_superres
        if not self.cv2:
            return image
        try:
            h, w = image.shape[:2]
            if h < 800 or w < 800:
                # Basic cubic interpolation as fallback for actual EDSR model
                return self.cv2.resize(image, (w * 2, h * 2), interpolation=self.cv2.INTER_CUBIC)
            return image
        except Exception:
            return image

    def preprocess_image_pipeline(self, img) -> Tuple[Any, List[str]]:
        steps = []
        if not self.cv2 or not self.np:
            return img, steps
        try:
            h, w = img.shape[:2]
            # Resize maximum width to 1500px to speed up processing
            if w > 1500:
                scale = 1500 / w
                img = self.cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=self.cv2.INTER_AREA)
                steps.append("RESIZE_1500PX")

            cropped = self.crop_to_boundary(img)
            if cropped.shape[0] != img.shape[0] or cropped.shape[1] != img.shape[1]:
                img = cropped
                steps.append("BOUNDARY_DETECTION")

            perspective = self.perspective_correction(img)
            if perspective is not img:
                img = perspective
                steps.append("PERSPECTIVE_CORRECTION")

            deskewed = self.deskew(img)
            if deskewed is not img:
                img = deskewed
                steps.append("DESKEW")

            shadow_removed = self.remove_shadows(img)
            if shadow_removed is not img:
                img = shadow_removed
                steps.append("SHADOW_REMOVAL")

            bg_removed = self.remove_background(img)
            if bg_removed is not img:
                img = bg_removed
                steps.append("BACKGROUND_REMOVAL")

            # Convert grayscale
            if len(img.shape) == 3:
                gray = self.cv2.cvtColor(img, self.cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            img = gray
            steps.append("GRAYSCALE")

            denoised = self.denoise(img)
            if denoised is not img:
                img = denoised
                steps.append("DENOISE")

            contrast_enhanced = self.enhance_contrast(img)
            if contrast_enhanced is not img:
                img = contrast_enhanced
                steps.append("CONTRAST_ENHANCEMENT")

            sharpened = self.sharpen(img)
            if sharpened is not img:
                img = sharpened
                steps.append("SHARPENING")

            # Adaptive Threshold
            img = self.cv2.adaptiveThreshold(
                img, 255, self.cv2.ADAPTIVE_THRESH_GAUSSIAN_C, self.cv2.THRESH_BINARY, 11, 2
            )
            steps.append("ADAPTIVE_THRESHOLD")

            return img, steps
        except Exception as e:
            logger.warning(f"Internal preprocessing failed: {e}")
            return img, steps

    def pdf_to_images(self, pdf_bytes: bytes) -> Tuple[List[Any], List[str]]:
        images = []
        steps = []
        try:
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                zoom = 300 / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                
                if self.np and self.cv2:
                    nparr = self.np.frombuffer(img_data, self.np.uint8)
                    img = self.cv2.imdecode(nparr, self.cv2.IMREAD_COLOR)
                    if img is not None:
                        images.append(img)
            if images:
                steps.append("PDF_TO_IMAGE_300DPI_PYMUPDF")
                return images, steps
        except Exception as e:
            logger.warning(f"PyMuPDF failed to convert PDF: {e}")
            
        try:
            from pdf2image import convert_from_bytes
            pil_images = convert_from_bytes(pdf_bytes, dpi=300)
            for pil_img in pil_images:
                img_byte_arr = BytesIO()
                pil_img.save(img_byte_arr, format='PNG')
                if self.np and self.cv2:
                    nparr = self.np.frombuffer(img_byte_arr.getvalue(), self.np.uint8)
                    img = self.cv2.imdecode(nparr, self.cv2.IMREAD_COLOR)
                    if img is not None:
                        images.append(img)
            if images:
                steps.append("PDF_TO_IMAGE_300DPI_PDF2IMAGE")
                return images, steps
        except Exception as e:
            logger.error(f"pdf2image failed to convert PDF: {e}")
            
        return images, steps
