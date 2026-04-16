from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import timedelta
from jose import JWTError, jwt
from . import models, schemas, auth, database
from slowapi import Limiter
from slowapi.util import get_remote_address
import re

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(database.get_async_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email: str = payload.get("sub")
        if email is None: raise credentials_exception
        token_data = schemas.TokenData(email=email)
    except JWTError: raise credentials_exception
    except Exception: raise credentials_exception

    stmt = select(models.User).options(selectinload(models.User.role_rel)).filter(models.User.email == token_data.email)
    res = await db.execute(stmt)
    user = res.unique().scalar_one_or_none()
    if user is None: raise credentials_exception
    return user

def check_permissions(role: models.UserRole):
    async def role_checker(current_user: models.User = Depends(get_current_user)):
        user_role_str = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
        target_role_str = str(role.value if hasattr(role, 'value') else role).upper()
        if user_role_str == target_role_str or user_role_str == "SUPER_ADMIN": return current_user
        raise HTTPException(status_code=403, detail="Insufficient privileges")
    return role_checker

def check_module_permission(module: str, sub_module: str = None, action: str = "read"):
    async def permission_checker(current_user: models.User = Depends(get_current_user)):
        if current_user.role == models.UserRole.SUPER_ADMIN: return current_user
        
        # Simplified permission check for async (can be expanded later)
        # Assuming permissions are in current_user.bvs_permissions or role_rel
        has_access = False
        perms = current_user.bvs_permissions or {}
        
        # Logic matches previous sync version but async compatible
        if sub_module:
            if perms.get(module, {}).get(sub_module): has_access = True
            if current_user.role_rel and current_user.role_rel.permissions:
                rk = f"{module}.{sub_module}"
                rp = current_user.role_rel.permissions.get(rk)
                if isinstance(rp, dict) and rp.get(action): has_access = True
                elif rp is True and action == "read": has_access = True
        else:
            if any((perms.get(module, {})).values()): has_access = True
            if current_user.role_rel and current_user.role_rel.permissions:
                rp = current_user.role_rel.permissions.get(module)
                if isinstance(rp, dict) and rp.get(action): has_access = True
                elif rp is True and action == "read": has_access = True

        if not has_access:
            # Grant systemic write access to specific oversight roles for the verification module
            oversight_roles = [models.UserRole.QA, models.UserRole.QC, models.UserRole.MANAGER, models.UserRole.ADMIN]
            if module == "bvs" and current_user.role in oversight_roles:
                return current_user
            raise HTTPException(status_code=403, detail=f"No {action} access to {module}")
        return current_user
    return permission_checker

@router.post("/login", response_model=schemas.Token)
@limiter.limit("5/minute")
async def login_for_access_token(request: Request, db: AsyncSession = Depends(database.get_async_db), form_data: OAuth2PasswordRequestForm = Depends()):
    stmt = select(models.User).options(selectinload(models.User.role_rel)).filter(models.User.email == form_data.username)
    res = await db.execute(stmt)
    user = res.unique().scalar_one_or_none()
    
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    perms = (user.role_rel.permissions or {}).copy() if user.role_id and user.role_rel else (user.bvs_permissions or {}).copy()

    token = auth.create_access_token(
        data={"sub": user.email, "id": user.id, "role": user.role, "full_name": user.full_name, "permissions": perms},
        expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": token, "token_type": "bearer"}

@router.post("/register", response_model=schemas.User)
async def register_user(user: schemas.UserCreate, db: AsyncSession = Depends(database.get_async_db)):
    if len(user.password) < 8: raise HTTPException(400, "Password too short")
    
    res = await db.execute(select(models.User).filter(models.User.email == user.email))
    if res.scalar_one_or_none(): raise HTTPException(400, "Email already exists")
    
    new_user = models.User(
        email=user.email,
        hashed_password=auth.get_password_hash(user.password),
        full_name=user.full_name,
        role=user.role,
        status=user.status
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user
