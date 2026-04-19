from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import json
from typing import List
from . import models, schemas, auth_routes
from .database import get_db_sync as get_db

router = APIRouter(
    prefix="/candidates",
    tags=["candidates"]
)

@router.post("", response_model=schemas.Candidate, dependencies=[Depends(auth_routes.check_module_permission("recruit", "management", action="write"))])
def create_candidate(candidate: schemas.CandidateCreate, db: Session = Depends(get_db)):
    db_candidate = models.Candidate(**candidate.dict())
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    return db_candidate

@router.get("", response_model=List[schemas.Candidate], dependencies=[Depends(auth_routes.check_module_permission("recruit", "management", action="read"))])
def read_candidates(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Candidate).offset(skip).limit(limit).all()

@router.get("/{candidate_id}", response_model=schemas.Candidate, dependencies=[Depends(auth_routes.check_module_permission("recruit", "management", action="read"))])
def read_candidate(candidate_id: str, db: Session = Depends(get_db)):
    db_candidate = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    if db_candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return db_candidate

async def check_candidate_update_access(current_user: models.User = Depends(auth_routes.get_current_user)):
    if current_user.role == models.UserRole.SUPER_ADMIN:
        return current_user
    
    # Check for either recruitment management or BVS verification write access
    perms = current_user.bvs_permissions or {}
    if isinstance(perms, str):
        try: perms = json.loads(perms)
        except: perms = {}
        
    role_perms = current_user.role_rel.permissions if current_user.role_rel else {}
    if isinstance(role_perms, str):
        try: role_perms = json.loads(role_perms)
        except: role_perms = {}
    
    # Role-based systemic access (matching auth_routes oversight logic)
    oversight_roles = [models.UserRole.QA, models.UserRole.QC, models.UserRole.MANAGER, models.UserRole.ADMIN]
    if current_user.role in oversight_roles: return current_user
    if current_user.role_rel and current_user.role_rel.name in ["Super Admin", "QC Verifier", "Verifier"]: return current_user

    # Granular permission check
    def has_write(p_obj, key):
        val = p_obj.get(key)
        if val is True: return True
        if isinstance(val, dict) and val.get("write"): return True
        if isinstance(val, str) and "W" in val.upper(): return True
        return False

    # Check Recruit Module or BVS Module
    if has_write(perms, "recruit") or has_write(role_perms, "recruit.management"): return current_user
    if has_write(perms, "bvs") or has_write(role_perms, "bvs.verification"): return current_user
    
    raise HTTPException(status_code=403, detail="Insufficient permissions to update candidate record")

@router.patch("/{candidate_id}", response_model=schemas.Candidate, dependencies=[Depends(check_candidate_update_access)])
def update_candidate(candidate_id: str, candidate_update: schemas.CandidateUpdate, db: Session = Depends(get_db)):
    db_candidate = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    if db_candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    update_data = candidate_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_candidate, key, value)
    
    db.commit()
    db.refresh(db_candidate)
    return db_candidate

@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(auth_routes.check_module_permission("recruit", "management", action="delete"))])
def delete_candidate(candidate_id: str, db: Session = Depends(get_db)):
    db_candidate = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    if db_candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    db.delete(db_candidate)
    db.commit()
    return None
