from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from . import models, schemas, database, auth_routes
import os
import uuid
import io
from .aws_utils import s3_client, aws_bucket, aws_region
from anyio import to_thread
from datetime import datetime

router = APIRouter(prefix="/customers", tags=["customers"])

@router.post("", response_model=schemas.Customer)
async def create_customer(
    name: str = Form(...),
    city: Optional[str] = Form(None),
    contact_person: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    status: str = Form("ACTIVE"),
    agreement_file: Optional[UploadFile] = File(None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "customer", action="write"))
):
    file_path = None
    if agreement_file and s3_client and aws_bucket:
        file_ext = os.path.splitext(agreement_file.filename)[1]
        file_name = f"bgv_documents/{uuid.uuid4()}{file_ext}"
        file_data = await agreement_file.read()
        
        await to_thread.run_sync(
            s3_client.upload_fileobj,
            io.BytesIO(file_data),
            aws_bucket,
            file_name,
            {'ContentType': agreement_file.content_type}
        )
        file_path = file_name

    db_customer = models.Customer(
        name=name,
        city=city,
        contact_person=contact_person,
        phone=phone,
        email=email,
        address=address,
        status=status,
        customer_agreement=file_path
    )
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer

@router.get("", response_model=List[schemas.Customer])
def list_customers(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "customer", action="read"))
):

    user_role_str = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    role_name = (current_user.role_rel.name.upper() if current_user.role_rel else "").upper()
    is_customer = "CUSTOMER" in user_role_str or "CUSTOMER" in role_name

    if is_customer and current_user.customer_id:
        return db.query(models.Customer).filter(models.Customer.id == current_user.customer_id).all()
    
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
async def update_customer(
    customer_id: str,
    name: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    contact_person: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    agreement_file: Optional[UploadFile] = File(None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.check_module_permission("bms", "customer", action="write"))
):
    db_customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    if name is not None: db_customer.name = name
    if city is not None: db_customer.city = city
    if contact_person is not None: db_customer.contact_person = contact_person
    if phone is not None: db_customer.phone = phone
    if email is not None: db_customer.email = email
    if address is not None: db_customer.address = address
    if status is not None: db_customer.status = status

    if agreement_file and s3_client and aws_bucket:
        file_ext = os.path.splitext(agreement_file.filename)[1]
        file_name = f"bgv_documents/{uuid.uuid4()}{file_ext}"
        file_data = await agreement_file.read()
        
        await to_thread.run_sync(
            s3_client.upload_fileobj,
            io.BytesIO(file_data),
            aws_bucket,
            file_name,
            {'ContentType': agreement_file.content_type}
        )
        db_customer.customer_agreement = file_name
    
    db.commit()
    db.refresh(db_customer)
    return db_customer

@router.post("/{customer_id}/documents", response_model=schemas.Customer)
async def upload_customer_document(
    customer_id: str,
    file: UploadFile = File(...),
    folder: str = "General",
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    # Check if user belongs to this customer or is admin
    if current_user.role != models.UserRole.SUPER_ADMIN and current_user.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="Not authorized to upload for this client")

    db_customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not db_customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    if not s3_client or not aws_bucket:
        raise HTTPException(status_code=500, detail="S3 storage is not configured. Please check your AWS credentials.")

    try:
        file_ext = os.path.splitext(file.filename)[1]
        file_key = f"bgv_documents/{uuid.uuid4()}{file_ext}"
        file_data = await file.read()
        
        await to_thread.run_sync(
            s3_client.upload_fileobj,
            io.BytesIO(file_data),
            aws_bucket,
            file_key,
            {'ContentType': file.content_type}
        )
        file_info = {
            "url": f"https://{aws_bucket}.s3.{aws_region}.amazonaws.com/{file_key}",
            "path": file_key,
            "original_filename": file.filename,
            "uploaded_at": datetime.utcnow().isoformat(),
            "uploaded_by": current_user.full_name,
            "folder": folder
        }
        
        docs = list(db_customer.documents or [])
        docs.append(file_info)
        db_customer.documents = docs
        db.commit()
        db.refresh(db_customer)
        return db_customer

    except Exception as e:
        print(f"S3 Upload Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload to S3: {str(e)}")

from fastapi.responses import RedirectResponse
@router.get("/{customer_id}/agreement")
async def get_customer_agreement(
    customer_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    db_customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not db_customer or not db_customer.customer_agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    
    if s3_client and aws_bucket:
        try:
            url = await to_thread.run_sync(
                s3_client.generate_presigned_url,
                'get_object',
                {'Bucket': aws_bucket, 'Key': db_customer.customer_agreement},
                3600
            )
            return {"url": url}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"S3 Error: {str(e)}")
    
    raise HTTPException(status_code=500, detail="S3 storage not configured")

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
