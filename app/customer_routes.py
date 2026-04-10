from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas, database, auth_routes

router = APIRouter(prefix="/customers", tags=["customers"])

@router.post("", response_model=schemas.Customer)
def create_customer(
    customer: schemas.CustomerCreate, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "customer", action="write"))
):

    db_customer = models.Customer(**customer.dict())
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer

@router.get("", response_model=List[schemas.Customer])
def list_customers(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "customer", action="read"))
):

    return db.query(models.Customer).all()

@router.get("/{customer_id}", response_model=schemas.Customer)
def get_customer(
    customer_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "customer", action="read"))
):
    db_customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return db_customer

@router.patch("/{customer_id}", response_model=schemas.Customer)
def update_customer(
    customer_id: str,
    customer_update: schemas.CustomerCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "customer", action="write"))
):
    db_customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    update_data = customer_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_customer, key, value)
    
    db.commit()
    db.refresh(db_customer)
    return db_customer

@router.delete("/{customer_id}")
def delete_customer(
    customer_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "customer", action="delete"))
):
    db_customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    db.delete(db_customer)
    db.commit()
    return {"message": "Customer deleted successfully"}
