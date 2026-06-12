import re
from .base import BaseParser

class EducationParser(BaseParser):
    document_type = "Degree Certificate"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        return bool(re.search(r'degree\s?certificate|bachelor|master|convocation|awarded.*degree|marksheet|mark\s?sheet|statement\s?of\s?marks|school\s?leaving|transfer\s?certificate|provisional\s?certificate', text, re.IGNORECASE) or 'degree' in hint_text or 'marksheet' in hint_text)
        
    def extract_fields(self, text: str):
        fields = {}
        univ_m = re.search(r'([A-Za-z\s]+ (?:University|College|Institute|Academy|School|Board))', text, re.IGNORECASE)
        univ_val = univ_m.group(1).strip().upper() if univ_m else "N/A"
        fields["institution"] = {"value": univ_val, "base_conf": 93 if univ_m else 60}
        
        deg_m = re.search(r'(?:degree|awarded|course|program|qualification)[:\s]+([A-Za-z\.\s]+)', text, re.IGNORECASE)
        deg_val = deg_m.group(1).strip().upper() if deg_m else "N/A"
        fields["qualification"] = {"value": deg_val, "base_conf": 90 if deg_m else 60}
        
        reg_m = re.search(r'(?:reg\s?no|register\s?number|roll\s?no|enrollment)[:\s]+([A-Za-z0-9]+)', text, re.IGNORECASE)
        reg_val = reg_m.group(1) if reg_m else "N/A"
        fields["registration_number"] = {"value": reg_val, "base_conf": 94 if reg_m else 55}
        
        year_m = re.search(r'(?:passing\s?year|year\s?of\s?passing|passed\s?in|batch)[:\s]+(\d{4})', text, re.IGNORECASE)
        year_val = year_m.group(1) if year_m else "N/A"
        fields["year_of_passing"] = {"value": year_val, "base_conf": 95 if year_m else 55}
        
        pct_m = re.search(r'(?:percentage|cgpa|gpa|grade|marks\s?obtained)[:\s]+([0-9\.]+\s?[%/]?\s?[\d\.]*)', text, re.IGNORECASE)
        pct_val = pct_m.group(1).strip() if pct_m else "N/A"
        fields["percentage_cgpa"] = {"value": pct_val, "base_conf": 91 if pct_m else 55}
        
        name_m = re.search(r'(?:this\s?is\s?to\s?certify\s?that|awarded\s?to|name)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
        name_val = name_m.group(1).strip().upper() if name_m else "N/A"
        fields["student_name"] = {"value": name_val, "base_conf": 90 if name_m else 55}
        return fields

    def get_confidence_weights(self):
        return {
            "institution": 0.25,
            "student_name": 0.25,
            "registration_number": 0.20,
            "year_of_passing": 0.15,
            "percentage_cgpa": 0.15
        }

class EmploymentParser(BaseParser):
    document_type = "Employment Document"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        return bool(re.search(r'experience\s?letter|relieving\s?letter|offer\s?letter|appointment\s?letter|payslip|salary\s?slip', text, re.IGNORECASE) or 'experience' in hint_text or 'salary' in hint_text or 'offer' in hint_text)
        
    def extract_fields(self, text: str):
        fields = {}
        emp_m = re.search(r'([A-Za-z0-9\s]+(?:Pvt|Ltd|Limited|Solutions|Corp|Technologies|Services|Pvt\.\s?Ltd))', text, re.IGNORECASE)
        emp_val = emp_m.group(1).strip().upper() if emp_m else "N/A"
        fields["employer_name"] = {"value": emp_val, "base_conf": 92 if emp_m else 60}
        
        name_m = re.search(r'(?:this\s?is\s?to\s?certify\s?that|mr\.|ms\.|mrs\.)\s*([A-Za-z\s]+)', text, re.IGNORECASE)
        name_val = name_m.group(1).strip().upper() if name_m else "N/A"
        fields["employee_name"] = {"value": name_val, "base_conf": 90 if name_m else 55}
        
        des_m = re.search(r'(?:designation|position|role)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
        des_val = des_m.group(1).strip().upper() if des_m else "N/A"
        fields["designation"] = {"value": des_val, "base_conf": 88 if des_m else 55}
        
        id_m = re.search(r'(?:emp\s?id|employee\s?code|emp\s?no|staff\s?id)[:\s]+([A-Za-z0-9-]+)', text, re.IGNORECASE)
        id_val = id_m.group(1) if id_m else "N/A"
        fields["employee_id"] = {"value": id_val, "base_conf": 94 if id_m else 55}
        
        doj_m = re.search(r'(?:doj|date\s?of\s?joining|joined\s?since|joined)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
        doj_val = self.normalize_date(doj_m.group(1)) if doj_m else "N/A"
        fields["joining_date"] = {"value": doj_val, "base_conf": 92 if doj_m else 50}
        
        dol_m = re.search(r'(?:relieved|last\s?working\s?day|date\s?of\s?leaving|resigned)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
        dol_val = self.normalize_date(dol_m.group(1)) if dol_m else "N/A"
        fields["relieving_date"] = {"value": dol_val, "base_conf": 92 if dol_m else 50}
        
        month_m = re.search(r'(?:salary\s?for|month\s?of|pay\s?period)[:\s]+([A-Za-z]+\s?\d{4})', text, re.IGNORECASE)
        month_val = month_m.group(1).strip().upper() if month_m else "N/A"
        fields["salary_month"] = {"value": month_val, "base_conf": 88 if month_m else 50}
        
        gross_m = re.search(r'(?:gross\s?salary|total\s?earnings|gross\s?pay)[:\s]+(?:Rs\.?|₹)?\s*([\d,]+)', text, re.IGNORECASE)
        gross_val = gross_m.group(1).replace(",", "") if gross_m else "N/A"
        fields["gross_salary"] = {"value": gross_val, "base_conf": 93 if gross_m else 55}
        
        net_m = re.search(r'(?:net\s?salary|net\s?pay|take\s?home)[:\s]+(?:Rs\.?|₹)?\s*([\d,]+)', text, re.IGNORECASE)
        net_val = net_m.group(1).replace(",", "") if net_m else "N/A"
        fields["net_salary"] = {"value": net_val, "base_conf": 95 if net_m else 55}
        
        return fields

    def get_confidence_weights(self):
        return {
            "employer_name": 0.30,
            "employee_name": 0.25,
            "designation": 0.15,
            "joining_date": 0.15,
            "gross_salary": 0.15
        }

class BankStatementParser(BaseParser):
    document_type = "Bank Statement"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        return bool(re.search(r'bank\s?statement|statement\s?of\s?account|account\s?summary|transaction\s?history', text, re.IGNORECASE) or 'bank' in hint_text)
        
    def extract_fields(self, text: str):
        fields = {}
        acc_m = re.search(r'(?:account\s?no|a/c\s?no|account\s?number)[:\s]+([0-9X-]{9,18})', text, re.IGNORECASE)
        acc_val = acc_m.group(1) if acc_m else "N/A"
        fields["account_number"] = {"value": acc_val, "base_conf": 96 if acc_m else 55}
        
        name_m = re.search(r'(?:account\s?holder|customer\s?name|name)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
        name_val = name_m.group(1).strip().upper() if name_m else "N/A"
        fields["account_holder"] = {"value": name_val, "base_conf": 90 if name_m else 55}
        
        bank_m = re.search(r'(?:bank\s?name|bank)[:\s]+([A-Za-z\s]+ Bank)', text, re.IGNORECASE)
        bank_val = bank_m.group(1).strip().upper() if bank_m else "N/A"
        fields["bank_name"] = {"value": bank_val, "base_conf": 92 if bank_m else 55}
        
        ifsc_m = re.search(r'(?:IFSC)[:\s]+([A-Z]{4}0[A-Z0-9]{6})', text, re.IGNORECASE)
        ifsc_val = ifsc_m.group(1).upper() if ifsc_m else "N/A"
        fields["ifsc_code"] = {"value": ifsc_val, "base_conf": 97 if ifsc_m else 50}
        return fields

    def get_confidence_weights(self):
        return {
            "account_number": 0.30,
            "account_holder": 0.25,
            "bank_name": 0.15,
            "ifsc_code": 0.15,
            "statement_from": 0.075,
            "statement_to": 0.075
        }

class AddressBillParser(BaseParser):
    document_type = "Address Bill"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        return bool(re.search(r'electricity\s?bill|power\s?bill|gas\s?bill|water\s?bill|telephone\s?bill|broadband', text, re.IGNORECASE) or 'electric' in hint_text or 'gas' in hint_text or 'water' in hint_text)
        
    def extract_fields(self, text: str):
        fields = {}
        name_m = re.search(r'(?:consumer\s?name|customer\s?name|subscriber)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
        name_val = name_m.group(1).strip().upper() if name_m else "N/A"
        fields["account_holder"] = {"value": name_val, "base_conf": 90 if name_m else 55}
        
        acc_m = re.search(r'(?:consumer\s?no|account\s?no|ca\s?no|customer\s?id|subscriber\s?id)[:\s]+([A-Za-z0-9-]+)', text, re.IGNORECASE)
        acc_val = acc_m.group(1) if acc_m else "N/A"
        fields["account_number"] = {"value": acc_val, "base_conf": 93 if acc_m else 55}
        
        addr_m = re.search(r'(?:service\s?address|premises\s?address|installation\s?address|address)[:\s]+(.+?)(?:\d{6}|Rs\.|₹|$)', text, re.IGNORECASE | re.DOTALL)
        addr_val = addr_m.group(1).strip()[:250] if addr_m else "N/A"
        fields["address"] = {"value": addr_val, "base_conf": 88 if addr_m else 50}
        
        pin_m = re.search(r'\b(\d{6})\b', text)
        pin_val = pin_m.group(1) if pin_m else "N/A"
        fields["pincode"] = {"value": pin_val, "base_conf": 92 if pin_m else 50}
        
        date_m = re.search(r'(?:bill\s?date|billing\s?date|statement\s?date)[:\s]+(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
        date_val = self.normalize_date(date_m.group(1)) if date_m else "N/A"
        fields["bill_date"] = {"value": date_val, "base_conf": 90 if date_m else 50}
        
        return fields

    def get_confidence_weights(self):
        return {
            "account_holder": 0.25,
            "account_number": 0.25,
            "address": 0.30,
            "pincode": 0.10,
            "bill_date": 0.10
        }

class SalarySlipParser(BaseParser):
    document_type = "Salary Slip"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        return bool(re.search(r'payslip|salary\s?slip|pay\s?stub', text, re.IGNORECASE) or 'salary' in hint_text)
        
    def extract_fields(self, text: str):
        fields = {}
        # Simple stubs for new parsers
        fields["employer_name"] = {"value": "N/A", "base_conf": 50}
        fields["employee_name"] = {"value": "N/A", "base_conf": 50}
        fields["net_salary"] = {"value": "N/A", "base_conf": 50}
        return fields

class ExperienceLetterParser(BaseParser):
    document_type = "Experience Letter"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        return bool(re.search(r'experience\s?letter|relieving\s?letter|service\s?certificate', text, re.IGNORECASE) or 'experience' in hint_text)
        
    def extract_fields(self, text: str):
        fields = {}
        fields["employer_name"] = {"value": "N/A", "base_conf": 50}
        fields["employee_name"] = {"value": "N/A", "base_conf": 50}
        fields["duration"] = {"value": "N/A", "base_conf": 50}
        return fields

class ReferenceLetterParser(BaseParser):
    document_type = "Reference Letter"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        return bool(re.search(r'reference\s?letter|letter\s?of\s?recommendation', text, re.IGNORECASE) or 'reference' in hint_text)
        
    def extract_fields(self, text: str):
        fields = {}
        fields["referee_name"] = {"value": "N/A", "base_conf": 50}
        fields["applicant_name"] = {"value": "N/A", "base_conf": 50}
        return fields

class MarksheetParser(BaseParser):
    document_type = "Marksheet"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        return bool(re.search(r'marksheet|mark\s?sheet|statement\s?of\s?marks', text, re.IGNORECASE) or 'marksheet' in hint_text)
        
    def extract_fields(self, text: str):
        fields = {}
        fields["student_name"] = {"value": "N/A", "base_conf": 50}
        fields["total_marks"] = {"value": "N/A", "base_conf": 50}
        return fields

class DrugTestParser(BaseParser):
    document_type = "Drug Test Certificate"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        return bool(re.search(r'drug\s?test|toxicology|substance\s?abuse|urine\s?analysis', text, re.IGNORECASE) or 'drug' in hint_text)
        
    def extract_fields(self, text: str):
        fields = {}
        fields["patient_name"] = {"value": "N/A", "base_conf": 50}
        fields["result"] = {"value": "N/A", "base_conf": 50}
        return fields

class PoliceVerificationParser(BaseParser):
    document_type = "Police Verification"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        return bool(re.search(r'police\s?verification|criminal\s?record|clearance\s?certificate', text, re.IGNORECASE) or 'police' in hint_text)
        
    def extract_fields(self, text: str):
        fields = {}
        fields["applicant_name"] = {"value": "N/A", "base_conf": 50}
        fields["clearance_status"] = {"value": "N/A", "base_conf": 50}
        return fields

class DefaultParser(BaseParser):
    document_type = "Unknown Document"
    
    def can_parse(self, text: str, hint_text: str = "") -> bool:
        return True # Catch-all
        
    def extract_fields(self, text: str):
        fields = {}
        email_m = re.search(r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b', text)
        email_val = email_m.group(1) if email_m else "N/A"
        fields["email"] = {"value": email_val, "base_conf": 85 if email_m else 45}
        
        mob_m = re.search(r'\b[6-9]\d{9}\b', text)
        mob_val = mob_m.group() if mob_m else "N/A"
        fields["mobile"] = {"value": mob_val, "base_conf": 85 if mob_m else 45}
        
        dob_val, dob_found = self.find_date(text)
        dob_norm = self.normalize_date(dob_val) if dob_val else "N/A"
        fields["detected_date"] = {"value": dob_norm, "base_conf": 75 if dob_found else 45}
        
        fields["raw_text_preview"] = {"value": text[:300] + ("..." if len(text) > 300 else ""), "base_conf": 40}
        return fields
