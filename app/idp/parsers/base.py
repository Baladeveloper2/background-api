import re
from datetime import datetime
from typing import Dict, Tuple, Any

class BaseParser:
    """Base class for all IDP document parsers."""
    
    document_type = "Unknown"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        """Determines if this parser is suitable for the given text."""
        return False
        
    def extract_fields(self, text: str) -> Dict[str, Any]:
        """Extracts fields and returns them as a dict."""
        return {}
        
    def get_confidence_weights(self) -> Dict[str, float]:
        """Returns weight distribution for overall confidence score calculation."""
        return {}
        
    def validate_field(self, field_name: str, value: str) -> bool:
        """Validates standard field values."""
        if not value or value == "N/A" or value.strip() == "":
            return False
        value_clean = value.strip()
        
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
            
        if "date" in field_name or field_name in ["dob", "dob_on_id", "validity", "agreement_start", "agreement_end", "joining_date", "relieving_date", "report_date", "test_date", "expiry_date"]:
            cleaned = value_clean.replace("/", "-")
            for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%m-%y"):
                try:
                    datetime.strptime(cleaned, fmt)
                    return True
                except ValueError:
                    continue
            return False
            
        return True

    def normalize_date(self, value: str) -> str:
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

    def find_date(self, text: str) -> Tuple[str, bool]:
        m = re.search(r'(\d{2}[-/]\d{2}[-/]\d{4}|\d{4}[-/]\d{2}[-/]\d{2})', text)
        return (m.group(1) if m else None, bool(m))

    def evaluate_extraction(self, text: str, engine_confidence: float) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """Wraps extraction with confidence scoring."""
        raw_fields = self.extract_fields(text)
        fields = {}
        confidence = {}
        
        for key, val_dict in raw_fields.items():
            value = val_dict.get('value', 'N/A')
            base_conf = val_dict.get('base_conf', 50)
            is_valid = self.validate_field(key, value)
            
            # Custom validation override
            if 'is_valid' in val_dict:
                is_valid = val_dict['is_valid']
                
            fields[key] = value
            if not is_valid or value == "N/A":
                conf = min(50, int(base_conf * 0.5))
            else:
                conf = int(base_conf * (engine_confidence / 100.0))
            confidence[key] = min(100, max(40, conf))
            
        return fields, confidence
