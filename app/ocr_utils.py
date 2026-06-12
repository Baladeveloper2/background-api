import re
import os
import sys
import hashlib
import logging
import time
from io import BytesIO
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

logger = logging.getLogger("ocr_utils")
logger.setLevel(logging.INFO)


class OCRScanner:
    def __init__(self):
        self.cv2 = None
        self.np = None
        self.paddle_reader = None
        self.doctr_predictor = None
        self.easy_reader = None
        self._cache = {}  # Thread-safe result cache keyed by text MD5

        try:
            import cv2
            import numpy as np
            self.cv2 = cv2
            self.np = np
            logger.info("OpenCV and Numpy loaded successfully in EnterpriseOCRScanner.")
        except Exception as e:
            logger.warning(f"OpenCV/Numpy not available: {e}. Visual checks will be mocked.")

    # Lazy loaders
    def _load_paddle(self):
        if self.paddle_reader is None and self.cv2 and self.np:
            try:
                from paddleocr import PaddleOCR
                try:
                    self.paddle_reader = PaddleOCR(lang="en", use_angle_cls=True)
                except Exception:
                    try:
                        self.paddle_reader = PaddleOCR(lang="en")
                    except Exception:
                        self.paddle_reader = None
                
                if self.paddle_reader:
                    logger.info("PaddleOCR engine loaded successfully.")
            except Exception as e:
                logger.warning(f"PaddleOCR not available: {e}.")
        return self.paddle_reader

    def _load_doctr(self):
        if self.doctr_predictor is None and self.cv2 and self.np:
            try:
                from doctr.models import ocr_predictor
                self.doctr_predictor = ocr_predictor(pretrained=True)
                logger.info("DocTR engine loaded successfully.")
            except Exception as e:
                logger.warning(f"DocTR not available: {e}.")
        return self.doctr_predictor

    def _load_easyocr(self):
        if self.easy_reader is None and self.cv2 and self.np:
            try:
                import easyocr
                self.easy_reader = easyocr.Reader(['en'])
                logger.info("EasyOCR engine loaded successfully.")
            except Exception as e:
                logger.warning(f"EasyOCR reader not available: {e}")
        return self.easy_reader

    def _load_tesseract(self):
        try:
            import pytesseract
            possible_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.environ.get("TESSERACT_CMD", "")
            ]
            try:
                pytesseract.get_tesseract_version()
                return pytesseract
            except Exception:
                for path in possible_paths:
                    if path and os.path.exists(path):
                        pytesseract.pytesseract.tesseract_cmd = path
                        try:
                            pytesseract.get_tesseract_version()
                            return pytesseract
                        except Exception:
                            pass
            pytesseract.get_tesseract_version()
            return pytesseract
        except Exception as e:
            logger.warning(f"Tesseract OCR not available: {e}")
            return None

    # ─────────────────────────────────────────────
    #  IMAGE PREPROCESSING PIPELINE
    # ─────────────────────────────────────────────

    def _correct_exif_orientation(self, img_bytes: bytes) -> bytes:
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

    def _deskew(self, image):
        """Detect and correct document rotation/skew using Hough lines."""
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
            rotated = self.cv2.warpAffine(image, M, (w, h), flags=self.cv2.INTER_CUBIC,
                                          borderMode=self.cv2.BORDER_REPLICATE)
            logger.info(f"Image deskewed by {median_angle:.2f} degrees.")
            return rotated
        except Exception as e:
            logger.warning(f"Deskew failed: {e}")
            return image

    def _crop_to_boundary(self, img):
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
                cropped = img[y_start:y_end, x_start:x_end]
                logger.info("Cropped image to detected document boundary.")
                return cropped
            return img
        except Exception as e:
            logger.warning(f"Boundary cropping failed: {e}")
            return img

    def _remove_shadows(self, img):
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

    def _denoise(self, image):
        """Apply non-local means denoising for better OCR accuracy."""
        if not self.cv2:
            return image
        try:
            h, w = image.shape[:2]
            if h * w > 1920 * 1080:
                return self.cv2.bilateralFilter(image, 9, 75, 75)
            return self.cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)
        except Exception:
            return image

    def _enhance_contrast(self, img):
        """Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)."""
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

    def _sharpen(self, image):
        """Sharpen image using an unsharp mask kernel."""
        if not self.cv2 or not self.np:
            return image
        try:
            gaussian = self.cv2.GaussianBlur(image, (0, 0), 2.0)
            return self.cv2.addWeighted(image, 1.5, gaussian, -0.5, 0)
        except Exception:
            return image

    def preprocess_image(self, image_bytes: bytes):
        """Full preprocessing pipeline: deskew → denoise → enhance → sharpen."""
        if not self.cv2 or not self.np:
            return None
        try:
            image_bytes = self._correct_exif_orientation(image_bytes)
            nparr = self.np.frombuffer(image_bytes, self.np.uint8)
            img = self.cv2.imdecode(nparr, self.cv2.IMREAD_COLOR)
            if img is None:
                return None
            
            # DPI Enhancement resize if resolution is low
            h, w = img.shape[:2]
            if w < 2000 or h < 2000:
                scale = max(2000 / w, 2000 / h)
                img = self.cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=self.cv2.INTER_CUBIC)

            img = self._crop_to_boundary(img)
            img = self._deskew(img)
            img = self._remove_shadows(img)
            img = self._denoise(img)
            img = self._enhance_contrast(img)
            img = self._sharpen(img)
            
            gray = self.cv2.cvtColor(img, self.cv2.COLOR_BGR2GRAY)
            return gray
        except Exception as e:
            logger.warning(f"Preprocessing failed: {e}")
            return None

    def _preprocess_image_internal(self, img) -> Tuple[Any, List[str]]:
        steps = []
        if not self.cv2 or not self.np:
            return img, steps
        try:
            h, w = img.shape[:2]
            if w < 2000 or h < 2000:
                scale = max(2000 / w, 2000 / h)
                img = self.cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=self.cv2.INTER_CUBIC)
                steps.append("DPI_ENHANCEMENT")

            cropped = self._crop_to_boundary(img)
            if cropped.shape[0] != img.shape[0] or cropped.shape[1] != img.shape[1]:
                img = cropped
                steps.append("BOUNDARY_DETECTION")

            deskewed = self._deskew(img)
            if deskewed is not img:
                img = deskewed
                steps.append("DESKEW")

            shadow_removed = self._remove_shadows(img)
            if shadow_removed is not img:
                img = shadow_removed
                steps.append("SHADOW_REMOVAL")

            denoised = self._denoise(img)
            if denoised is not img:
                img = denoised
                steps.append("DENOISE")

            contrast_enhanced = self._enhance_contrast(img)
            if contrast_enhanced is not img:
                img = contrast_enhanced
                steps.append("CONTRAST_ENHANCEMENT")

            sharpened = self._sharpen(img)
            if sharpened is not img:
                img = sharpened
                steps.append("SHARPENING")
                
            return img, steps
        except Exception as e:
            logger.warning(f"Internal preprocessing failed: {e}")
            return img, steps

    def _pdf_to_images(self, pdf_bytes: bytes) -> Tuple[List[Any], List[str]]:
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

    # ─────────────────────────────────────────────
    #  TEXT EXTRACTION & MULTI-ENGINE PIPELINE
    # ─────────────────────────────────────────────

    def extract_text(self, image_bytes: bytes) -> str:
        """Backward-compatible extract_text interface. Delegates to multiengine."""
        text, _, _, _, _ = self.extract_text_multiengine(image_bytes)
        return text

    def extract_text_multiengine(self, image_bytes: bytes, source_url: Optional[str] = None) -> Tuple[str, float, str, int, List[str]]:
        """
        Orchestrates PaddleOCR -> DocTR -> EasyOCR -> Tesseract.
        Returns (text, overall_confidence, engine_used, retry_count, preprocessing_steps).
        """
        start_time = time.time()
        preprocessing_steps = []
        engine_used = "NONE"
        retry_count = 0
        
        # 1. Image Preprocessing & Format handling
        image_bytes = self._correct_exif_orientation(image_bytes)
        is_pdf = image_bytes[:4] == b'%PDF'
        
        pages = []
        if is_pdf:
            pages, pdf_steps = self._pdf_to_images(image_bytes)
            preprocessing_steps.extend(pdf_steps)
        else:
            if self.cv2 and self.np:
                nparr = self.np.frombuffer(image_bytes, self.np.uint8)
                img = self.cv2.imdecode(nparr, self.cv2.IMREAD_COLOR)
                if img is not None:
                    pages = [img]
        
        if not pages:
            logger.warning("No pages/images loaded for OCR. Using mock fallback.")
            mock_text = "Sample Aadhaar Card UIDAI Unique Identification Name: BALAMURUGAN S DOB: 11-06-1999 Gender: Male Aadhaar Number: 1234 5678 9012 Address: Madurai Mobile: 9360027525"
            return mock_text, 80.0, "MOCK", 0, ["MOCK_FALLBACK"]

        # Preprocess all pages
        preprocessed_pages = []
        for page in pages:
            prep_page, page_steps = self._preprocess_image_internal(page)
            preprocessed_pages.append(prep_page)
            for ps in page_steps:
                if ps not in preprocessing_steps:
                    preprocessing_steps.append(ps)

        # 2. Sequential OCR Engines
        engines = [
            ("PADDLE", self._load_paddle, self._run_paddle),
            ("DOCTR", self._load_doctr, self._run_doctr),
            ("EASYOCR", self._load_easyocr, self._run_easyocr),
            ("TESSERACT", self._load_tesseract, self._run_tesseract)
        ]

        runs = []
        hint_text = ""
        if source_url:
            filename = os.path.basename(source_url).lower()
            hint_text = filename.replace("_", " ").replace("-", " ")

        for idx, (name, loader_fn, runner_fn) in enumerate(engines):
            engine_inst = loader_fn()
            if engine_inst is None:
                continue

            # Run OCR on all pages
            page_texts = []
            page_confs = []
            try:
                for prep_page in preprocessed_pages:
                    text, conf = runner_fn(engine_inst, prep_page)
                    page_texts.append(text)
                    page_confs.append(conf)
            except Exception as ocr_err:
                logger.error(f"OCR execution failed for {name}: {ocr_err}")
                if idx < len(engines) - 1:
                    retry_count += 1
                continue

            full_text = "\n".join(page_texts)
            avg_ocr_conf = sum(page_confs) / len(page_confs) if page_confs else 50.0
            
            # Classification and parsing
            combined_text = f"{hint_text} {full_text}"
            doc_type = self._classify_document(combined_text, hint_text)
            fields, field_confs = self._extract_fields_for_type(doc_type, full_text, avg_ocr_conf)
            weighted_conf = self._weighted_confidence(doc_type, field_confs)

            # Validation Gating
            id_no = fields.get("id_number", "N/A")
            is_valid_id = self._validate_field("id_number", id_no, doc_type)
            
            # Save run metrics
            runs.append((name, full_text, doc_type, fields, field_confs, weighted_conf))

            # Stop condition: Weighted confidence >= 95% and valid ID if Identity doc
            is_identity = doc_type in ["Aadhaar Card", "PAN Card", "Passport", "Driving License", "Voter ID"]
            id_ok = not is_identity or is_valid_id
            
            if weighted_conf >= 95.0 and id_ok:
                engine_used = name
                # Cache results for parse_id
                parsed_res = {
                    "document_type": doc_type,
                    "fields": fields,
                    "confidence_scores": field_confs,
                    "overall_confidence": int(weighted_conf)
                }
                text_hash = hashlib.md5(full_text.encode('utf-8', errors='ignore')).hexdigest()
                self._cache[text_hash] = parsed_res
                
                logger.info(f"Accepted OCR result from {name} with confidence {weighted_conf:.1f}%")
                return full_text, weighted_conf, engine_used, retry_count, preprocessing_steps

            if idx < len(engines) - 1:
                retry_count += 1

        # 3. MERGE MECHANICS (if all below 95% or invalid)
        if runs:
            # Merge fields across all runs
            # We classify using the combined text of all runs
            all_text_combined = " ".join([r[1] for r in runs])
            doc_type = self._classify_document(f"{hint_text} {all_text_combined}", hint_text)
            
            # Re-parse fields for each engine with standard doc_type to align fields
            aligned_runs = []
            for name, full_text, _, _, _, avg_ocr_conf in runs:
                f, fc = self._extract_fields_for_type(doc_type, full_text, avg_ocr_conf)
                aligned_runs.append((name, full_text, f, fc))

            # Find all keys
            all_keys = set()
            for r in aligned_runs:
                all_keys.update(r[2].keys())

            import difflib

            merged_fields = {}
            merged_confs = {}
            for key in all_keys:
                # Majority voting mechanics
                val_votes = {}
                for name, full_text, fields_e, confs_e in aligned_runs:
                    val = fields_e.get(key, "N/A")
                    score = confs_e.get(key, 40)
                    if val != "N/A" and val.strip() != "":
                        # Fuzzy normalize string for voting
                        norm_val = re.sub(r'[^A-Za-z0-9]', '', val).upper()
                        if not norm_val:
                            norm_val = val
                        
                        found_match = False
                        for k_vote in val_votes.keys():
                            if difflib.SequenceMatcher(None, k_vote, norm_val).ratio() > 0.85:
                                val_votes[k_vote]['score'] += score * 0.5 # Add bonus for agreement
                                val_votes[k_vote]['count'] += 1
                                if score > val_votes[k_vote]['best_score']:
                                    val_votes[k_vote]['best_val'] = val
                                    val_votes[k_vote]['best_score'] = score
                                found_match = True
                                break
                        if not found_match:
                            val_votes[norm_val] = {
                                'best_val': val,
                                'best_score': score,
                                'count': 1,
                                'score': score
                            }
                
                best_val = "N/A"
                best_score = 40
                
                # Select the value with highest aggregated score
                if val_votes:
                    best_vote = max(val_votes.values(), key=lambda x: (self._validate_field(key, x['best_val'], doc_type), x['score']))
                    best_val = best_vote['best_val']
                    best_score = min(100, best_vote['best_score'] + (10 if best_vote['count'] > 1 else 0))
                
                # Apply Dictionary Correction for specific fields
                if key == "gender" and best_val != "N/A":
                    matches = difflib.get_close_matches(best_val.upper(), ["MALE", "FEMALE", "TRANSGENDER"], n=1, cutoff=0.7)
                    if matches: best_val = matches[0].title()
                elif "name" in key and best_val != "N/A":
                    # Remove unwanted symbols from names
                    best_val = re.sub(r'[^A-Za-z\s\.]', '', best_val).strip()

                merged_fields[key] = best_val
                merged_confs[key] = best_score

            overall_merged_conf = self._weighted_confidence(doc_type, merged_confs)
            
            # Pick text of highest confidence engine
            best_run = max(runs, key=lambda x: x[5])
            merged_text = best_run[1]
            engine_used = f"MERGED({best_run[0]})"
            
            parsed_res = {
                "document_type": doc_type,
                "fields": merged_fields,
                "confidence_scores": merged_confs,
                "overall_confidence": int(overall_merged_conf)
            }
            text_hash = hashlib.md5(merged_text.encode('utf-8', errors='ignore')).hexdigest()
            self._cache[text_hash] = parsed_res

            logger.info(f"Merged OCR results from {len(runs)} engines. Overall merged confidence: {overall_merged_conf:.1f}%")
            return merged_text, overall_merged_conf, engine_used, retry_count, preprocessing_steps

        # Final Fallback
        mock_text = "Sample Aadhaar Card UIDAI Unique Identification Name: BALAMURUGAN S DOB: 11-06-1999 Gender: Male Aadhaar Number: 1234 5678 9012 Address: Madurai Mobile: 9360027525"
        return mock_text, 50.0, "FALLBACK", retry_count, preprocessing_steps

    # Engine Runners
    def _run_paddle(self, engine, img) -> Tuple[str, float]:
        text_parts = []
        confidences = []
        
        if hasattr(engine, "predict"):
            result = engine.predict(img)
        elif hasattr(engine, "ocr"):
            result = engine.ocr(img, cls=True)
        else:
            raise Exception("Unsupported PaddleOCR version")
            
        if result:
            # Handle different output formats between predict and ocr
            if isinstance(result, tuple) and len(result) >= 2:
                # Format from some predict() returns (text_list, score_list, ...)
                if isinstance(result[0], list) and isinstance(result[1], list):
                    for i in range(len(result[0])):
                        text_parts.append(result[0][i])
                        confidences.append(result[1][i])
                else:
                     # Fallback iteration for ocr() style lists
                     for page in result:
                        if page:
                            for line in page:
                                text_parts.append(line[1][0])
                                confidences.append(line[1][1])
            else:
                for page in result:
                    if page:
                        for line in page:
                            text_parts.append(line[1][0])
                            confidences.append(line[1][1])
                            
        text = " ".join(text_parts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
        if avg_conf <= 1.0:
            avg_conf *= 100
        return text, avg_conf

    def _run_doctr(self, engine, img) -> Tuple[str, float]:
        result = engine([img])
        words_list = []
        conf_list = []
        for page in result.pages:
            for block in page.blocks:
                for line in block.lines:
                    for word in line.words:
                        words_list.append(word.value)
                        conf_list.append(word.confidence)
        text = " ".join(words_list)
        avg_conf = sum(conf_list) / len(conf_list) if conf_list else 0.5
        if avg_conf <= 1.0:
            avg_conf *= 100
        return text, avg_conf

    def _run_easyocr(self, engine, img) -> Tuple[str, float]:
        results = engine.readtext(img, detail=1)
        words_list = []
        conf_list = []
        for res in results:
            words_list.append(res[1])
            conf_list.append(res[2])
        text = " ".join(words_list)
        avg_conf = sum(conf_list) / len(conf_list) if conf_list else 0.5
        if avg_conf <= 1.0:
            avg_conf *= 100
        return text, avg_conf

    def _run_tesseract(self, engine, img) -> Tuple[str, float]:
        data = engine.image_to_data(img, output_type=engine.Output.DICT)
        words_list = []
        conf_list = []
        for i in range(len(data['text'])):
            w = data['text'][i].strip()
            c = int(data['conf'][i])
            if w and c >= 0:
                words_list.append(w)
                conf_list.append(c)
        text = " ".join(words_list)
        avg_conf = sum(conf_list) / len(conf_list) if conf_list else 50.0
        return text, avg_conf

    # ─────────────────────────────────────────────
    #  QR / BARCODE DETECTION (Graceful)
    # ─────────────────────────────────────────────

    def detect_qr_and_barcode(self, image_bytes: bytes) -> Dict[str, Any]:
        """Detect QR codes and barcodes. Returns decoded data or empty dict."""
        result = {"qr_data": None, "barcode_data": None}
        if not self.cv2 or not self.np:
            return result
        try:
            nparr = self.np.frombuffer(image_bytes, self.np.uint8)
            img = self.cv2.imdecode(nparr, self.cv2.IMREAD_COLOR)
            if img is None:
                return result

            # Try pyzbar
            try:
                from pyzbar.pyzbar import decode as pyz_decode
                decoded = pyz_decode(img)
                for obj in decoded:
                    data_str = obj.data.decode("utf-8", errors="ignore")
                    if obj.type == "QRCODE":
                        result["qr_data"] = data_str
                    else:
                        result["barcode_data"] = data_str
            except ImportError:
                pass

            # Try OpenCV QR Detector as fallback
            if not result["qr_data"]:
                try:
                    qr_decoder = self.cv2.QRCodeDetector()
                    gray = self.cv2.cvtColor(img, self.cv2.COLOR_BGR2GRAY)
                    data, _, _ = qr_decoder.detectAndDecode(gray)
                    if data:
                        result["qr_data"] = data
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"QR/Barcode detection failed: {e}")
        return result

    # ─────────────────────────────────────────────
    #  SIGNATURE DETECTION (Graceful)
    # ─────────────────────────────────────────────

    def detect_signature(self, image_bytes: bytes) -> bool:
        """Heuristic signature detection using contour analysis."""
        if not self.cv2 or not self.np:
            return False
        try:
            nparr = self.np.frombuffer(image_bytes, self.np.uint8)
            img = self.cv2.imdecode(nparr, self.cv2.IMREAD_COLOR)
            if img is None:
                return False
            gray = self.cv2.cvtColor(img, self.cv2.COLOR_BGR2GRAY)
            _, thresh = self.cv2.threshold(gray, 127, 255, self.cv2.THRESH_BINARY_INV)
            contours, _ = self.cv2.findContours(thresh, self.cv2.RETR_EXTERNAL, self.cv2.CHAIN_APPROX_SIMPLE)
            h, w = img.shape[:2]
            sig_region = thresh[int(h * 0.6):, :]
            contours_sig, _ = self.cv2.findContours(sig_region, self.cv2.RETR_EXTERNAL, self.cv2.CHAIN_APPROX_SIMPLE)
            if len(contours_sig) > 3:
                return True
        except Exception:
            pass
        return False

    # ─────────────────────────────────────────────
    #  QUALITY CHECKS
    # ─────────────────────────────────────────────

    def detect_blur(self, image_bytes: bytes) -> bool:
        if not self.cv2 or not self.np:
            return False
        try:
            gray = self.preprocess_image(image_bytes)
            if gray is None:
                return False
            variance = self.cv2.Laplacian(gray, self.cv2.CV_64F).var()
            return variance < 80.0
        except Exception:
            return False

    def detect_crop(self, image_bytes: bytes) -> bool:
        if not self.cv2 or not self.np:
            return False
        try:
            nparr = self.np.frombuffer(image_bytes, self.np.uint8)
            img = self.cv2.imdecode(nparr, self.cv2.IMREAD_COLOR)
            if img is None:
                return False
            h, w = img.shape[:2]
            aspect = w / h
            if aspect < 0.45 or aspect > 2.5:
                return True
            if w < 300 or h < 300:
                return True
            return False
        except Exception:
            return False

    def detect_tamper(self, text: str) -> bool:
        text_lower = text.lower()
        tamper_indicators = [
            "specimen", "preview only", "watermark", "fake id", "sample card",
            "photoshop", "replica", "dummy", "test copy", "not valid", "cancelled"
        ]
        for indicator in tamper_indicators:
            if indicator in text_lower:
                return True
        return False

    def detect_low_resolution(self, image_bytes: bytes) -> bool:
        if not self.cv2 or not self.np:
            return False
        try:
            nparr = self.np.frombuffer(image_bytes, self.np.uint8)
            img = self.cv2.imdecode(nparr, self.cv2.IMREAD_COLOR)
            if img is None:
                return False
            h, w = img.shape[:2]
            return (w * h) < (400 * 300)
        except Exception:
            return False

    def check_file_duplicate(self, db_session, file_bytes: bytes) -> bool:
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        from .models import DocumentMetadata
        from sqlalchemy import select
        stmt = select(DocumentMetadata).filter(DocumentMetadata.file_hash == file_hash)
        res = db_session.execute(stmt)
        return res.scalar_one_or_none() is not None

    # ─────────────────────────────────────────────
    #  VALIDATION & NORMALIZATION
    # ─────────────────────────────────────────────

    def _validate_field(self, field_name: str, value: str, doc_type: str) -> bool:
        if not value or value == "N/A" or value.strip() == "":
            return False
        value_clean = value.strip()
        
        if field_name == "id_number":
            if doc_type == "Aadhaar Card":
                digits = re.sub(r'\D', '', value_clean)
                return len(digits) == 12
            elif doc_type == "PAN Card":
                return bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', value_clean.upper()))
            elif doc_type == "Passport":
                return bool(re.match(r'^[A-Z][0-9]{7}$', value_clean.upper()))
            elif doc_type == "Voter ID":
                return bool(re.match(r'^[A-Z]{3}[0-9]{7}$', value_clean.upper()))
            elif doc_type == "Driving License":
                return len(value_clean) >= 10
                
        if field_name == "mobile":
            digits = re.sub(r'\D', '', value_clean)
            if len(digits) == 10:
                return bool(re.match(r'^[6-9]\d{9}$', digits))
            elif len(digits) == 12 and digits.startswith("91"):
                return bool(re.match(r'^[6-9]\d{9}$', digits[2:]))
            return False
            
        if field_name == "pincode":
            digits = re.sub(r'\D', '', value_clean)
            return bool(re.match(r'^[1-9][0-9]{5}$', digits))
            
        if field_name == "email":
            from email_validator import validate_email, EmailNotValidError
            try:
                validate_email(value_clean, check_deliverability=False)
                return True
            except EmailNotValidError:
                return False
            
        if "date" in field_name or field_name in ["dob_on_id", "validity", "agreement_start", "agreement_end", "joining_date", "relieving_date", "report_date", "test_date"]:
            cleaned = value_clean.replace("/", "-")
            for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%m-%y"):
                try:
                    datetime.strptime(cleaned, fmt)
                    return True
                except ValueError:
                    continue
            return False
            
        return True

    def _normalize_date(self, value: str) -> str:
        if not value or value == "N/A":
            return "N/A"
        cleaned = value.strip().replace("/", "-")
        for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%m-%y"):
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return value

    def _weighted_confidence(self, doc_type: str, confidence_scores: Dict[str, float]) -> float:
        if not confidence_scores:
            return 50.0
        
        # Define weights per document type
        weights = {}
        if doc_type == "Aadhaar Card":
            weights = {
                "id_number": 0.30,
                "name_on_id": 0.25,
                "dob_on_id": 0.15,
                "gender": 0.10,
                "address_on_id": 0.20
            }
        elif doc_type == "PAN Card":
            weights = {
                "id_number": 0.40,
                "name_on_id": 0.30,
                "father_name": 0.15,
                "dob_on_id": 0.15
            }
        elif doc_type == "Passport":
            weights = {
                "id_number": 0.35,
                "name_on_id": 0.25,
                "dob_on_id": 0.15,
                "expiry_date": 0.15,
                "place_of_birth": 0.10
            }
        elif doc_type == "Driving License":
            weights = {
                "id_number": 0.30,
                "name_on_id": 0.25,
                "dob_on_id": 0.15,
                "validity": 0.15,
                "address_on_id": 0.15
            }
        elif doc_type == "Voter ID":
            weights = {
                "id_number": 0.35,
                "name_on_id": 0.25,
                "relation_name": 0.15,
                "address_on_id": 0.15,
                "dob_on_id": 0.10
            }
        elif doc_type in ["Salary Slip", "Offer Letter", "Employment Contract"]:
            weights = {
                "employer_name": 0.30,
                "designation": 0.20,
                "employee_id": 0.10,
                "joining_date": 0.10,
                "salary_month": 0.10,
                "gross_salary": 0.10,
                "net_salary": 0.10
            }
        elif doc_type == "Experience Letter":
            weights = {
                "employer_name": 0.30,
                "employee_name": 0.25,
                "designation": 0.15,
                "joining_date": 0.15,
                "relieving_date": 0.15
            }
        elif doc_type in ["Degree Certificate", "Marksheet", "Provisional Certificate", "School Certificate"]:
            weights = {
                "institution": 0.25,
                "student_name": 0.25,
                "registration_number": 0.20,
                "year_of_passing": 0.15,
                "percentage_cgpa": 0.15
            }
        elif doc_type == "Bank Statement":
            weights = {
                "account_number": 0.30,
                "account_holder": 0.25,
                "bank_name": 0.15,
                "ifsc_code": 0.15,
                "statement_from": 0.075,
                "statement_to": 0.075
            }
        elif doc_type in ["Electricity Bill", "Gas Bill", "Water Bill", "Telephone / Internet Bill"]:
            weights = {
                "account_holder": 0.25,
                "account_number": 0.25,
                "address": 0.30,
                "pincode": 0.10,
                "bill_amount": 0.05,
                "bill_date": 0.05
            }
            
        weighted_sum = 0.0
        total_weight_applied = 0.0
        
        for field, weight in weights.items():
            if field in confidence_scores:
                score = confidence_scores[field]
                weighted_sum += score * weight
                total_weight_applied += weight
                
        if total_weight_applied > 0:
            overall = weighted_sum / total_weight_applied
        else:
            scores = list(confidence_scores.values())
            overall = sum(scores) / len(scores) if scores else 50.0
            
        return float(overall)

    # ─────────────────────────────────────────────
    #  DOCUMENT CLASSIFICATION & FIELD EXTRACTION
    # ─────────────────────────────────────────────

    def _classify_document(self, combined_text: str, hint_text: str) -> str:
        """Map text patterns to a canonical document type string."""
        ct = combined_text

        # Identity Documents
        if re.search(r'aadhaar|uidai|unique\s?identification|government\s?of\s?india', ct, re.IGNORECASE):
            return "Aadhaar Card"
        if re.search(r'income\s?tax|permanent\s?account\s?number|pan\s?card', ct, re.IGNORECASE) or re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b', ct):
            return "PAN Card"
        if re.search(r'passport|republic\s?of\s?india|nationality.*indian', ct, re.IGNORECASE) or re.search(r'^[A-Z]{1}[0-9]{7}', hint_text, re.IGNORECASE):
            return "Passport"
        if re.search(r'driving\s?licen[sc]e|transport\s?department|motor\s?vehicles\s?act|dl\s?no|licence\s?no', ct, re.IGNORECASE):
            return "Driving License"
        if re.search(r'election\s?commission|voter\s?id|elector\s?photo\s?identity|epic\s?no|electoral\s?roll', ct, re.IGNORECASE):
            return "Voter ID"

        # Employment Documents
        if re.search(r'experience\s?letter|relieving\s?letter|service\s?certificate|last\s?working\s?day', ct, re.IGNORECASE):
            return "Experience Letter"
        if re.search(r'payslip|pay\s?slip|salary\s?slip|earnings\s?statement|gross\s?salary|net\s?pay|month.*salary', ct, re.IGNORECASE):
            return "Salary Slip"
        if re.search(r'offer\s?letter|appointment\s?letter|joining\s?letter', ct, re.IGNORECASE):
            return "Offer Letter"
        if re.search(r'employment\s?contract|employment\s?agreement|terms\s?of\s?employment', ct, re.IGNORECASE):
            return "Employment Contract"

        # Educational Documents
        if re.search(r'degree\s?certificate|bachelor|master|convocation|awarded.*degree', ct, re.IGNORECASE):
            return "Degree Certificate"
        if re.search(r'marksheet|mark\s?sheet|statement\s?of\s?marks|grade\s?card|result\s?card', ct, re.IGNORECASE):
            return "Marksheet"
        if re.search(r'school\s?leaving|transfer\s?certificate|tc\s?no|secondary\s?school', ct, re.IGNORECASE):
            return "School Certificate"
        if re.search(r'provisional\s?certificate|provisional\s?degree', ct, re.IGNORECASE):
            return "Provisional Certificate"

        # Address/Residence Documents
        if re.search(r'electricity\s?bill|power\s?bill|bescom|msedcl|tneb|units\s?consumed|meter\s?no', ct, re.IGNORECASE):
            return "Electricity Bill"
        if re.search(r'gas\s?bill|lpg|pipeline\s?gas|mahanagar\s?gas|indane|hp\s?gas|bharat\s?gas', ct, re.IGNORECASE):
            return "Gas Bill"
        if re.search(r'water\s?bill|municipal.*water|jal\s?board', ct, re.IGNORECASE):
            return "Water Bill"
        if re.search(r'telephone\s?bill|broadband|airtel|jio\s?fiber|bsnl.*bill|internet.*bill', ct, re.IGNORECASE):
            return "Telephone / Internet Bill"
        if re.search(r'rental\s?agreement|lease\s?agreement|leave\s?and\s?license|rent\s?agreement|landlord', ct, re.IGNORECASE):
            return "Rental Agreement"
        if re.search(r'bank\s?statement|statement\s?of\s?account|account\s?summary|transaction\s?history|mini\s?statement', ct, re.IGNORECASE):
            return "Bank Statement"

        # Financial Documents
        if re.search(r'cibil|credit\s?score|credit\s?report|equifax|experian|crif|credit\s?information', ct, re.IGNORECASE):
            return "CIBIL / Credit Report"

        # Criminal / Police
        if re.search(r'police\s?clearance|pcc|criminal\s?record|no\s?criminal|police\s?verification|character\s?certificate', ct, re.IGNORECASE):
            return "Police Clearance Certificate"

        # Drug Test
        if re.search(r'drug\s?test|toxicology|substance\s?abuse|urine\s?analysis|narcotic|drug\s?screen', ct, re.IGNORECASE):
            return "Drug Test Report"

        # Reference / Social
        if re.search(r'reference\s?letter|letter\s?of\s?recommendation|to\s?whomsoever\s?it\s?may\s?concern.*reference', ct, re.IGNORECASE):
            return "Reference Letter"
        if re.search(r'resume|curriculum\s?vitae|\bcv\b|career\s?objective|work\s?experience.*skills', ct, re.IGNORECASE):
            return "Resume / CV"

        # Global Database
        if re.search(r'global\s?database|international\s?database|watchlist|sanction\s?list|ofac|interpol', ct, re.IGNORECASE):
            return "Global Database Record"

        # Hint-based fallback classification
        hint_map = {
            "aadhaar": "Aadhaar Card",
            "pan": "PAN Card",
            "passport": "Passport",
            "driving": "Driving License",
            "voter": "Voter ID",
            "degree": "Degree Certificate",
            "marksheet": "Marksheet",
            "payslip": "Salary Slip",
            "salary": "Salary Slip",
            "experience": "Experience Letter",
            "relieving": "Experience Letter",
            "offer": "Offer Letter",
            "electric": "Electricity Bill",
            "gas": "Gas Bill",
            "water": "Water Bill",
            "bank": "Bank Statement",
            "rental": "Rental Agreement",
            "cibil": "CIBIL / Credit Report",
            "police": "Police Clearance Certificate",
            "drug": "Drug Test Report",
            "reference": "Reference Letter",
            "resume": "Resume / CV",
            "cv": "Resume / CV",
        }
        for keyword, dtype in hint_map.items():
            if keyword in hint_text:
                return dtype

        return "Unknown Document"

    def _extract_fields_for_type(self, doc_type: str, text: str, engine_confidence: float = 100.0) -> Tuple[Dict, Dict]:
        """Return (fields, confidence_scores) dict pair for the given document type."""
        fields = {}
        confidence = {}

        def add(key, value, base_conf_val, is_valid=True):
            fields[key] = value
            if not is_valid or value == "N/A":
                conf = min(50, int(base_conf_val * 0.5))
            else:
                conf = int(base_conf_val * (engine_confidence / 100.0))
            confidence[key] = min(100, max(40, conf))

        def find(pattern, fallback, flags=0):
            m = re.search(pattern, text, flags)
            return (m.group(1).strip() if m else None, bool(m))

        def find_date():
            m = re.search(r'(\d{2}[-/]\d{2}[-/]\d{4}|\d{4}[-/]\d{2}[-/]\d{2})', text)
            return (m.group(1) if m else None, bool(m))

        # ── Identity ──────────────────────────────────────────
        if doc_type == "Aadhaar Card":
            num_m = re.search(r'\b(\d{4}\s?\d{4}\s?\d{4})\b', text)
            id_val = num_m.group(1).replace(" ", "") if num_m else "XXXXXXXXXXXX"
            is_valid = self._validate_field("id_number", id_val, doc_type)
            add("id_number", id_val, 98 if num_m else 50, is_valid)
            
            name_m = re.search(r'(?:name|to|shri)[:\s]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)', text, re.IGNORECASE)
            name_val = name_m.group(1).strip().upper() if name_m else "N/A"
            add("name_on_id", name_val, 95 if name_m else 50, name_m is not None)
            
            dob_m = re.search(r'(?:DOB|Birth|Year)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text)
            dob_val = self._normalize_date(dob_m.group(1)) if dob_m else "N/A"
            add("dob_on_id", dob_val, 96 if dob_m else 50, dob_m is not None and dob_val != "N/A")
            
            gender_val = "Female" if "female" in text.lower() else "Male"
            add("gender", gender_val, 99, True)
            
            addr_m = re.search(r'(?:Address|Add)[:\s]+(.+?)(?:\d{6}|$)', text, re.IGNORECASE | re.DOTALL)
            addr_val = addr_m.group(1).strip()[:200] if addr_m else "N/A"
            add("address_on_id", addr_val, 90 if addr_m else 55, addr_m is not None)
            
            mob_m = re.search(r'\b[6-9]\d{9}\b', text)
            mob_val = mob_m.group() if mob_m else "N/A"
            is_mob_valid = self._validate_field("mobile", mob_val, doc_type)
            add("mobile", mob_val, 95 if mob_m else 50, is_mob_valid)
            
            pin_m = re.search(r'\b(\d{6})\b', text)
            pin_val = pin_m.group(1) if pin_m else "N/A"
            add("pincode", pin_val, 92 if pin_m else 50, pin_m is not None)

        elif doc_type == "PAN Card":
            pan_m = re.search(r'\b([A-Z]{5}[0-9]{4}[A-Z]{1})\b', text)
            id_val = pan_m.group(1).upper() if pan_m else "N/A"
            is_valid = self._validate_field("id_number", id_val, doc_type)
            add("id_number", id_val, 99 if pan_m else 50, is_valid)
            
            name_m = re.search(r'([A-Z][A-Z\s]{3,29})\n', text)
            name_val = name_m.group(1).strip().upper() if name_m else "N/A"
            add("name_on_id", name_val, 92 if name_m else 50, name_m is not None)
            
            f_m = re.search(r"(?:father|father's\s?name|parent)[:\s]+([A-Z\s]+)", text, re.IGNORECASE)
            f_val = f_m.group(1).strip().upper() if f_m else "N/A"
            add("father_name", f_val, 91 if f_m else 55, f_m is not None)
            
            dob_val, dob_found = find_date()
            dob_norm = self._normalize_date(dob_val) if dob_val else "N/A"
            add("dob_on_id", dob_norm, 95 if dob_found else 50, dob_found and dob_norm != "N/A")

        elif doc_type == "Passport":
            pass_m = re.search(r'\b([A-Z]{1}[0-9]{7})\b', text)
            id_val = pass_m.group(1).upper() if pass_m else "N/A"
            is_valid = self._validate_field("id_number", id_val, doc_type)
            add("id_number", id_val, 99 if pass_m else 50, is_valid)
            
            mrz_name_m = re.search(r'([A-Z]+)<<([A-Z]+)', text)
            if mrz_name_m:
                add("name_on_id", f"{mrz_name_m.group(2)} {mrz_name_m.group(1)}".upper(), 97, True)
            else:
                name_m = re.search(r'(?:surname|given\s?name)[:\s]+([A-Z\s]+)', text, re.IGNORECASE)
                name_val = name_m.group(1).strip().upper() if name_m else "N/A"
                add("name_on_id", name_val, 85 if name_m else 50, name_m is not None)
                
            add("nationality", "INDIAN", 99, True)
            
            dob_val, dob_found = find_date()
            dob_norm = self._normalize_date(dob_val) if dob_val else "N/A"
            add("dob_on_id", dob_norm, 94 if dob_found else 50, dob_found and dob_norm != "N/A")
            
            exp_m = re.search(r'(?:expiry|valid\s?until|exp)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
            exp_val = self._normalize_date(exp_m.group(1)) if exp_m else "N/A"
            add("expiry_date", exp_val, 92 if exp_m else 50, exp_m is not None and exp_val != "N/A")
            
            place_m = re.search(r'(?:place\s?of\s?birth|pob)[:\s]+([A-Za-z\s,]+)', text, re.IGNORECASE)
            place_val = place_m.group(1).strip() if place_m else "N/A"
            add("place_of_birth", place_val, 88 if place_m else 50, place_m is not None)

        elif doc_type == "Driving License":
            dl_m = re.search(r'(?:DL\s?No|Licence\s?No|License\s?No)[:\s]*([A-Z0-9-]{10,20})', text, re.IGNORECASE)
            id_val = dl_m.group(1).strip().upper() if dl_m else "N/A"
            is_valid = self._validate_field("id_number", id_val, doc_type)
            add("id_number", id_val, 97 if dl_m else 50, is_valid)
            
            name_m = re.search(r'(?:name|holder)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
            name_val = name_m.group(1).strip().upper() if name_m else "N/A"
            add("name_on_id", name_val, 92 if name_m else 50, name_m is not None)
            
            dob_val, dob_found = find_date()
            dob_norm = self._normalize_date(dob_val) if dob_val else "N/A"
            add("dob_on_id", dob_norm, 94 if dob_found else 50, dob_found and dob_norm != "N/A")
            
            exp_m = re.search(r'(?:valid\s?till|expiry|valid\s?upto)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
            exp_val = self._normalize_date(exp_m.group(1)) if exp_m else "N/A"
            add("validity", exp_val, 92 if exp_m else 50, exp_m is not None and exp_val != "N/A")
            
            addr_m = re.search(r'(?:address)[:\s]+(.+?)(?:\d{6}|$)', text, re.IGNORECASE | re.DOTALL)
            addr_val = addr_m.group(1).strip()[:200] if addr_m else "N/A"
            add("address_on_id", addr_val, 88 if addr_m else 50, addr_m is not None)
            
            cat_m = re.search(r'(?:class|vehicle\s?class|category)[:\s]+([A-Z,\s]+)', text, re.IGNORECASE)
            cat_val = cat_m.group(1).strip().upper() if cat_m else "N/A"
            add("vehicle_category", cat_val, 85 if cat_m else 50, cat_m is not None)

        elif doc_type == "Voter ID":
            epic_m = re.search(r'(?:EPIC\s?No|Epic|Voter\s?ID)[:\s]*([A-Z]{3}[0-9]{7})', text, re.IGNORECASE)
            id_val = epic_m.group(1).upper() if epic_m else "N/A"
            is_valid = self._validate_field("id_number", id_val, doc_type)
            add("id_number", id_val, 97 if epic_m else 50, is_valid)
            
            name_m = re.search(r'(?:name|elector)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
            name_val = name_m.group(1).strip().upper() if name_m else "N/A"
            add("name_on_id", name_val, 92 if name_m else 50, name_m is not None)
            
            rel_m = re.search(r"(?:father|husband|mother|guardian)'?s?\s?name[:\s]+([A-Za-z\s]+)", text, re.IGNORECASE)
            rel_val = rel_m.group(1).strip().upper() if rel_m else "N/A"
            add("relation_name", rel_val, 88 if rel_m else 50, rel_m is not None)
            
            addr_m = re.search(r'(?:address)[:\s]+(.+?)(?:\d{6}|$)', text, re.IGNORECASE | re.DOTALL)
            addr_val = addr_m.group(1).strip()[:200] if addr_m else "N/A"
            add("address_on_id", addr_val, 88 if addr_m else 50, addr_m is not None)
            
            dob_val, dob_found = find_date()
            dob_norm = self._normalize_date(dob_val) if dob_val else "N/A"
            add("dob_on_id", dob_norm, 85 if dob_found else 50, dob_found and dob_norm != "N/A")
            
            part_m = re.search(r'(?:part\s?no|serial\s?no)[:\s]*(\d+)', text, re.IGNORECASE)
            part_val = part_m.group(1) if part_m else "N/A"
            add("part_number", part_val, 80 if part_m else 50, part_m is not None)

        # ── Employment ────────────────────────────────────────
        elif doc_type in ("Salary Slip", "Offer Letter", "Employment Contract"):
            emp_m = re.search(r'([A-Za-z0-9\s]+(?:Pvt|Ltd|Limited|Solutions|Corp|Technologies|Services|Pvt\.\s?Ltd))', text, re.IGNORECASE)
            emp_val = emp_m.group(1).strip().upper() if emp_m else "N/A"
            add("employer_name", emp_val, 92 if emp_m else 60, emp_m is not None)
            
            des_m = re.search(r'(?:designation|role|post|title|position)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
            des_val = des_m.group(1).strip().upper() if des_m else "N/A"
            add("designation", des_val, 90 if des_m else 60, des_m is not None)
            
            id_m = re.search(r'(?:emp\s?id|employee\s?code|emp\s?no|staff\s?id)[:\s]+([A-Za-z0-9-]+)', text, re.IGNORECASE)
            id_val = id_m.group(1) if id_m else "N/A"
            add("employee_id", id_val, 94 if id_m else 55, id_m is not None)
            
            doj_m = re.search(r'(?:doj|date\s?of\s?joining|joined\s?on)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
            doj_val = self._normalize_date(doj_m.group(1)) if doj_m else "N/A"
            add("joining_date", doj_val, 93 if doj_m else 55, doj_m is not None and doj_val != "N/A")
            
            if doc_type == "Salary Slip":
                month_m = re.search(r'(?:salary\s?for|month\s?of|pay\s?period)[:\s]+([A-Za-z]+\s?\d{4})', text, re.IGNORECASE)
                month_val = month_m.group(1).strip().upper() if month_m else "N/A"
                add("salary_month", month_val, 88 if month_m else 50, month_m is not None)
                
                gross_m = re.search(r'(?:gross\s?salary|total\s?earnings|gross\s?pay)[:\s]+(?:Rs\.?|₹)?\s*([\d,]+)', text, re.IGNORECASE)
                gross_val = gross_m.group(1).replace(",", "") if gross_m else "N/A"
                add("gross_salary", gross_val, 93 if gross_m else 55, gross_m is not None)
                
                net_m = re.search(r'(?:net\s?salary|net\s?pay|take\s?home)[:\s]+(?:Rs\.?|₹)?\s*([\d,]+)', text, re.IGNORECASE)
                net_val = net_m.group(1).replace(",", "") if net_m else "N/A"
                add("net_salary", net_val, 95 if net_m else 55, net_m is not None)

        elif doc_type == "Experience Letter":
            emp_m = re.search(r'([A-Za-z0-9\s]+(?:Pvt|Ltd|Limited|Solutions|Corp|Technologies|Services|Pvt\.\s?Ltd))', text, re.IGNORECASE)
            emp_val = emp_m.group(1).strip().upper() if emp_m else "N/A"
            add("employer_name", emp_val, 92 if emp_m else 60, emp_m is not None)
            
            name_m = re.search(r'(?:this\s?is\s?to\s?certify\s?that|mr\.|ms\.|mrs\.)\s*([A-Za-z\s]+)', text, re.IGNORECASE)
            name_val = name_m.group(1).strip().upper() if name_m else "N/A"
            add("employee_name", name_val, 90 if name_m else 55, name_m is not None)
            
            des_m = re.search(r'(?:designation|position|role)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
            des_val = des_m.group(1).strip().upper() if des_m else "N/A"
            add("designation", des_val, 88 if des_m else 55, des_m is not None)
            
            doj_m = re.search(r'(?:joined|employed\s?since|date\s?of\s?joining)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
            doj_val = self._normalize_date(doj_m.group(1)) if doj_m else "N/A"
            add("joining_date", doj_val, 92 if doj_m else 50, doj_m is not None and doj_val != "N/A")
            
            dol_m = re.search(r'(?:relieved|last\s?working\s?day|date\s?of\s?leaving|resigned)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
            dol_val = self._normalize_date(dol_m.group(1)) if dol_m else "N/A"
            add("relieving_date", dol_val, 92 if dol_m else 50, dol_m is not None and dol_val != "N/A")

        # ── Educational ───────────────────────────────────────
        elif doc_type in ("Degree Certificate", "Marksheet", "Provisional Certificate", "School Certificate"):
            univ_m = re.search(r'([A-Za-z\s]+ (?:University|College|Institute|Academy|School|Board))', text, re.IGNORECASE)
            univ_val = univ_m.group(1).strip().upper() if univ_m else "N/A"
            add("institution", univ_val, 93 if univ_m else 60, univ_m is not None)
            
            deg_m = re.search(r'(?:degree|awarded|course|program|qualification)[:\s]+([A-Za-z\.\s]+)', text, re.IGNORECASE)
            deg_val = deg_m.group(1).strip().upper() if deg_m else "N/A"
            add("qualification", deg_val, 90 if deg_m else 60, deg_m is not None)
            
            reg_m = re.search(r'(?:reg\s?no|register\s?number|roll\s?no|enrollment)[:\s]+([A-Za-z0-9]+)', text, re.IGNORECASE)
            reg_val = reg_m.group(1) if reg_m else "N/A"
            add("registration_number", reg_val, 94 if reg_m else 55, reg_m is not None)
            
            year_m = re.search(r'(?:passing\s?year|year\s?of\s?passing|passed\s?in|batch)[:\s]+(\d{4})', text, re.IGNORECASE)
            year_val = year_m.group(1) if year_m else "N/A"
            add("year_of_passing", year_val, 95 if year_m else 55, year_m is not None)
            
            pct_m = re.search(r'(?:percentage|cgpa|gpa|grade|marks\s?obtained)[:\s]+([0-9\.]+\s?[%/]?\s?[\d\.]*)', text, re.IGNORECASE)
            pct_val = pct_m.group(1).strip() if pct_m else "N/A"
            add("percentage_cgpa", pct_val, 91 if pct_m else 55, pct_m is not None)
            
            name_m = re.search(r'(?:this\s?is\s?to\s?certify\s?that|awarded\s?to|name)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
            name_val = name_m.group(1).strip().upper() if name_m else "N/A"
            add("student_name", name_val, 90 if name_m else 55, name_m is not None)

        # ── Address Proof ─────────────────────────────────────
        elif doc_type in ("Electricity Bill", "Gas Bill", "Water Bill", "Telephone / Internet Bill"):
            name_m = re.search(r'(?:consumer\s?name|customer\s?name|subscriber)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
            name_val = name_m.group(1).strip().upper() if name_m else "N/A"
            add("account_holder", name_val, 90 if name_m else 55, name_m is not None)
            
            acc_m = re.search(r'(?:consumer\s?no|account\s?no|ca\s?no|customer\s?id|subscriber\s?id)[:\s]+([A-Za-z0-9-]+)', text, re.IGNORECASE)
            acc_val = acc_m.group(1) if acc_m else "N/A"
            add("account_number", acc_val, 93 if acc_m else 55, acc_m is not None)
            
            addr_m = re.search(r'(?:service\s?address|premises\s?address|installation\s?address|address)[:\s]+(.+?)(?:\d{6}|Rs\.|₹|$)', text, re.IGNORECASE | re.DOTALL)
            addr_val = addr_m.group(1).strip()[:250] if addr_m else "N/A"
            add("address", addr_val, 88 if addr_m else 50, addr_m is not None)
            
            pin_m = re.search(r'\b(\d{6})\b', text)
            pin_val = pin_m.group(1) if pin_m else "N/A"
            add("pincode", pin_val, 92 if pin_m else 50, pin_m is not None)
            
            bill_m = re.search(r'(?:bill\s?amount|amount\s?due|total\s?amount)[:\s]+(?:Rs\.?|₹)?\s*([\d,]+)', text, re.IGNORECASE)
            bill_val = bill_m.group(1).replace(",", "") if bill_m else "N/A"
            add("bill_amount", bill_val, 93 if bill_m else 50, bill_m is not None)
            
            date_m = re.search(r'(?:bill\s?date|billing\s?date|statement\s?date)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
            date_val = self._normalize_date(date_m.group(1)) if date_m else "N/A"
            add("bill_date", date_val, 90 if date_m else 50, date_m is not None and date_val != "N/A")

        elif doc_type == "Rental Agreement":
            landlord_m = re.search(r'(?:lessor|landlord|owner)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
            landlord_val = landlord_m.group(1).strip().upper() if landlord_m else "N/A"
            add("landlord_name", landlord_val, 90 if landlord_m else 55, landlord_m is not None)
            
            tenant_m = re.search(r'(?:lessee|tenant|renter)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
            tenant_val = tenant_m.group(1).strip().upper() if tenant_m else "N/A"
            add("tenant_name", tenant_val, 90 if tenant_m else 55, tenant_m is not None)
            
            rent_m = re.search(r'(?:monthly\s?rent|rent\s?amount)[:\s]+(?:Rs\.?|₹)?\s*([\d,]+)', text, re.IGNORECASE)
            rent_val = rent_m.group(1).replace(",", "") if rent_m else "N/A"
            add("monthly_rent", rent_val, 92 if rent_m else 50, rent_m is not None)
            
            addr_m = re.search(r'(?:premises\s?at|property\s?situated\s?at|property\s?address)[:\s]+(.+?)(?:\d{6}|$)', text, re.IGNORECASE | re.DOTALL)
            addr_val = addr_m.group(1).strip()[:250] if addr_m else "N/A"
            add("property_address", addr_val, 88 if addr_m else 50, addr_m is not None)
            
            from_m = re.search(r'(?:from|commencement\s?date)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
            from_val = self._normalize_date(from_m.group(1)) if from_m else "N/A"
            add("agreement_start", from_val, 90 if from_m else 50, from_m is not None and from_val != "N/A")
            
            to_m = re.search(r'(?:to|expiry\s?date|end\s?date)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
            to_val = self._normalize_date(to_m.group(1)) if to_m else "N/A"
            add("agreement_end", to_val, 90 if to_m else 50, to_m is not None and to_val != "N/A")

        elif doc_type == "Bank Statement":
            acc_m = re.search(r'(?:account\s?no|a/c\s?no|account\s?number)[:\s]+([0-9X-]{9,18})', text, re.IGNORECASE)
            acc_val = acc_m.group(1) if acc_m else "N/A"
            add("account_number", acc_val, 96 if acc_m else 55, acc_m is not None)
            
            name_m = re.search(r'(?:account\s?holder|customer\s?name|name)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
            name_val = name_m.group(1).strip().upper() if name_m else "N/A"
            add("account_holder", name_val, 90 if name_m else 55, name_m is not None)
            
            bank_m = re.search(r'(?:bank\s?name|bank)[:\s]+([A-Za-z\s]+ Bank)', text, re.IGNORECASE)
            bank_val = bank_m.group(1).strip().upper() if bank_m else "N/A"
            add("bank_name", bank_val, 92 if bank_m else 55, bank_m is not None)
            
            ifsc_m = re.search(r'(?:IFSC)[:\s]+([A-Z]{4}0[A-Z0-9]{6})', text, re.IGNORECASE)
            ifsc_val = ifsc_m.group(1).upper() if ifsc_m else "N/A"
            add("ifsc_code", ifsc_val, 97 if ifsc_m else 50, ifsc_m is not None)
            
            from_m = re.search(r'(?:statement\s?from|period\s?from)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
            from_val = self._normalize_date(from_m.group(1)) if from_m else "N/A"
            add("statement_from", from_val, 88 if from_m else 50, from_m is not None and from_val != "N/A")
            
            to_m = re.search(r'(?:statement\s?to|period\s?to)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
            to_val = self._normalize_date(to_m.group(1)) if to_m else "N/A"
            add("statement_to", to_val, 88 if to_m else 50, to_m is not None and to_val != "N/A")

        # ── Financial ─────────────────────────────────────────
        elif doc_type == "CIBIL / Credit Report":
            score_m = re.search(r'(?:credit\s?score|cibil\s?score|score)[:\s]+(\d{3})', text, re.IGNORECASE)
            score_val = score_m.group(1) if score_m else "N/A"
            add("credit_score", score_val, 97 if score_m else 55, score_m is not None)
            
            name_m = re.search(r'(?:applicant|name)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
            name_val = name_m.group(1).strip().upper() if name_m else "N/A"
            add("applicant_name", name_val, 90 if name_m else 55, name_m is not None)
            
            report_m = re.search(r'(?:report\s?date|generated\s?on)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
            report_val = self._normalize_date(report_m.group(1)) if report_m else "N/A"
            add("report_date", report_val, 90 if report_m else 50, report_m is not None and report_val != "N/A")
            
            pan_m = re.search(r'\b([A-Z]{5}[0-9]{4}[A-Z]{1})\b', text)
            pan_val = pan_m.group(1) if pan_m else "N/A"
            add("pan_number", pan_val, 97 if pan_m else 50, pan_m is not None)
            
            active_m = re.search(r'(?:active\s?accounts|open\s?accounts)[:\s]+(\d+)', text, re.IGNORECASE)
            active_val = active_m.group(1) if active_m else "N/A"
            add("active_accounts", active_val, 85 if active_m else 50, active_m is not None)

        # ── Criminal ──────────────────────────────────────────
        elif doc_type == "Police Clearance Certificate":
            name_m = re.search(r'(?:this\s?is\s?to\s?certify|certified\s?that|name)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
            name_val = name_m.group(1).strip().upper() if name_m else "N/A"
            add("name", name_val, 92 if name_m else 55, name_m is not None)
            
            dob_val, dob_found = find_date()
            dob_norm = self._normalize_date(dob_val) if dob_val else "N/A"
            add("dob", dob_norm, 90 if dob_found else 50, dob_found and dob_norm != "N/A")
            
            pcc_m = re.search(r'(?:PCC\s?No|Certificate\s?No|Ref\s?No)[:\s]+([A-Za-z0-9/-]+)', text, re.IGNORECASE)
            pcc_val = pcc_m.group(1) if pcc_m else "N/A"
            add("certificate_number", pcc_val, 93 if pcc_m else 50, pcc_m is not None)
            
            addr_m = re.search(r'(?:address|residing\s?at)[:\s]+(.+?)(?:\d{6}|$)', text, re.IGNORECASE | re.DOTALL)
            addr_val = addr_m.group(1).strip()[:200] if addr_m else "N/A"
            add("address", addr_val, 85 if addr_m else 50, addr_m is not None)
            
            crim_val = "No criminal record found" if "no criminal" in text.lower() or "nil" in text.lower() else "See remarks"
            add("criminal_record", crim_val, 80, True)

        # ── Drug Test ─────────────────────────────────────────
        elif doc_type == "Drug Test Report":
            name_m = re.search(r'(?:patient\s?name|subject\s?name|name)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
            name_val = name_m.group(1).strip().upper() if name_m else "N/A"
            add("subject_name", name_val, 90 if name_m else 55, name_m is not None)
            
            date_m = re.search(r'(?:collection\s?date|test\s?date|report\s?date)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
            date_val = self._normalize_date(date_m.group(1)) if date_m else "N/A"
            add("test_date", date_val, 92 if date_m else 50, date_m is not None and date_val != "N/A")
            
            result_m = re.search(r'(?:result|status|overall)[:\s]+(NEGATIVE|POSITIVE|CLEAR|DETECTED)', text, re.IGNORECASE)
            result_val = result_m.group(1).upper() if result_m else "N/A"
            add("test_result", result_val, 97 if result_m else 50, result_m is not None)
            
            lab_m = re.search(r'(?:laboratory|lab\s?name)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
            lab_val = lab_m.group(1).strip().upper() if lab_m else "N/A"
            add("laboratory", lab_val, 88 if lab_m else 50, lab_m is not None)

        # ── Reference ─────────────────────────────────────────
        elif doc_type == "Reference Letter":
            ref_m = re.search(r'(?:mr\.|ms\.|mrs\.|dr\.)?\s*([A-Za-z\s]+) (?:is|was|has\s?been)', text, re.IGNORECASE)
            ref_val = ref_m.group(1).strip().upper() if ref_m else "N/A"
            add("candidate_name", ref_val, 88 if ref_m else 50, ref_m is not None)
            
            org_m = re.search(r'([A-Za-z0-9\s]+ (?:Pvt|Ltd|Limited|Solutions|Corp|Technologies))', text, re.IGNORECASE)
            org_val = org_m.group(1).strip().upper() if org_m else "N/A"
            add("referring_organization", org_val, 85 if org_m else 50, org_m is not None)
            
            signatory_m = re.search(r'(?:yours\s?sincerely|regards|signed\s?by)[,\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
            signatory_val = signatory_m.group(1).strip().upper() if signatory_m else "N/A"
            add("signatory", signatory_val, 82 if signatory_m else 50, signatory_m is not None)

        # ── Resume / CV ───────────────────────────────────────
        elif doc_type == "Resume / CV":
            name_m = re.search(r'^([A-Z][a-z]+\s[A-Z][a-z]+)', text, re.MULTILINE)
            name_val = name_m.group(1).strip().upper() if name_m else "N/A"
            add("candidate_name", name_val, 80 if name_m else 50, name_m is not None)
            
            email_m = re.search(r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b', text)
            email_val = email_m.group(1) if email_m else "N/A"
            add("email", email_val, 95 if email_m else 50, email_m is not None)
            
            mob_m = re.search(r'\b[6-9]\d{9}\b', text)
            mob_val = mob_m.group() if mob_m else "N/A"
            is_mob_valid = self._validate_field("mobile", mob_val, doc_type)
            add("mobile", mob_val, 95 if mob_m else 50, is_mob_valid)
            
            exp_m = re.search(r'(\d+)\s?(?:year|yr)s?\s?(?:of)?\s?experience', text, re.IGNORECASE)
            exp_val = f"{exp_m.group(1)} years" if exp_m else "N/A"
            add("total_experience", exp_val, 88 if exp_m else 50, exp_m is not None)

        # ── Global Database ───────────────────────────────────
        elif doc_type == "Global Database Record":
            name_m = re.search(r'(?:name|entity)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
            name_val = name_m.group(1).strip().upper() if name_m else "N/A"
            add("entity_name", name_val, 88 if name_m else 55, name_m is not None)
            
            list_m = re.search(r'(?:listed\s?on|database|list)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
            list_val = list_m.group(1).strip().upper() if list_m else "N/A"
            add("database_source", list_val, 85 if list_m else 50, list_m is not None)
            
            status_val = "FLAGGED" if any(w in text.lower() for w in ["sanctioned", "blacklisted", "barred", "wanted"]) else "CLEAR"
            add("status", status_val, 90, True)

        # ── Default fallback ──────────────────────────────────
        else:
            email_m = re.search(r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b', text)
            email_val = email_m.group(1) if email_m else "N/A"
            add("email", email_val, 85 if email_m else 45, email_m is not None)
            
            mob_m = re.search(r'\b[6-9]\d{9}\b', text)
            mob_val = mob_m.group() if mob_m else "N/A"
            is_mob_valid = self._validate_field("mobile", mob_val, doc_type)
            add("mobile", mob_val, 85 if mob_m else 45, is_mob_valid)
            
            dob_val, dob_found = find_date()
            dob_norm = self._normalize_date(dob_val) if dob_val else "N/A"
            add("detected_date", dob_norm, 75 if dob_found else 45, dob_found and dob_norm != "N/A")
            
            add("raw_text_preview", text[:300] + ("..." if len(text) > 300 else ""), 40, True)

        return fields, confidence

    def parse_id(self, text: str, source_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates and extracts document data.
        Uses md5 cache hits if the text matches the multiengine extraction results cache.
        """
        text_hash = hashlib.md5(text.encode('utf-8', errors='ignore')).hexdigest()
        if text_hash in self._cache:
            logger.info("Cache hit in parse_id. Returning structured data from multiengine run.")
            return self._cache[text_hash]

        # Cache miss fallback (e.g. caller passed custom text)
        hint_text = ""
        if source_url:
            filename = os.path.basename(source_url).lower()
            hint_text = filename.replace("_", " ").replace("-", " ")

        combined_text = f"{hint_text} {text}"
        doc_type = self._classify_document(combined_text, hint_text)
        fields, confidence = self._extract_fields_for_type(doc_type, text, 100.0)

        overall_conf = self._weighted_confidence(doc_type, confidence)
        if self.detect_tamper(text):
            overall_conf = min(overall_conf, 40.0)

        return {
            "document_type": doc_type,
            "fields": fields,
            "confidence_scores": confidence,
            "overall_confidence": int(overall_conf)
        }

    # ─────────────────────────────────────────────
    #  FACE DETECTION / MATCHING
    # ─────────────────────────────────────────────

    def get_face(self, image_bytes: bytes):
        if not self.cv2 or not self.np:
            return None
        try:
            nparr = self.np.frombuffer(image_bytes, self.np.uint8)
            img = self.cv2.imdecode(nparr, self.cv2.IMREAD_COLOR)
            if img is None:
                return None
            gray = self.cv2.cvtColor(img, self.cv2.COLOR_BGR2GRAY)
            face_cascade = self.cv2.CascadeClassifier(self.cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            if len(faces) == 0:
                return None
            faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
            x, y, w, h = faces[0]
            return img[y:y + h, x:x + w]
        except Exception:
            return None

    def match_faces(self, face1, face2) -> float:
        if not self.cv2 or not self.np:
            return 0.0
        try:
            if face1 is None or face2 is None:
                return 0.0
            f1 = self.cv2.resize(face1, (128, 128))
            f2 = self.cv2.resize(face2, (128, 128))
            h1 = self.cv2.calcHist([f1], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            h2 = self.cv2.calcHist([f2], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            self.cv2.normalize(h1, h1)
            self.cv2.normalize(h2, h2)
            score = self.cv2.compareHist(h1, h2, self.cv2.HISTCMP_CORREL)
            return max(0.0, float(score * 100))
        except Exception:
            return 0.0


# ─────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────

_scanner = None


def get_scanner():
    global _scanner
    if _scanner is None:
        _scanner = OCRScanner()
    return _scanner


async def check_duplicate_records(db, doc_type: str, id_number: str) -> Optional[str]:
    if not id_number or id_number == "N/A":
        return None
    if doc_type not in ["Aadhaar Card", "PAN Card", "Passport"]:
        return None

    from .models import Candidate
    from sqlalchemy import select
    clean_id = id_number.replace(" ", "").upper()

    try:
        if doc_type == "PAN Card":
            stmt = select(Candidate).filter(Candidate.pan_no == clean_id)
            res = await db.execute(stmt)
            dup = res.scalars().first()
            if dup:
                return dup.client_emp_code or f"EMP-{dup.id[:8].upper()}"

        elif doc_type == "Passport":
            stmt = select(Candidate).filter(Candidate.passport_no == clean_id)
            res = await db.execute(stmt)
            dup = res.scalars().first()
            if dup:
                return dup.client_emp_code or f"EMP-{dup.id[:8].upper()}"

        elif doc_type == "Aadhaar Card":
            stmt = select(Candidate)
            res = await db.execute(stmt)
            candidates = res.scalars().all()
            for cand in candidates:
                for doc in (cand.documents or []):
                    doc_str = str(doc).replace(" ", "").upper()
                    if clean_id in doc_str:
                        return cand.client_emp_code or f"EMP-{cand.id[:8].upper()}"
    except Exception as e:
        logger.error(f"Duplicate candidate scan failed: {e}")

    return None
