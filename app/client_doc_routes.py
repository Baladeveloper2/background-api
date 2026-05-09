from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, case
from typing import List, Optional
import os
import uuid
from datetime import datetime
from . import models, schemas, database, auth_routes, aws_utils, notification_utils
from .database import get_async_db
from .auth_routes import get_current_user

router = APIRouter(prefix="/client-documents", tags=["client-documents"])

@router.get("/summary")
async def get_document_summary(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    # Check if admin
    user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    role_name = (current_user.role_rel.name.upper() if current_user.role_rel else "").upper()
    is_admin = user_role in ["SUPER_ADMIN", "ADMIN"] or "SUPER ADMIN" in role_name
    
    if not is_admin:
        raise HTTPException(403, detail="Admin access required")

    # Get all customers, include those without documents
    stmt = select(
        models.Customer.id,
        models.Customer.name,
        func.count(models.ClientDocument.id).label("total_docs"),
        func.sum(case((and_(models.ClientDocument.is_read == False, models.ClientDocument.is_folder == False), 1), else_=0)).label("unread_docs"),
        func.max(models.ClientDocument.created_at).label("latest_upload")
    ).outerjoin(models.ClientDocument, models.Customer.id == models.ClientDocument.customer_id) \
     .group_by(models.Customer.id, models.Customer.name)
    
    res = await db.execute(stmt)
    return [dict(r._mapping) for r in res]

@router.post("/upload")
async def upload_client_document(
    name: str = Form(...),
    is_folder: bool = Form(False),
    parent_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    if not current_user.customer_id:
        raise HTTPException(403, detail="Only client users can upload documents")

    file_path = None
    file_type = None
    
    if not is_folder and file:
        file_ext = os.path.splitext(file.filename)[1]
        file_path = f"client_docs/{current_user.customer_id}/{uuid.uuid4()}{file_ext}"
        await aws_utils.upload_to_s3(file, file_path)
        file_type = file.content_type

    new_doc = models.ClientDocument(
        customer_id=current_user.customer_id,
        name=name,
        is_folder=is_folder,
        parent_id=parent_id,
        file_path=file_path,
        file_type=file_type,
        uploaded_by=current_user.id
    )
    
    db.add(new_doc)
    await db.commit()
    await db.refresh(new_doc)
    
    if not is_folder:
        try:
            # Try to get customer name
            customer_name = "Unknown Client"
            if current_user.customer:
                customer_name = current_user.customer.name
            elif current_user.customer_id:
                # Fetch customer if not loaded
                c_res = await db.execute(select(models.Customer).filter_by(id=current_user.customer_id))
                customer = c_res.scalar_one_or_none()
                if customer:
                    customer_name = customer.name

            await notification_utils.notify_client_document_uploaded(
                db=db,
                document_name=name,
                customer_id=current_user.customer_id,
                customer_name=customer_name,
                background_tasks=background_tasks
            )
        except Exception as e:
            import logging
            logging.error(f"Error sending upload notification: {str(e)}")
            
    return new_doc

@router.get("")
async def list_client_documents(
    parent_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    # If customer, can only see their own
    active_customer_id = current_user.customer_id
    
    # If admin, can specify customer_id
    user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    role_name = (current_user.role_rel.name.upper() if current_user.role_rel else "").upper()
    is_admin = user_role in ["SUPER_ADMIN", "ADMIN"] or "SUPER ADMIN" in role_name
    
    if is_admin and customer_id:
        active_customer_id = customer_id
    
    if not active_customer_id:
        raise HTTPException(403, detail="Access denied")

    stmt = select(models.ClientDocument).filter(models.ClientDocument.customer_id == active_customer_id)
    if parent_id:
        stmt = stmt.filter(models.ClientDocument.parent_id == parent_id)
    else:
        stmt = stmt.filter(models.ClientDocument.parent_id.is_(None))
    
    res = await db.execute(stmt)
    docs = res.scalars().all()
    
    results = []
    for doc in docs:
        d = {
            "id": doc.id,
            "name": doc.name,
            "is_folder": doc.is_folder,
            "parent_id": doc.parent_id,
            "file_path": doc.file_path,
            "file_type": doc.file_type,
            "uploaded_by": doc.uploaded_by,
            "created_at": doc.created_at,
            "is_read": doc.is_read
        }
        if doc.is_folder:
            c_stmt = select(func.count(models.ClientDocument.id)).filter(models.ClientDocument.parent_id == doc.id)
            c_res = await db.execute(c_stmt)
            d["asset_count"] = c_res.scalar()
        results.append(d)
        
    return results

@router.get("/folders")
async def list_folders(
    customer_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    active_customer_id = current_user.customer_id
    
    user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    role_name = (current_user.role_rel.name.upper() if current_user.role_rel else "").upper()
    is_admin = user_role in ["SUPER_ADMIN", "ADMIN"] or "SUPER ADMIN" in role_name
    
    if is_admin and customer_id:
        active_customer_id = customer_id
        
    if not active_customer_id:
        return []

    stmt = select(models.ClientDocument).filter(
        models.ClientDocument.customer_id == active_customer_id,
        models.ClientDocument.is_folder == True
    )
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/download/{doc_id}")
async def download_document(
    doc_id: str,
    as_attachment: bool = False,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    stmt = select(models.ClientDocument).filter(models.ClientDocument.id == doc_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    
    if not doc or doc.is_folder:
        raise HTTPException(404, detail="Document not found")
    
    # Check access
    user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
    role_name = (current_user.role_rel.name.upper() if current_user.role_rel else "").upper()
    is_admin = user_role in ["SUPER_ADMIN", "ADMIN"] or "SUPER ADMIN" in role_name
    
    if not is_admin and doc.customer_id != current_user.customer_id:
        raise HTTPException(403, detail="Access denied")
    
    url = await aws_utils.generate_presigned_url(doc.file_path, as_attachment=as_attachment, filename=doc.name)
    
    # Mark as read if not already
    if not doc.is_read:
        doc.is_read = True
        doc.read_at = datetime.utcnow()
        doc.read_by = current_user.id
        await db.commit()
        
    return {"url": url}

@router.post("/{doc_id}/toggle-read")
async def toggle_document_read(
    doc_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    stmt = select(models.ClientDocument).filter(models.ClientDocument.id == doc_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(404, detail="Document not found")
        
    doc.is_read = not doc.is_read
    if doc.is_read:
        doc.read_at = datetime.utcnow()
        doc.read_by = current_user.id
    else:
        doc.read_at = None
        doc.read_by = None
        
    await db.commit()
    return {"id": doc.id, "is_read": doc.is_read}

@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    stmt = select(models.ClientDocument).filter(models.ClientDocument.id == doc_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(404, detail="Document not found")
        
    if doc.customer_id != current_user.customer_id:
        # maybe allow admin too
        user_role = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
        role_name = (current_user.role_rel.name.upper() if current_user.role_rel else "").upper()
        is_admin = user_role in ["SUPER_ADMIN", "ADMIN"] or "SUPER ADMIN" in role_name
        if not is_admin:
            raise HTTPException(403, detail="Access denied")

    # If folder, check if empty or delete recursively (simplified: just delete record for now)
    await db.delete(doc)
    await db.commit()
    return {"status": "deleted"}
