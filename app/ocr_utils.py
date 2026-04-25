import re
from typing import Dict, Any, Optional

class OCRScanner:
    def __init__(self):
        # Heavy imports inside __init__ to avoid startup overhead
        import easyocr
        import cv2
        import numpy as np
        self.easyocr = easyocr
        self.cv2 = cv2
        self.np = np
        # Initialize reader for English.
        self.reader = easyocr.Reader(['en'])

    def preprocess_image(self, image_bytes: bytes):
        nparr = self.np.frombuffer(image_bytes, self.np.uint8)
        img = self.cv2.imdecode(nparr, self.cv2.IMREAD_COLOR)
        # Convert to grayscale for better OCR
        gray = self.cv2.cvtColor(img, self.cv2.COLOR_BGR2GRAY)
        return gray

    def extract_text(self, image_bytes: bytes) -> str:
        results = self.reader.readtext(image_bytes, detail=0)
        return " ".join(results)

    def parse_id(self, text: str) -> Dict[str, Any]:
        data = {
            "id_type": "Unknown",
            "id_number": "",
            "name_on_id": "",
            "dob_on_id": "",
            "father_name": "",
            "gender": ""
        }

        # PAN Card Detection
        if re.search(r'INCOME TAX DEPARTMENT|PERMANENT ACCOUNT NUMBER', text, re.IGNORECASE):
            data["id_type"] = "PAN Card"
            pan_match = re.search(r'[A-Z]{5}[0-9]{4}[A-Z]{1}', text)
            if pan_match:
                data["id_number"] = pan_match.group()
            
            # Name is usually the line after "INCOME TAX DEPARTMENT" or common labels
            # We'll look for Uppercase words that don't match common labels
            lines = text.split(' ')
            for line in lines:
                if len(line) > 3 and line.isupper() and not any(x in line for x in ['INCOME', 'TAX', 'DEPARTMENT', 'INDIA', 'GOVT', 'PERMANENT', 'ACCOUNT', 'NUMBER', 'CARD']):
                   if not data["name_on_id"]:
                       data["name_on_id"] = line
                   elif not data["father_name"] and line != data["name_on_id"]:
                       data["father_name"] = line
            
        # Aadhaar Detection
        elif re.search(r'Aadhaar| Unique Identification Authority', text, re.IGNORECASE):
            data["id_type"] = "Aadhaar Card"
            aadhaar_match = re.search(r'\d{4}\s?\d{4}\s?\d{4}', text)
            if aadhaar_match:
                data["id_number"] = aadhaar_match.group().replace(" ", "")
            
            if "Male" in text: data["gender"] = "Male"
            elif "Female" in text: data["gender"] = "Female"

            # Name extraction for Aadhaar is tricky from raw text, 
            # but usually it's the first few words that are not "Aadhaar" or "Authority"
            words = text.split(' ')
            potential_names = [w for w in words if w.isalpha() and len(w) > 2 and w[0].isupper() and w.upper() not in ['AADHAAR', 'UNIQUE', 'IDENTIFICATION', 'AUTHORITY', 'GOVERNMENT', 'INDIA', 'MALE', 'FEMALE']]
            if potential_names:
                data["name_on_id"] = " ".join(potential_names[:2])
            
            dob_match = re.search(r'DOB:?\s?(\d{2}/\d{2}/\d{4})', text)
            if dob_match:
                data["dob_on_id"] = dob_match.group(1)

            # Father/Husband Name (S/O, D/O, W/O)
            parent_match = re.search(r'(?:S/O|D/O|W/O):?\s?([A-Z\s]+)', text, re.IGNORECASE)
            if parent_match:
                data["father_name"] = parent_match.group(1).strip()

            # Address (usually after a pin code or specific keywords)
            # This is very rough but better than nothing
            address_match = re.search(r'Address:?\s?(.+?)\s?\d{6}', text, re.IGNORECASE)
            if address_match:
                data["address"] = address_match.group(1).strip()

        # Employment / Education Detection (Generic)
        elif re.search(r'Experience|Relieving|Letter|Offer|Certificate|Degree|Marksheet|University|College|Institute|Limited|Pvt|Ltd', text, re.IGNORECASE):
            data["id_type"] = "Supporting Document"
            
            # Extract Organization (Employer/University)
            # Usually found near "Limited", "Ltd", "University", "College"
            org_match = re.search(r'([A-Z][A-Za-z\s&\.]+ (?:Limited|Pvt|Ltd|University|College|Institute|School))', text, re.IGNORECASE)
            if org_match:
                data["organization"] = org_match.group(1).strip()
            
            # Extract Candidate Name from common salutations
            name_match = re.search(r'(?:Mr\.|Ms\.|Mrs\.|Shri|Smt\.?)\s?([A-Z][A-Z\s]+)', text)
            if name_match:
                data["name_on_id"] = name_match.group(1).split('\n')[0].strip()
            
            # Specialized for Degree
            if re.search(r'Degree|Diploma|Certificate', text, re.IGNORECASE):
                data["id_type"] = "Education Certificate"
            
        return data

    def get_face(self, image_bytes: bytes):
        try:
            nparr = self.np.frombuffer(image_bytes, self.np.uint8)
            img = self.cv2.imdecode(nparr, self.cv2.IMREAD_COLOR)
            if img is None: return None
            
            gray = self.cv2.cvtColor(img, self.cv2.COLOR_BGR2GRAY)
            face_cascade = self.cv2.CascadeClassifier(self.cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            
            if len(faces) == 0: return None
            
            # Sort by area and take largest
            faces = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)
            x, y, w, h = faces[0]
            face_crop = img[y:y+h, x:x+w]
            return face_crop
        except Exception:
            return None

    def match_faces(self, face1, face2) -> float:
        try:
            if face1 is None or face2 is None: return 0.0
            
            # Normalize
            f1 = self.cv2.resize(face1, (128, 128))
            f2 = self.cv2.resize(face2, (128, 128))
            
            # Histogram comparison (simple biometric proxy)
            h1 = self.cv2.calcHist([f1], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            h2 = self.cv2.calcHist([f2], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            self.cv2.normalize(h1, h1)
            self.cv2.normalize(h2, h2)
            
            score = self.cv2.compareHist(h1, h2, self.cv2.HISTCMP_CORREL)
            return max(0, score * 100)
        except Exception:
            return 0.0

# Global instance
_scanner = None

def get_scanner():
    global _scanner
    if _scanner is None:
        _scanner = OCRScanner()
    return _scanner
