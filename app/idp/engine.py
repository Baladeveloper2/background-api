import os
import sys
import re
import hashlib
import time
import logging
import concurrent.futures
from typing import Dict, Any, Optional, Tuple, List, Callable
from .preprocessing import ImagePreprocessor
from .fraud_detection import FraudDetector
from .parsers.registry import get_registered_parsers, get_default_parser
from .cloud_integrations import CloudOCREngines

logger = logging.getLogger("idp.engine")

class DocumentIntelligenceEngine:
    """Production-grade modular OCR Engine."""
    
    def __init__(self):
        self.preprocessor = ImagePreprocessor()
        self.fraud_detector = FraudDetector(self.preprocessor)
        
        self.paddle_reader = None
        self.doctr_predictor = None
        self.easy_reader = None
        self._cache = {}
        
        self.parsers = [parser_cls() for parser_cls in get_registered_parsers()]
        self.default_parser = get_default_parser()()
        
        # Pre-load PaddleOCR immediately as a singleton
        self._load_paddle()
        
    def _load_paddle(self):
        if self.paddle_reader is None and self.preprocessor.cv2 and self.preprocessor.np:
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
        if self.doctr_predictor is None and self.preprocessor.cv2 and self.preprocessor.np:
            try:
                from doctr.models import ocr_predictor
                self.doctr_predictor = ocr_predictor(pretrained=True)
            except Exception as e:
                logger.warning(f"DocTR not available: {e}.")
        return self.doctr_predictor

    def _load_easyocr(self):
        if self.easy_reader is None and self.preprocessor.cv2 and self.preprocessor.np:
            try:
                import easyocr
                self.easy_reader = easyocr.Reader(['en'])
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
            return None

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
                            
        text = "\n".join(text_parts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.5
        if avg_conf <= 1.0:
            avg_conf *= 100
        return text, avg_conf

    def _run_doctr(self, engine, img) -> Tuple[str, float]:
        result = engine([img])
        lines_list = []
        conf_list = []
        for page in result.pages:
            for block in page.blocks:
                for line in block.lines:
                    line_words = []
                    for word in line.words:
                        line_words.append(word.value)
                        conf_list.append(word.confidence)
                    if line_words:
                        lines_list.append(" ".join(line_words))
        text = "\n".join(lines_list)
        avg_conf = sum(conf_list) / len(conf_list) if conf_list else 0.5
        if avg_conf <= 1.0:
            avg_conf *= 100
        return text, avg_conf

    def _run_easyocr(self, engine, img) -> Tuple[str, float]:
        results = engine.readtext(img, detail=1)
        lines_list = []
        conf_list = []
        for res in results:
            lines_list.append(res[1])
            conf_list.append(res[2])
        text = "\n".join(lines_list)
        avg_conf = sum(conf_list) / len(conf_list) if conf_list else 0.5
        if avg_conf <= 1.0:
            avg_conf *= 100
        return text, avg_conf

    def _run_tesseract(self, engine, img) -> Tuple[str, float]:
        data = engine.image_to_data(img, output_type=engine.Output.DICT)
        lines_dict = {}
        conf_list = []
        for i in range(len(data['text'])):
            w = data['text'][i].strip()
            c = int(data['conf'][i])
            if w and c >= 0:
                line_id = f"{data['block_num'][i]}_{data['par_num'][i]}_{data['line_num'][i]}"
                if line_id not in lines_dict:
                    lines_dict[line_id] = []
                lines_dict[line_id].append(w)
                conf_list.append(c)
        text = "\n".join([" ".join(words) for words in lines_dict.values()])
        avg_conf = sum(conf_list) / len(conf_list) if conf_list else 50.0
        return text, avg_conf

    def _get_best_parser(self, text: str, hint_text: str):
        for parser in self.parsers:
            if parser.can_parse(text, hint_text):
                return parser
        return self.default_parser

    def _weighted_confidence(self, parser, confidence_scores: Dict[str, float]) -> float:
        if not confidence_scores:
            return 50.0
        
        weights = parser.get_confidence_weights()
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

    def _pre_classify_document(self, image_bytes: bytes, hint_text: str = "") -> str:
        """Fast pre-OCR pass to determine document type before heavy preprocessing."""
        try:
            # Downscale image drastically for fast Tesseract pass
            if self.preprocessor.cv2 and self.preprocessor.np:
                nparr = self.preprocessor.np.frombuffer(image_bytes, self.preprocessor.np.uint8)
                img = self.preprocessor.cv2.imdecode(nparr, self.preprocessor.cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    h, w = img.shape
                    if w > 800 or h > 800:
                        scale = min(800/w, 800/h)
                        img = self.preprocessor.cv2.resize(img, (int(w*scale), int(h*scale)))
                    
                    tess = self._load_tesseract()
                    if tess:
                        text = tess.image_to_string(img)
                        parser = self._get_best_parser(f"{hint_text} {text}", hint_text)
                        logger.info(f"Pre-classification detected: {parser.document_type}")
                        return parser.document_type
        except Exception as e:
            logger.warning(f"Pre-classification failed: {e}")
            
        return "Unknown Document"

    def process_document(self, image_bytes: bytes, source_url: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Main entry point for extracting and processing document intelligence."""
        
        if not self.preprocessor.cv2 or not self.preprocessor.np:
            return {
                "success": False,
                "error": "Missing system dependencies (OpenCV/Numpy). Cannot perform OCR.",
                "engine_used": "NONE",
                "extractedFields": {}
            }

        hint_text = ""
        if source_url:
            hint_text = os.path.basename(source_url).lower().replace("_", " ").replace("-", " ")
            
        def safe_callback(status, progress, doc_type="Unknown"):
            if kwargs.get("progress_callback"):
                try:
                    kwargs["progress_callback"](status, progress, doc_type)
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")

        # Fraud Detection (runs concurrently conceptually)
        fraud_score = self.fraud_detector.calculate_fraud_score("", image_bytes)

        # 1. Pre-classification
        preprocessing_steps = []
        safe_callback("PREPARING_DOCUMENT", 10)
        pre_classified_type = self._pre_classify_document(image_bytes, hint_text)
        preprocessing_steps.append(f"PRE_CLASSIFIED_AS_{pre_classified_type.upper().replace(' ', '_')}")

        # 2. Preprocessing
        safe_callback("CONVERTING_TO_IMAGES", 20, pre_classified_type)
        image_bytes = self.preprocessor.correct_exif_orientation(image_bytes)
        is_pdf = image_bytes[:4] == b'%PDF'
        
        pages = []
        if is_pdf:
            pages, pdf_steps = self.preprocessor.pdf_to_images(image_bytes)
            preprocessing_steps.extend(pdf_steps)
        else:
            if self.preprocessor.cv2 and self.preprocessor.np:
                nparr = self.preprocessor.np.frombuffer(image_bytes, self.preprocessor.np.uint8)
                img = self.preprocessor.cv2.imdecode(nparr, self.preprocessor.cv2.IMREAD_COLOR)
                if img is not None:
                    pages = [img]
                    
        if not pages:
            # Hard fail instead of mock fallback
            return {
                "success": False,
                "error": "Failed to decode document pages. Invalid file or missing dependencies.",
                "engine_used": "NONE",
                "extractedFields": {}
            }

        if pre_classified_type in ["Aadhaar Card", "PAN Card", "Passport", "Driving License", "Voter ID"]:
            pages = pages[:1]

        preprocessed_pages = []
        safe_callback("IMAGE_PREPROCESSING", 35, pre_classified_type)
        for page in pages:
            prep_page, page_steps = self.preprocessor.preprocess_image_pipeline(page)
            preprocessed_pages.append(prep_page)
            for ps in page_steps:
                if ps not in preprocessing_steps:
                    preprocessing_steps.append(ps)

        # 3. Multi-engine text extraction (Free Local Python Libraries Only)
        safe_callback("RUNNING_OCR_ENGINE", 50, pre_classified_type)
        
        is_manual_retry = kwargs.get("is_manual_retry", False)
        
        if is_manual_retry:
            engines = [
                ("DOCTR", self._load_doctr, self._run_doctr)
            ]
        else:
            engines = [
                ("PADDLE", self._load_paddle, self._run_paddle),
                ("EASYOCR", self._load_easyocr, self._run_easyocr)
            ]

        runs = []
        retry_count = 0
        
        workers = min(os.cpu_count() or 4, 4)
        
        for name, loader_fn, runner_fn in engines:
            safe_callback(f"INITIALIZING_ENGINE_{name}", 55, pre_classified_type)
            engine_inst = loader_fn()
            if not engine_inst:
                continue

            page_texts = []
            page_confs = []
            try:
                safe_callback(f"EXTRACTING_TEXT_VIA_{name}", 65, pre_classified_type)
                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = []
                    for prep_page in preprocessed_pages:
                        futures.append(executor.submit(runner_fn, engine_inst, prep_page))
                    for future in concurrent.futures.as_completed(futures):
                        text, conf = future.result()
                        page_texts.append(text)
                        page_confs.append(conf)
            except Exception as e:
                logger.error(f"OCR execution failed for {name}: {e}")
                retry_count += 1
                continue

            full_text = "\n".join(page_texts)
            avg_ocr_conf = sum(page_confs) / len(page_confs) if page_confs else 50.0
            
            safe_callback("EXTRACTING_FIELDS", 80, pre_classified_type)
            combined_text = f"{hint_text} {full_text}"
            parser = self._get_best_parser(combined_text, hint_text)
            fields, field_confs = parser.evaluate_extraction(full_text, avg_ocr_conf)
            
            safe_callback("CALCULATING_CONFIDENCE", 90, parser.document_type)
            weighted_conf = self._weighted_confidence(parser, field_confs)
            
            id_val = fields.get("id_number", "N/A")
            is_valid_id = parser.validate_field("id_number", id_val)
            
            is_identity = parser.document_type in ["Aadhaar Card", "PAN Card", "Passport", "Driving License", "Voter ID"]
            id_ok = not is_identity or is_valid_id
            
            runs.append((name, full_text, parser, fields, field_confs, weighted_conf))
            
            if weighted_conf >= 60.0 and id_ok:
                fraud_score = max(fraud_score, self.fraud_detector.calculate_fraud_score(full_text, image_bytes))
                safe_callback("CLEANING_TEXT", 95, parser.document_type)
                safe_callback("OCR_COMPLETED", 100, parser.document_type)
                return {
                    "success": True,
                    "documentType": parser.document_type,
                    "confidence": float(weighted_conf),
                    "extractedFields": fields,
                    "validation": {k: field_confs[k] >= 90 for k in field_confs},
                    "fraudScore": fraud_score,
                    "engine_used": name,
                    "retry_count": retry_count,
                    "preprocessing_steps": preprocessing_steps
                }

        # 3. Merging logic (if no >95% confidence result)
        if runs:
            all_text_combined = " ".join([r[1] for r in runs])
            best_parser = self._get_best_parser(f"{hint_text} {all_text_combined}", hint_text)
            
            aligned_runs = []
            for name, full_text, _, _, _, avg_ocr_conf in runs:
                f, fc = best_parser.evaluate_extraction(full_text, avg_ocr_conf)
                aligned_runs.append((name, full_text, f, fc))

            all_keys = set()
            for r in aligned_runs:
                all_keys.update(r[2].keys())

            import difflib
            merged_fields = {}
            merged_confs = {}
            for key in all_keys:
                val_votes = {}
                for name, full_text, fields_e, confs_e in aligned_runs:
                    val = fields_e.get(key, "N/A")
                    score = confs_e.get(key, 40)
                    if val != "N/A" and val.strip() != "":
                        norm_val = re.sub(r'[^A-Za-z0-9]', '', val).upper()
                        if not norm_val:
                            norm_val = val
                        found_match = False
                        for k_vote in val_votes.keys():
                            if difflib.SequenceMatcher(None, k_vote, norm_val).ratio() > 0.85:
                                val_votes[k_vote]['score'] += score * 0.5
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
                if val_votes:
                    best_vote = max(val_votes.values(), key=lambda x: (best_parser.validate_field(key, x['best_val']), x['score']))
                    best_val = best_vote['best_val']
                    best_score = min(100, best_vote['best_score'] + (10 if best_vote['count'] > 1 else 0))
                
                merged_fields[key] = best_val
                merged_confs[key] = best_score
                
            overall_merged_conf = self._weighted_confidence(best_parser, merged_confs)
            fraud_score = max(fraud_score, self.fraud_detector.calculate_fraud_score(all_text_combined, image_bytes))
            
            return {
                "success": True,
                "documentType": best_parser.document_type,
                "confidence": float(overall_merged_conf),
                "extractedFields": merged_fields,
                "validation": {k: merged_confs[k] >= 90 for k in merged_confs},
                "fraudScore": fraud_score,
                "engine_used": "MERGED",
                "retry_count": len(runs),
                "preprocessing_steps": preprocessing_steps
            }

        return {
            "success": False,
            "status": "FAILED",
            "reason": "No OCR engine installed",
            "engine": "NONE",
            "engine_used": "NONE"
        }

# Singleton instance
_engine = None

def get_idp_engine():
    global _engine
    if _engine is None:
        _engine = DocumentIntelligenceEngine()
    return _engine
