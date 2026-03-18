from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas, database, auth_routes

router = APIRouter(prefix="/partners", tags=["partners"])

@router.post("/", response_model=schemas.Partner)
def create_partner(
    partner: schemas.PartnerCreate, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "partner", action="write"))
):
    db_partner = models.Partner(**partner.dict())
    db.add(db_partner)
    db.commit()
    db.refresh(db_partner)
    return db_partner

@router.get("/", response_model=List[schemas.Partner])
def list_partners(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "partner", action="read"))
):
    return db.query(models.Partner).all()

@router.get("/{partner_id}", response_model=schemas.Partner)
def get_partner(
    partner_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "partner", action="read"))
):
    db_partner = db.query(models.Partner).filter(models.Partner.id == partner_id).first()
    if not db_partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    return db_partner

@router.patch("/{partner_id}", response_model=schemas.Partner)
def update_partner(
    partner_id: str,
    partner_update: schemas.PartnerCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "partner", action="write"))
):
    db_partner = db.query(models.Partner).filter(models.Partner.id == partner_id).first()
    if not db_partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    
    update_data = partner_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_partner, key, value)
    
    db.commit()
    db.refresh(db_partner)
    return db_partner

@router.delete("/{partner_id}")
def delete_partner(
    partner_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "partner", action="delete"))
):
    db_partner = db.query(models.Partner).filter(models.Partner.id == partner_id).first()
    if not db_partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    
    db.delete(db_partner)
    db.commit()
    return {"message": "Partner deleted successfully"}
