from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas
from .database import get_db
from .auth_routes import get_current_user, check_permissions

router = APIRouter(
    tags=["rbac"]
)

# Roles API
@router.post("/roles", response_model=schemas.Role, dependencies=[Depends(check_permissions(models.UserRole.ADMIN))])
def create_role(role: schemas.RoleCreate, db: Session = Depends(get_db)):
    db_role = db.query(models.Role).filter(models.Role.name == role.name).first()
    if db_role:
        raise HTTPException(status_code=400, detail="Role name already exists")
    db_role = models.Role(**role.dict())
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role

@router.get("/roles", response_model=List[schemas.Role], dependencies=[Depends(check_permissions(models.UserRole.ADMIN))])
def read_roles(db: Session = Depends(get_db)):
    return db.query(models.Role).all()

@router.patch("/roles/{role_id}", response_model=schemas.Role, dependencies=[Depends(check_permissions(models.UserRole.ADMIN))])
def update_role(role_id: str, role_update: schemas.RoleBase, db: Session = Depends(get_db)):
    db_role = db.query(models.Role).filter(models.Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    update_data = role_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_role, key, value)
    
    db.commit()
    db.refresh(db_role)
    return db_role

@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(check_permissions(models.UserRole.ADMIN))])
def delete_role(role_id: str, db: Session = Depends(get_db)):
    db_role = db.query(models.Role).filter(models.Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    db.delete(db_role)
    db.commit()
    return None

# Modules API
@router.post("/modules", response_model=schemas.Module, dependencies=[Depends(check_permissions(models.UserRole.ADMIN))])
def create_module(module: schemas.ModuleCreate, db: Session = Depends(get_db)):
    db_module = db.query(models.Module).filter(models.Module.code == module.code).first()
    if db_module:
        raise HTTPException(status_code=400, detail="Module code already exists")
    db_module = models.Module(**module.dict())
    db.add(db_module)
    db.commit()
    db.refresh(db_module)
    return db_module

@router.get("/modules", response_model=List[schemas.Module], dependencies=[Depends(check_permissions(models.UserRole.ADMIN))])
def read_modules(db: Session = Depends(get_db)):
    return db.query(models.Module).all()

@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(check_permissions(models.UserRole.ADMIN))])
def delete_module(module_id: str, db: Session = Depends(get_db)):
    db_module = db.query(models.Module).filter(models.Module.id == module_id).first()
    if not db_module:
        raise HTTPException(status_code=404, detail="Module not found")
    db.delete(db_module)
    db.commit()
    return None
