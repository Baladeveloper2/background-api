import re
from .base import BaseParser

class AadhaarParser(BaseParser):
    document_type = "Aadhaar Card"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        return bool(re.search(r'aadhaar|uidai|unique\s?identification|government\s?of\s?india', text, re.IGNORECASE) or 'aadhaar' in hint_text)
        
    def extract_fields(self, text: str):
        fields = {}
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        num_m = re.search(r'\b(\d{4}\s?\d{4}\s?\d{4})\b', text)
        id_val = num_m.group(1).replace(" ", "") if num_m else "N/A"
        fields["aadhaar_number"] = {"value": id_val, "base_conf": 98 if num_m else 50}
        fields["id_number"] = {"value": id_val, "base_conf": 98 if num_m else 50}
        
        # 2. Gender
        gender_val = "Female" if re.search(r'\bfemale\b', text, re.IGNORECASE) else ("Male" if re.search(r'\bmale\b', text, re.IGNORECASE) else "N/A")
        fields["gender"] = {"value": gender_val, "base_conf": 99 if gender_val != "N/A" else 50}
        
        # 3. DOB and Name (Layout Aware)
        dob_val = "N/A"
        name_val = "N/A"
        dob_line_idx = -1
        
        for i, line in enumerate(lines):
            dob_m = re.search(r'(?:DOB|Birth|Year).*?(\d{2}[-/]\d{2}[-/]\d{4}|\d{4})', line, re.IGNORECASE)
            if dob_m:
                dob_val = self.normalize_date(dob_m.group(1))
                dob_line_idx = i
                break
                
        fields["dob"] = {"value": dob_val, "base_conf": 96 if dob_val != "N/A" else 50}
        fields["dob_on_id"] = {"value": dob_val, "base_conf": 96 if dob_val != "N/A" else 50}
        
        # Name is usually 1-2 lines above DOB
        if dob_line_idx > 0:
            for j in range(dob_line_idx - 1, max(-1, dob_line_idx - 4), -1):
                candidate = lines[j]
                # A good name candidate: Mostly alphabets, length > 3, not Government of India
                if re.match(r'^[A-Za-z\s\.]+$', candidate) and len(candidate) > 3 and not re.search(r'government|india', candidate, re.IGNORECASE):
                    name_val = candidate.upper()
                    break
                    
        # Fallback for Name if layout fails
        if name_val == "N/A":
            name_m = re.search(r'(?:name|to|shri)[:\s]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)', text, re.IGNORECASE)
            if name_m: name_val = name_m.group(1).strip().upper()
            
        fields["name"] = {"value": name_val, "base_conf": 95 if name_val != "N/A" else 50}
        fields["name_on_id"] = {"value": name_val, "base_conf": 95 if name_val != "N/A" else 50}
        
        # 4. Address and Pincode
        addr_val = "N/A"
        pin_val = "N/A"
        
        address_started = False
        addr_lines = []
        for line in lines:
            if re.search(r'^(?:Address|Add)[:\s]', line, re.IGNORECASE):
                address_started = True
                addr_lines.append(re.sub(r'^(?:Address|Add)[:\s]+', '', line, flags=re.IGNORECASE))
            elif address_started:
                addr_lines.append(line)
                
            if address_started:
                pin_m = re.search(r'\b(\d{6})\b', line)
                if pin_m:
                    pin_val = pin_m.group(1)
                    break # Stop reading address after pincode
                    
        if addr_lines:
            addr_val = ", ".join(addr_lines).strip()
            if len(addr_val) > 200: addr_val = addr_val[:200]
            
        # Fallback pin
        if pin_val == "N/A":
            pin_m = re.search(r'\b(\d{6})\b', text)
            if pin_m: pin_val = pin_m.group(1)

        fields["address"] = {"value": addr_val, "base_conf": 92 if addr_val != "N/A" else 55}
        fields["address_on_id"] = {"value": addr_val, "base_conf": 92 if addr_val != "N/A" else 55}
        fields["pincode"] = {"value": pin_val, "base_conf": 95 if pin_val != "N/A" else 50}
        
        # Parse City, District, State from address
        city_val = "N/A"
        district_val = "N/A"
        state_val = "N/A"
        
        if addr_val != "N/A":
            parts = [p.strip() for p in addr_val.split(',')]
            if len(parts) >= 3:
                # State is typically the second to last part before pincode
                # City/District usually right before state
                possible_state = parts[-1]
                if re.match(r'^\d+$', possible_state) and len(parts) >= 2:
                    possible_state = parts[-2]
                    
                # Clean up state
                possible_state = re.sub(r'\d+', '', possible_state).strip()
                if possible_state:
                    state_val = possible_state
                    
                # Very basic heuristic for city/district (just picking preceding elements)
                if len(parts) >= 3 and state_val != "N/A":
                    district_val = parts[-3].strip()
                    city_val = parts[-3].strip()
                    
        fields["state"] = {"value": state_val, "base_conf": 90 if state_val != "N/A" else 50}
        fields["city"] = {"value": city_val, "base_conf": 90 if city_val != "N/A" else 50}
        fields["district"] = {"value": district_val, "base_conf": 90 if district_val != "N/A" else 50}
        
        # 5. Mobile
        mob_m = re.search(r'\b[6-9]\d{9}\b', text)
        mob_val = mob_m.group() if mob_m else "N/A"
        fields["mobile"] = {"value": mob_val, "base_conf": 95 if mob_m else 50}
        
        return fields

    def validate_field(self, field_name: str, value: str) -> bool:
        if field_name == "id_number":
            digits = re.sub(r'\D', '', value)
            return len(digits) == 12
        return super().validate_field(field_name, value)

    def get_confidence_weights(self):
        return {
            "aadhaar_number": 0.30,
            "name": 0.20,
            "dob": 0.15,
            "gender": 0.10,
            "address": 0.10,
            "pincode": 0.15
        }

