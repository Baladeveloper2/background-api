from datetime import datetime, timedelta
from . import enums

# Optimized TAT protocols based on industry standards for each verification vector
TAT_VECTORS = {
    "ADDRESS": 3,
    "EMPLOYMENT": 5,
    "EDUCATION": 4,
    "CRIMINAL": 7,
    "GLOBAL_DATABASE": 2,
    "ID_VERIFICATION": 1,
    "CREDIT": 3,
    "REFERENCE": 4
}

def calculate_predictive_tat(check_types: list[str]) -> int:
    """
    Calculates the maximum expected turnaround time based on the active verification vectors.
    """
    if not check_types:
        return 5 # Default protocol
    
    max_days = 0
    for ct in check_types:
        # Match check type to known vectors (fuzzy match or direct)
        ct_upper = ct.upper()
        days = 5 # Default for unknown vector
        
        for vector, tat in TAT_VECTORS.items():
            if vector in ct_upper:
                days = tat
                break
        
        if days > max_days:
            max_days = days
            
    return max_days

def check_is_at_risk(received_date: datetime, tat_days: int) -> bool:
    """
    Determines if a case is approaching its SLA deadline.
    Flagged as 'At Risk' if >70% of TAT has elapsed.
    """
    if not received_date:
        return False
        
    deadline = received_date + timedelta(days=tat_days)
    now = datetime.now(received_date.tzinfo) if received_date.tzinfo else datetime.now()
    
    total_duration = timedelta(days=tat_days).total_seconds()
    if total_duration <= 0:
        return False
        
    elapsed = (now - received_date).total_seconds()
    usage_ratio = elapsed / total_duration
    
    return usage_ratio > 0.7
