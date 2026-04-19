from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import traceback
from . import models, schemas, auth, database
from .auth_routes import get_current_user, check_module_permission

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
        if res.scalar_one_or_none():
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
            bvs_permissions=user.bvs_permissions or {}
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        return db_user
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=List[schemas.User])
async def read_users(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(database.get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    res = await db.execute(select(models.User).offset(skip).limit(limit))
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
    
    await db.delete(db_user)
    await db.commit()
    return None