class PANParser(BaseParser):
    document_type = "PAN Card"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        return bool(re.search(r'income\s?tax|permanent\s?account\s?number|pan\s?card', text, re.IGNORECASE) or re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b', text) or 'pan' in hint_text)
        
    def extract_fields(self, text: str):
        fields = {}
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        pan_m = re.search(r'\b([A-Z]{5}[0-9]{4}[A-Z]{1})\b', text)
        id_val = pan_m.group(1).upper() if pan_m else "N/A"
        fields["pan_number"] = {"value": id_val, "base_conf": 99 if pan_m else 50}
        fields["id_number"] = {"value": id_val, "base_conf": 99 if pan_m else 50}
        
        name_val = "N/A"
        father_val = "N/A"
        dob_val = "N/A"
        
        # Layout aware PAN extraction
        # Typically:
        # GOVT OF INDIA / INCOME TAX DEPT
        # <NAME>
        # <FATHER'S NAME>
        # <DOB>
        for i, line in enumerate(lines):
            # Find DOB line
            if re.search(r'\d{2}[-/]\d{2}[-/]\d{4}', line):
                dob_m = re.search(r'(\d{2}[-/]\d{2}[-/]\d{4})', line)
                if dob_m: dob_val = self.normalize_date(dob_m.group(1))
                # Father name is usually 1 line above DOB
                if i - 1 >= 0:
                    candidate_father = lines[i-1]
                    if re.match(r'^[A-Za-z\s]+$', candidate_father):
                        father_val = candidate_father.upper()
                # Name is usually 2 lines above DOB
                if i - 2 >= 0:
                    candidate_name = lines[i-2]
                    if re.match(r'^[A-Za-z\s]+$', candidate_name):
                        name_val = candidate_name.upper()
                break

        # Fallbacks
        if name_val == "N/A":
            name_m = re.search(r'([A-Z][A-Z\s]{3,29})\n', text)
            if name_m: name_val = name_m.group(1).strip().upper()
            
        if father_val == "N/A":
            f_m = re.search(r"(?:father|father's\s?name|parent)[:\s]+([A-Z\s]+)", text, re.IGNORECASE)
            if f_m: father_val = f_m.group(1).strip().upper()
            
        if dob_val == "N/A":
            dob_val_f, dob_found = self.find_date(text)
            if dob_found: dob_val = self.normalize_date(dob_val_f)

        fields["name"] = {"value": name_val, "base_conf": 95 if name_val != "N/A" else 50}
        fields["name_on_id"] = {"value": name_val, "base_conf": 95 if name_val != "N/A" else 50}
        fields["father_name"] = {"value": father_val, "base_conf": 95 if father_val != "N/A" else 55}
        fields["dob"] = {"value": dob_val, "base_conf": 95 if dob_val != "N/A" else 50}
        fields["dob_on_id"] = {"value": dob_val, "base_conf": 95 if dob_val != "N/A" else 50}
        
        return fields

    def validate_field(self, field_name: str, value: str) -> bool:
        if field_name == "id_number":
            return bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', value.upper()))
        return super().validate_field(field_name, value)

    def get_confidence_weights(self):
        return {
            "pan_number": 0.40,
            "name": 0.30,
            "father_name": 0.15,
            "dob": 0.15
        }

class PassportParser(BaseParser):
    document_type = "Passport"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        return bool(re.search(r'passport|republic\s?of\s?india|nationality.*indian', text, re.IGNORECASE) or re.search(r'^[A-Z]{1}[0-9]{7}', hint_text, re.IGNORECASE) or 'passport' in hint_text)
        
    def extract_fields(self, text: str):
        fields = {}
        pass_m = re.search(r'\b([A-Z]{1}[0-9]{7})\b', text)
        id_val = pass_m.group(1).upper() if pass_m else "N/A"
        fields["id_number"] = {"value": id_val, "base_conf": 99 if pass_m else 50}
        
        mrz_name_m = re.search(r'([A-Z]+)<<([A-Z]+)', text)
        if mrz_name_m:
            fields["name_on_id"] = {"value": f"{mrz_name_m.group(2)} {mrz_name_m.group(1)}".upper(), "base_conf": 97}
        else:
            name_m = re.search(r'(?:surname|given\s?name)[:\s]+([A-Z\s]+)', text, re.IGNORECASE)
            name_val = name_m.group(1).strip().upper() if name_m else "N/A"
            fields["name_on_id"] = {"value": name_val, "base_conf": 85 if name_m else 50}
            
        fields["nationality"] = {"value": "INDIAN", "base_conf": 99}
        
        dob_val, dob_found = self.find_date(text)
        dob_norm = self.normalize_date(dob_val) if dob_val else "N/A"
        fields["dob_on_id"] = {"value": dob_norm, "base_conf": 94 if dob_found else 50}
        
        exp_m = re.search(r'(?:expiry|valid\s?until|exp)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
        exp_val = self.normalize_date(exp_m.group(1)) if exp_m else "N/A"
        fields["expiry_date"] = {"value": exp_val, "base_conf": 92 if exp_m else 50}
        
        place_m = re.search(r'(?:place\s?of\s?birth|pob)[:\s]+([A-Za-z\s,]+)', text, re.IGNORECASE)
        place_val = place_m.group(1).strip() if place_m else "N/A"
        fields["place_of_birth"] = {"value": place_val, "base_conf": 88 if place_m else 50}
        
        return fields

    def validate_field(self, field_name: str, value: str) -> bool:
        if field_name == "id_number":
            return bool(re.match(r'^[A-Z][0-9]{7}$', value.upper()))
        return super().validate_field(field_name, value)

    def get_confidence_weights(self):
        return {
            "id_number": 0.35,
            "name_on_id": 0.25,
            "dob_on_id": 0.15,
            "expiry_date": 0.15,
            "place_of_birth": 0.10
        }

class VoterIDParser(BaseParser):
    document_type = "Voter ID"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        return bool(re.search(r'election\s?commission|voter\s?id|elector\s?photo\s?identity|epic\s?no|electoral\s?roll', text, re.IGNORECASE) or 'voter' in hint_text)

    def extract_fields(self, text: str):
        fields = {}
        epic_m = re.search(r'(?:EPIC\s?No|Epic|Voter\s?ID)[:\s]*([A-Z]{3}[0-9]{7})', text, re.IGNORECASE)
        id_val = epic_m.group(1).upper() if epic_m else "N/A"
        fields["id_number"] = {"value": id_val, "base_conf": 97 if epic_m else 50}
        
        name_m = re.search(r'(?:name|elector)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
        name_val = name_m.group(1).strip().upper() if name_m else "N/A"
        fields["name_on_id"] = {"value": name_val, "base_conf": 92 if name_m else 50}
        
        rel_m = re.search(r"(?:father|husband|mother|guardian)'?s?\s?name[:\s]+([A-Za-z\s]+)", text, re.IGNORECASE)
        rel_val = rel_m.group(1).strip().upper() if rel_m else "N/A"
        fields["relation_name"] = {"value": rel_val, "base_conf": 88 if rel_m else 50}
        
        addr_m = re.search(r'(?:address)[:\s]+(.+?)(?:\d{6}|$)', text, re.IGNORECASE | re.DOTALL)
        addr_val = addr_m.group(1).strip()[:200] if addr_m else "N/A"
        fields["address_on_id"] = {"value": addr_val, "base_conf": 88 if addr_m else 50}
        
        dob_val, dob_found = self.find_date(text)
        dob_norm = self.normalize_date(dob_val) if dob_val else "N/A"
        fields["dob_on_id"] = {"value": dob_norm, "base_conf": 85 if dob_found else 50}
        
        return fields

    def validate_field(self, field_name: str, value: str) -> bool:
        if field_name == "id_number":
            return bool(re.match(r'^[A-Z]{3}[0-9]{7}$', value.upper()))
        return super().validate_field(field_name, value)

    def get_confidence_weights(self):
        return {
            "id_number": 0.35,
            "name_on_id": 0.25,
            "relation_name": 0.15,
            "address_on_id": 0.15,
            "dob_on_id": 0.10
        }

class DrivingLicenseParser(BaseParser):
    document_type = "Driving License"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        return bool(re.search(r'driving\s?licen[sc]e|transport\s?department|motor\s?vehicles\s?act|dl\s?no|licence\s?no', text, re.IGNORECASE) or 'driving' in hint_text)
        
    def extract_fields(self, text: str):
        fields = {}
        dl_m = re.search(r'(?:DL\s?No|Licence\s?No|License\s?No)[:\s]*([A-Z0-9-]{10,20})', text, re.IGNORECASE)
        id_val = dl_m.group(1).strip().upper() if dl_m else "N/A"
        fields["id_number"] = {"value": id_val, "base_conf": 97 if dl_m else 50}
        
        name_m = re.search(r'(?:name|holder)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
        name_val = name_m.group(1).strip().upper() if name_m else "N/A"
        fields["name_on_id"] = {"value": name_val, "base_conf": 92 if name_m else 50}
        
        dob_val, dob_found = self.find_date(text)
        dob_norm = self.normalize_date(dob_val) if dob_val else "N/A"
        fields["dob_on_id"] = {"value": dob_norm, "base_conf": 94 if dob_found else 50}
        
        exp_m = re.search(r'(?:valid\s?till|expiry|valid\s?upto)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
        exp_val = self.normalize_date(exp_m.group(1)) if exp_m else "N/A"
        fields["validity"] = {"value": exp_val, "base_conf": 92 if exp_m else 50}
        
        addr_m = re.search(r'(?:address)[:\s]+(.+?)(?:\d{6}|$)', text, re.IGNORECASE | re.DOTALL)
        addr_val = addr_m.group(1).strip()[:200] if addr_m else "N/A"
        fields["address_on_id"] = {"value": addr_val, "base_conf": 88 if addr_m else 50}
        
        cat_m = re.search(r'(?:class|vehicle\s?class|category)[:\s]+([A-Z,\s]+)', text, re.IGNORECASE)
        cat_val = cat_m.group(1).strip().upper() if cat_m else "N/A"
        fields["vehicle_category"] = {"value": cat_val, "base_conf": 85 if cat_m else 50}
        
        return fields

    def validate_field(self, field_name: str, value: str) -> bool:
        if field_name == "id_number":
            return len(value) >= 10
        return super().validate_field(field_name, value)

    def get_confidence_weights(self):
        return {
            "id_number": 0.30,
            "name_on_id": 0.25,
            "dob_on_id": 0.15,
            "validity": 0.15,
            "address_on_id": 0.15
        }
