from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from .logging_config import logger
from . import models, schemas, auth, database
from .auth_routes import get_current_user, check_module_permission, invalidate_user_cache_by_user_id
from .visibility import get_tenant_filters

router = APIRouter(
    prefix="/users",
    tags=["users"]
)

@router.post("", response_model=schemas.User)
async def create_user(
    user: schemas.UserCreate, 
    db: AsyncSession = Depends(database.get_async_db),
    current_user: models.User = Depends(check_module_permission("bms", "applicants", "write"))
):
    try:
        # Check if email exists
        res = await db.execute(select(models.User).filter(models.User.email == user.email))
        existing_user = res.scalar_one_or_none()
        if existing_user:
            if getattr(existing_user, "status", None) in ["INACTIVE", "DELETED"]:
                import time
                existing_user.email = f"{int(time.time())}_del_{existing_user.email[:200]}"
                db.add(existing_user)
                await db.flush()
            else:
                raise HTTPException(status_code=400, detail="Email already registered")
        
        hashed_password = auth.get_password_hash(user.password)
        db_user = models.User(
            email=user.email,
            hashed_password=hashed_password,
            full_name=user.full_name,
            role=user.role,
            role_id=user.role_id,
            status=user.status,
            territory=user.territory,
            business_unit=user.business_unit,
            customer_id=user.customer_id,
            zone_id=user.zone_id,
            branch_id=user.branch_id,
            bvs_permissions=user.bvs_permissions or {}
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        return db_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

from typing import List, Optional

@router.get("", response_model=List[schemas.User])
async def read_users(
    skip: int = 0, 
    limit: int = 100, 
    customer_id: Optional[str] = None,
    db: AsyncSession = Depends(database.get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    query = select(models.User).order_by(models.User.created_at.desc())
    
    if customer_id:
        query = query.filter(models.User.customer_id == customer_id)

    
    # Enforce Hierarchy Scoping
    tenant_filter = get_tenant_filters(current_user, models.User)
    if tenant_filter is not None:
        if tenant_filter is False:
            return []
        elif tenant_filter is not True:
            query = query.filter(tenant_filter)
        
    stmt = query.offset(skip).limit(limit)
    res = await db.execute(stmt)
    users = res.scalars().all()
    return users

@router.get("/{user_id}", response_model=schemas.User)
async def read_user(
    user_id: str, 
    db: AsyncSession = Depends(database.get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    res = await db.execute(select(models.User).filter(models.User.id == user_id))
    db_user = res.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@router.patch("/me/theme", response_model=schemas.User)
async def update_my_theme(
    theme_update: dict,
    db: AsyncSession = Depends(database.get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    if "theme_preference" not in theme_update:
        raise HTTPException(status_code=400, detail="Missing theme_preference")
        
    current_user.theme_preference = theme_update["theme_preference"]
    await db.commit()
    await db.refresh(current_user)
    invalidate_user_cache_by_user_id(current_user.id)
    return current_user

@router.patch("/{user_id}", response_model=schemas.User)
async def update_user(
    user_id: str, 
    user_update: schemas.UserUpdate, 
    db: AsyncSession = Depends(database.get_async_db),
    current_user: models.User = Depends(check_module_permission("bms", "applicants", "write"))
):
    res = await db.execute(select(models.User).filter(models.User.id == user_id))
    db_user = res.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_update.model_dump(exclude_unset=True)
    if 'password' in update_data and update_data['password']:
        db_user.hashed_password = auth.get_password_hash(update_data.pop('password'))
    
    for key, value in update_data.items():
        setattr(db_user, key, value)
    
    await db.commit()
    await db.refresh(db_user)
    invalidate_user_cache_by_user_id(db_user.id)
    return db_user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str, 
    db: AsyncSession = Depends(database.get_async_db),
    current_user: models.User = Depends(check_module_permission("bms", "applicants", "write"))
):
    res = await db.execute(select(models.User).filter(models.User.id == user_id))
    db_user = res.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    from sqlalchemy import delete, update
    
    try:
        # 1. Clean up dependent transaction logs and audit entries
        await db.execute(delete(models.AuditLog).filter(models.AuditLog.user_id == user_id))
        await db.execute(delete(models.Notification).filter(models.Notification.user_id == user_id))
        await db.execute(delete(models.CaseComment).filter(models.CaseComment.user_id == user_id))
        await db.execute(delete(models.RevokeLog).filter(models.RevokeLog.user_id == user_id))
        await db.execute(delete(models.InsufficiencyLog).filter(models.InsufficiencyLog.user_id == user_id))
        await db.execute(delete(models.VerificationLog).filter(models.VerificationLog.performed_by_id == user_id))
        await db.execute(delete(models.QCFieldIssue).filter((models.QCFieldIssue.raised_by == user_id) | (models.QCFieldIssue.assigned_to == user_id)))
        await db.execute(delete(models.VerificationDocument).filter(models.VerificationDocument.uploaded_by_id == user_id))
        await db.execute(delete(models.ClientDocument).filter((models.ClientDocument.uploaded_by == user_id) | (models.ClientDocument.read_by == user_id)))
        await db.execute(delete(models.Insufficiency).filter((models.Insufficiency.raised_by == user_id) | (models.Insufficiency.updated_by == user_id) | (models.Insufficiency.resolved_by == user_id)))
        
        # 2. Reset nullable user associations in Case/Check status entities
        await db.execute(update(models.VerificationCheck).filter(models.VerificationCheck.assigned_verifier_id == user_id).values(assigned_verifier_id=None))
        await db.execute(update(models.VerificationCheck).filter(models.VerificationCheck.finalized_by == user_id).values(finalized_by=None))
        await db.execute(update(models.Case).filter(models.Case.assigned_to == user_id).values(assigned_to=None))
        await db.execute(update(models.Case).filter(models.Case.finalized_by == user_id).values(finalized_by=None))
        await db.execute(update(models.DocumentMetadata).filter(models.DocumentMetadata.uploader_id == user_id).values(uploader_id=None))
        
        # 3. Perform primary row deletion
        await db.delete(db_user)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Integrity error during deletion of user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user due to database constraint dependencies: {str(e)}"
        )
        
    return None
