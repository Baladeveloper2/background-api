from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import timedelta, datetime
from typing import Optional
from jose import JWTError, jwt
from . import models, schemas, auth, database
from slowapi import Limiter
from slowapi.util import get_remote_address
from .cache import delete_cache
import re
import time
import threading

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# ---------------------------------------------------------------------------
# In-process token → user TTL cache
# Keyed on the raw JWT string; entries expire after USER_CACHE_TTL_SECONDS.
# This avoids a DB round-trip on every authenticated request (was 6s+).
# Thread-safe via a simple lock; size is bounded by active token count.
# ---------------------------------------------------------------------------
_USER_CACHE: dict = {}          # token -> {"user": User, "ts": float}
_USER_CACHE_LOCK = threading.Lock()
USER_CACHE_TTL_SECONDS = 120    # 2 minutes

def _cache_get(token: str):
    with _USER_CACHE_LOCK:
        entry = _USER_CACHE.get(token)
        if entry and (time.monotonic() - entry["ts"]) < USER_CACHE_TTL_SECONDS:
            return entry["user"]
        if entry:
            del _USER_CACHE[token]  # evict stale entry
    return None

def _cache_set(token: str, user):
    with _USER_CACHE_LOCK:
        # Prune entries older than TTL on every write to keep dict bounded
        now = time.monotonic()
        stale = [k for k, v in _USER_CACHE.items() if (now - v["ts"]) >= USER_CACHE_TTL_SECONDS]
        for k in stale:
            del _USER_CACHE[k]
        _USER_CACHE[token] = {"user": user, "ts": now}

def invalidate_user_cache(token: str):
    """Call this after logout or permission changes to force a fresh DB lookup."""
    with _USER_CACHE_LOCK:
        _USER_CACHE.pop(token, None)

def invalidate_user_cache_by_user_id(user_id: str):
    """Evict cached user instances by user ID when user details or permissions change."""
    with _USER_CACHE_LOCK:
        keys_to_del = [k for k, v in _USER_CACHE.items() if getattr(v.get("user"), "id", None) == user_id]
        for k in keys_to_del:
            _USER_CACHE.pop(k, None)

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

    # Fast path: return cached user merged into active DB session (avoids DB hit on every request & detached session errors)
    cached = _cache_get(token)
    if cached is not None:
        return await db.merge(cached)

    # Cache miss — fetch from DB and populate cache
    stmt = select(models.User).options(selectinload(models.User.role_rel)).filter(models.User.email == token_data.email)
    res = await db.execute(stmt)
    user = res.unique().scalar_one_or_none()
    if user is None: raise credentials_exception

    _cache_set(token, user)
    return user

async def create_audit_log(db: AsyncSession, user_id: str, action: str, details: str, resource_id: Optional[str] = None):
    log = models.AuditLog(user_id=user_id, action=action, details=details, resource_id=resource_id)
    db.add(log)
    await db.flush()
    if resource_id:
        # Invalidate the history cache for this case
        # Note: We use the same key pattern as in case_routes.py
        cache_key = f"case_history:get_case_history:case_id:{resource_id}"
        await delete_cache(cache_key)

def check_permissions(role: models.UserRole):
    async def role_checker(current_user: models.User = Depends(get_current_user)):
        user_role_str = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
        target_role_str = str(role.value if hasattr(role, 'value') else role).upper()
        is_sa = user_role_str == "SUPER_ADMIN" or (current_user.role_rel and current_user.role_rel.name == "Super Admin")
        if user_role_str == target_role_str or is_sa: return current_user
        raise HTTPException(status_code=403, detail="Insufficient privileges")
    return role_checker

