import re
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

class TextSanitizer:
    @staticmethod
    def remove_leading_garbage(text: str) -> str:
        """Removes leading punctuation, OCR artifacts, and garbage characters."""
        if not text:
            return ""
        # Match any of these characters at the start of the string, one or more times, possibly mixed with spaces
        pattern = r"^[,\.;:'\"`\~!@#\$%\^&\*\(\)_\+=\|\\/\<\>\?\s]+"
        return re.sub(pattern, "", str(text)).strip()

    @staticmethod
    def collapse_multiple_spaces(text: str) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", str(text)).strip()

    @staticmethod
    def remove_duplicate_commas(text: str) -> str:
        if not text:
            return ""
        # Remove consecutive commas (e.g., ",,," -> ",")
        text = re.sub(r",\s*,+", ",", str(text))
        # Remove commas followed by dots or dots followed by commas
        text = re.sub(r",\.", ",", text)
        text = re.sub(r"\.,", ".", text)
        # Remove consecutive dots
        text = re.sub(r"\.\.+", ".", text)
        # Remove trailing commas
        text = re.sub(r",\s*$", "", text)
        return text

    @staticmethod
    def clean_text(text: str) -> str:
        """Generic cleanup for any field."""
        if not text:
            return ""
        text = TextSanitizer.remove_leading_garbage(text)
        text = TextSanitizer.collapse_multiple_spaces(text)
        text = TextSanitizer.remove_duplicate_commas(text)
        return text.strip()

    @staticmethod
    def clean_name(text: str) -> str:
        """Cleans names: removes OCR garbage, trims, and converts to Title Case."""
        text = TextSanitizer.clean_text(text)
        if not text:
            return ""
        # Remove characters that shouldn't be in a name (allow letters, spaces, dots, and hyphens)
        text = re.sub(r"[^A-Za-z\s\.-]", "", text)
        text = TextSanitizer.collapse_multiple_spaces(text)
        # Title case
        # Capitalize parts properly e.g. "BALAMURUGAN S" -> "Balamurugan S"
        return text.title()

    @staticmethod
    def clean_address(text: str) -> str:
        """Normalizes addresses: common abbreviations and formatting."""
        text = TextSanitizer.clean_text(text)
        if not text:
            return ""
        
        # Word mappings (case insensitive replacement)
        replacements = {
            r"\bSTREET\b": "Street",
            r"\bNO\b": "No",
            r"\bST\b": "St.",
            r"\bROAD\b": "Road",
            r"\bRD\b": "Rd.",
            r"\bLANE\b": "Lane",
            r"\bLN\b": "Ln.",
            r"\bPOST\b": "PO",
            r"\bDISTRICT\b": "Dist.",
            r"\bTALUK\b": "Taluk"
        }
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            
        # Fix missing space after comma
        text = re.sub(r",([^\s])", r", \1", text)
        return TextSanitizer.collapse_multiple_spaces(text)

    @staticmethod
    def clean_pincode(text: str) -> str:
        """Extracts exactly 6 digits."""
        if not text:
            return ""
        digits = re.sub(r"\D", "", str(text))
        if len(digits) == 6:
            return digits
        # Try finding a 6-digit sequence in case there's surrounding text
        match = re.search(r"\b\d{6}\b", text)
        if match:
            return match.group(0)
        return "" # Reject partial or invalid pincode

    @staticmethod
    def clean_aadhaar(text: str) -> str:
        """Extracts exactly 12 digits, ignoring spaces."""
        if not text:
            return ""
        digits = re.sub(r"\D", "", str(text))
        if len(digits) == 12:
            return digits
        # Fallback regex just in case
        match = re.search(r"\b\d{12}\b", digits)
        if match:
            return match.group(0)
        return ""

    @staticmethod
    def clean_pan(text: str) -> str:
        text = TextSanitizer.clean_text(text).upper()
        # Clean anything that is not alphanumeric
        cleaned = re.sub(r"[^A-Z0-9]", "", text)
        if len(cleaned) >= 10:
            # typical format: 5 letters, 4 digits, 1 letter
            match = re.search(r"[A-Z]{5}[0-9]{4}[A-Z]{1}", cleaned)
            if match:
                return match.group(0)
            return cleaned[:10]
        return text

    @staticmethod
    def clean_date(text: str) -> str:
        """Converts DD/MM/YYYY, DD-MM-YYYY, YYYY/MM/DD, YYYY-MM-DD -> YYYY-MM-DD."""
        text = TextSanitizer.clean_text(text)
        if not text:
            return ""
        
        # Extract date-like pattern
        match = re.search(r"(\d{2,4})[-/](\d{1,2})[-/](\d{2,4})", text)
        if not match:
            return text
            
        part1, part2, part3 = match.groups()
        
        try:
            # If part1 is 4 digits, it's YYYY-MM-DD
            if len(part1) == 4:
                year, month, day = int(part1), int(part2), int(part3)
            # If part3 is 4 digits, it's DD-MM-YYYY
            elif len(part3) == 4:
                year, month, day = int(part3), int(part2), int(part1)
            else:
                return text # Can't confidently determine year
                
            # Basic validation
            if 1 <= month <= 12 and 1 <= day <= 31:
                return f"{year:04d}-{month:02d}-{day:02d}"
        except Exception:
            pass
            
        return text

    @staticmethod
    def sanitize_payload(raw_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Iterates through extracted fields and applies specific sanitization rules."""
        sanitized = {}
        for key, value in raw_dict.items():
            if not isinstance(value, str):
                sanitized[key] = value
                continue
                
            k = key.lower()
            if "name" in k and "father" not in k and "mother" not in k and "spouse" not in k:
                sanitized[key] = TextSanitizer.clean_name(value)
            elif "father" in k or "mother" in k or "spouse" in k:
                sanitized[key] = TextSanitizer.clean_name(value)
            elif "address" in k or "state" in k or "district" in k or "city" in k:
                sanitized[key] = TextSanitizer.clean_address(value)
            elif "pin" in k or "zip" in k:
                sanitized[key] = TextSanitizer.clean_pincode(value)
            elif "dob" in k or "date" in k:
                sanitized[key] = TextSanitizer.clean_date(value)
            elif "aadhaar" in k or "aadhar" in k:
                sanitized[key] = TextSanitizer.clean_aadhaar(value)
            elif "pan" in k:
                sanitized[key] = TextSanitizer.clean_pan(value)
            elif "mobile" in k or "phone" in k:
                # Basic mobile cleanup
                digits = re.sub(r"\D", "", str(value))
                sanitized[key] = digits[-10:] if len(digits) >= 10 else digits
            else:
                sanitized[key] = TextSanitizer.clean_text(value)
                
            logger.info(f"Sanitized field [{key}]: Raw='{value}' -> Clean='{sanitized[key]}'")
            
        return sanitized
