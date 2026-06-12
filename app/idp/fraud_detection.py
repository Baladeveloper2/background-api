import logging

logger = logging.getLogger("idp.fraud_detection")

class FraudDetector:
    def __init__(self, preprocessor):
        self.preprocessor = preprocessor

    def detect_blur(self, image_bytes: bytes) -> bool:
        if not self.preprocessor.cv2 or not self.preprocessor.np:
            return False
        try:
            # We need just grayscale for laplacian variance
            nparr = self.preprocessor.np.frombuffer(image_bytes, self.preprocessor.np.uint8)
            img = self.preprocessor.cv2.imdecode(nparr, self.preprocessor.cv2.IMREAD_COLOR)
            if img is None:
                return False
            gray = self.preprocessor.cv2.cvtColor(img, self.preprocessor.cv2.COLOR_BGR2GRAY)
            variance = self.preprocessor.cv2.Laplacian(gray, self.preprocessor.cv2.CV_64F).var()
            return variance < 80.0
        except Exception:
            return False

    def detect_crop(self, image_bytes: bytes) -> bool:
        if not self.preprocessor.cv2 or not self.preprocessor.np:
            return False
        try:
            nparr = self.preprocessor.np.frombuffer(image_bytes, self.preprocessor.np.uint8)
            img = self.preprocessor.cv2.imdecode(nparr, self.preprocessor.cv2.IMREAD_COLOR)
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
        if not self.preprocessor.cv2 or not self.preprocessor.np:
            return False
        try:
            nparr = self.preprocessor.np.frombuffer(image_bytes, self.preprocessor.np.uint8)
            img = self.preprocessor.cv2.imdecode(nparr, self.preprocessor.cv2.IMREAD_COLOR)
            if img is None:
                return False
            h, w = img.shape[:2]
            return (w * h) < (400 * 300)
        except Exception:
            return False

    def check_file_duplicate(self, db_session, file_bytes: bytes) -> bool:
        import hashlib
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        from app.models import DocumentMetadata
        from sqlalchemy import select
        stmt = select(DocumentMetadata).filter(DocumentMetadata.file_hash == file_hash)
        res = db_session.execute(stmt)
        return res.scalar_one_or_none() is not None

    def calculate_fraud_score(self, text: str, image_bytes: bytes) -> int:
        score = 0
        if self.detect_blur(image_bytes):
            score += 20
        if self.detect_crop(image_bytes):
            score += 15
        if self.detect_low_resolution(image_bytes):
            score += 10
        if self.detect_tamper(text):
            score += 50
            
        return min(100, score)
