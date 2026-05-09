from datetime import datetime, timedelta
from sqlalchemy import select
from . import models, enums

async def calculate_case_risk(case: models.Case):
    """
    Heuristic-based risk assessment for SLA breaches.
    Returns (score, factors) where score is 0-100.
    """
    score = 0
    factors = []
    
    if case.status in ['COMPLETED', 'QC_VERIFIED']:
        return 0, {}

    # 1. Time-based risk (SLA is 10 days)
    days_passed = (datetime.utcnow() - case.received_date).days
    if days_passed >= 8:
        score += 60
        factors.append("Approaching Critical SLA (8+ days)")
    elif days_passed >= 5:
        score += 30
        factors.append("Moderate TAT consumption (5+ days)")

    # 2. Insufficiency risk
    if case.insufficiency_count > 1:
        score += 20
        factors.append("Multiple insufficiencies detected")
    elif case.insufficiency_count == 1:
        score += 10
        factors.append("Single insufficiency delay")

    # 3. Check-type complexity (Simulated)
    # Education/Criminal usually take longer
    for check in case.checks:
        if "EDUCATION" in check.check_type.upper():
            score += 5
            factors.append("Complexity: Education verification")
        if "CRIMINAL" in check.check_type.upper():
            score += 10
            factors.append("Complexity: Judicial record check")

    return min(100, score), {"factors": factors, "evaluated_at": datetime.utcnow().isoformat()}

async def update_all_case_risks(db):
    """Batch update risk scores for all active cases."""
    stmt = select(models.Case).filter(models.Case.status.notin_(['COMPLETED', 'QC_VERIFIED']))
    res = await db.execute(stmt)
    cases = res.scalars().all()
    
    for case in cases:
        score, factors = await calculate_case_risk(case)
        case.risk_score = score
        case.risk_factors = factors
        case.last_risk_assessment = datetime.utcnow()
    
    await db.commit()