def check_module_permission(module: str, sub_module: Optional[str] = None, action: str = "read"):
    async def permission_checker(current_user: models.User = Depends(get_current_user)):
        if current_user.role == models.UserRole.SUPER_ADMIN: return current_user
        if current_user.role_rel and current_user.role_rel.name == "Super Admin": return current_user
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
                elif isinstance(rp, str):
                    m = {"read": "R", "write": "W", "delete": "D"}[action]
                    if m in rp: has_access = True
                elif rp is True and action == "read": has_access = True
        else:
            if any((perms.get(module, {})).values()): has_access = True
            if current_user.role_rel and current_user.role_rel.permissions:
                rp = current_user.role_rel.permissions.get(module)
                if isinstance(rp, dict) and rp.get(action): has_access = True
                elif isinstance(rp, str):
                    m = {"read": "R", "write": "W", "delete": "D"}[action]
                    if m in rp: has_access = True
                elif rp is True and action == "read": has_access = True

        if not has_access:
            # Check if it's a customer user accessing their permitted modules
            user_role_str = str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role).upper()
            role_name = (current_user.role_rel.name.upper() if current_user.role_rel else "").upper()
            is_customer = "CUSTOMER" in user_role_str or "CUSTOMER" in role_name
            
            if is_customer and action in ["read", "write"] and module in ["bms", "bvs"]:
                return current_user

            # Grant systemic write access to specific oversight roles for the verification module
            oversight_roles = [models.UserRole.QA, models.UserRole.QC, models.UserRole.MANAGER, models.UserRole.ADMIN]
            oversight_names = ["Super Admin", "QC Verifier"]
            
            is_oversight = current_user.role in oversight_roles
            if current_user.role_rel and current_user.role_rel.name in oversight_names:
                is_oversight = True

            if module == "bvs" and is_oversight:
                return current_user
            if module == "bms" and is_oversight and action == "read":
                return current_user
            raise HTTPException(status_code=403, detail=f"No {action} access to {module}")
        return current_user
    return permission_checker

from datetime import datetime
import random
from pydantic import BaseModel

class Verify2FARequest(BaseModel):
    temp_token: str
    otp_code: str

class Resend2FARequest(BaseModel):
    temp_token: str

