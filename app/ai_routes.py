from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from . import models, schemas
from .database import get_async_db
from .auth_routes import check_module_permission

router = APIRouter(
    prefix="/ai",
    tags=["AI"]
)

@router.get("/insights/{case_id}", dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def get_ai_insights(case_id: str, db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.Case).options(selectinload(models.Case.checks)).filter(models.Case.id == case_id)
    res = await db.execute(stmt)
    case_obj = res.scalar_one_or_none()
    
    if not case_obj:
        raise HTTPException(status_code=404, detail="Case not found")
        
    checks = case_obj.checks or []
    discrepancies = [c for c in checks if c.status in ["RED", "INSUFF", "INSUFFICIENT"]]
    wip_checks = [c for c in checks if c.status in ["VERIFICATION", "PENDING", "INTERIM"]]
    completed_checks = [c for c in checks if c.status in ["GREEN", "COMPLETED", "CLEAR"]]
    
    risk_level = "LOW"
    if discrepancies:
        risk_level = "HIGH"
    elif len(wip_checks) > len(completed_checks) or not completed_checks:
        risk_level = "MEDIUM"
        
    summary = f"Neural Engine analysis for Case {case_obj.case_ref_no} complete. Found {len(discrepancies)} non-compliance markers across {len(checks)} parameters."
    
    recommendation = "Manual Audit Recommended"
    if risk_level == "LOW":
        recommendation = "Proceed to Final Dispatch"
    elif risk_level == "HIGH":
        recommendation = "Immediate Compliance Review Mandatory"
        
    return {
        "riskLevel": risk_level,
        "summary": summary,
        "recommendation": recommendation,
        "metrics": {
            "discrepancies": len(discrepancies),
            "pending": len(wip_checks),
            "verified": len(completed_checks)
        }
    }
