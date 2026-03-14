from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas, database, auth_routes

router = APIRouter(prefix="/customers", tags=["customers"])

@router.post("/", response_model=schemas.Customer)
def create_customer(
    customer: schemas.CustomerCreate, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "customer"))
):

    db_customer = models.Customer(**customer.dict())
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer

@router.get("/", response_model=List[schemas.Customer])
def list_customers(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "customer"))
):

    return db.query(models.Customer).all()