@router.post("/login", response_model=schemas.Token)
@limiter.limit("5/minute")
async def login_for_access_token(request: Request, db: AsyncSession = Depends(database.get_async_db), form_data: OAuth2PasswordRequestForm = Depends()):
    stmt = select(models.User).options(
        selectinload(models.User.role_rel),
        selectinload(models.User.customer)
    ).filter(models.User.email == form_data.username)
    res = await db.execute(stmt)
    user = res.unique().scalar_one_or_none()
    
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    # If 2FA is enabled and user has a phone number
    if user.is_2fa_enabled and user.phone:
        otp = f"{random.randint(100000, 999999)}"
        user.otp_code = otp
        user.otp_expires_at = datetime.utcnow() + timedelta(minutes=5)
        db.add(user)
        await db.commit()
        
        # Send OTP SMS compliant with Jio DLT
        from .sms_utils import send_otp_sms
        await send_otp_sms(user.phone, otp)
        
        # Mask phone number (e.g. +91 ******1234)
        phone = user.phone.strip()
        masked_phone = f"+91 ******{phone[-4:]}" if len(phone) >= 4 else phone
        
        # Generate temp JWT token
        temp_token = auth.create_access_token(
            data={"sub": user.email, "type": "2fa_temp"},
            expires_delta=timedelta(minutes=5)
        )
        
        return {
            "status": "2fa_required",
            "temp_token": temp_token,
            "phone_masked": masked_phone
        }
    
    perms = (user.role_rel.permissions or {}).copy() if user.role_id and user.role_rel else (user.bvs_permissions or {}).copy()

    token = auth.create_access_token(
        data={
            "sub": user.email, 
            "id": user.id, 
            "role": user.role_rel.name if user.role_id and user.role_rel else ("Super Admin" if user.role == models.UserRole.SUPER_ADMIN else user.role), 
            "full_name": user.full_name, 
            "customer_id": user.customer_id,
            "permissions": perms
        },
        expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    branding = None
    if user.customer:
        branding = {
            "primary": user.customer.brand_primary_color,
            "secondary": user.customer.brand_secondary_color,
            "logo": user.customer.logo_url
        }

    return {
        "access_token": token, 
        "token_type": "bearer",
        "status": "success",
        "branding": branding
    }

@router.post("/verify-2fa", response_model=schemas.Token)
async def verify_2fa(payload: Verify2FARequest, db: AsyncSession = Depends(database.get_async_db)):
    try:
        decoded = jwt.decode(payload.temp_token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email = decoded.get("sub")
        token_type = decoded.get("type")
        
        if not email or token_type != "2fa_temp":
            raise HTTPException(status_code=401, detail="Invalid temporary token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Expired or invalid temporary token")
        
    stmt = select(models.User).options(
        selectinload(models.User.role_rel),
        selectinload(models.User.customer)
    ).filter(models.User.email == email)
    res = await db.execute(stmt)
    user = res.unique().scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not user.otp_code or user.otp_code != payload.otp_code:
        raise HTTPException(status_code=400, detail="Invalid OTP code")
        
    if not user.otp_expires_at or user.otp_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP code has expired")
        
    # Clear OTP columns
    user.otp_code = None
    user.otp_expires_at = None
    db.add(user)
    await db.commit()
    
    perms = (user.role_rel.permissions or {}).copy() if user.role_id and user.role_rel else (user.bvs_permissions or {}).copy()

    token = auth.create_access_token(
        data={
            "sub": user.email, 
            "id": user.id, 
            "role": user.role_rel.name if user.role_id and user.role_rel else ("Super Admin" if user.role == models.UserRole.SUPER_ADMIN else user.role), 
            "full_name": user.full_name, 
            "customer_id": user.customer_id,
            "permissions": perms
        },
        expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    branding = None
    if user.customer:
        branding = {
            "primary": user.customer.brand_primary_color,
            "secondary": user.customer.brand_secondary_color,
            "logo": user.customer.logo_url
        }

    return {
        "access_token": token, 
        "token_type": "bearer",
        "status": "success",
        "branding": branding
    }

@router.post("/resend-2fa")
async def resend_2fa(payload: Resend2FARequest, db: AsyncSession = Depends(database.get_async_db)):
    try:
        decoded = jwt.decode(payload.temp_token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email = decoded.get("sub")
        token_type = decoded.get("type")
        
        if not email or token_type != "2fa_temp":
            raise HTTPException(status_code=401, detail="Invalid temporary token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Expired or invalid temporary token")
        
    stmt = select(models.User).filter(models.User.email == email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    otp = f"{random.randint(100000, 999999)}"
    user.otp_code = otp
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=5)
    db.add(user)
    await db.commit()
    
    from .sms_utils import send_otp_sms
    await send_otp_sms(user.phone, otp)
    
    return {"status": "success", "message": "OTP resent successfully"}

@router.get("/me")
async def get_me(current_user: models.User = Depends(get_current_user), db: AsyncSession = Depends(database.get_async_db)):
    """Return full user details including branding for session hydration."""
    stmt = select(models.Customer).filter(models.Customer.id == current_user.customer_id)
    res = await db.execute(stmt)
    customer = res.scalar_one_or_none()
    
    branding = None
    if customer:
        branding = {
            "primary": customer.brand_primary_color,
            "secondary": customer.brand_secondary_color,
            "logo": customer.logo_url
        }
        
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": str(current_user.role.value if hasattr(current_user.role, 'value') else current_user.role),
        "customer_id": current_user.customer_id,
        "branding": branding
    }

@router.post("/register", response_model=schemas.User)
async def register_user(user: schemas.UserCreate, db: AsyncSession = Depends(database.get_async_db)):
    if len(user.password) < 8: raise HTTPException(400, "Password too short")
    
    res = await db.execute(select(models.User).filter(models.User.email == user.email))
    existing_user = res.scalar_one_or_none()
    if existing_user:
        if getattr(existing_user, "status", None) in ["INACTIVE", "DELETED"]:
            import time
            existing_user.email = f"{int(time.time())}_del_{existing_user.email[:200]}"
            db.add(existing_user)
            await db.flush()
        else:
            raise HTTPException(400, "Email already exists")
    
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
