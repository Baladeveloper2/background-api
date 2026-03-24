from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from jose import JWTError, jwt
from . import models, schemas, auth, database
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request
import re
import os

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = schemas.TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    return user

def check_permissions(role: models.UserRole):
    def role_checker(current_user: models.User = Depends(get_current_user)):
        if current_user.role != role and current_user.role != models.UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The user doesn't have enough privileges"
            )
        return current_user
    return role_checker

def check_module_permission(module: str, sub_module: str = None, action: str = "read"):
    def permission_checker(current_user: models.User = Depends(get_current_user)):
        if current_user.role == models.UserRole.SUPER_ADMIN:
            return current_user
        
        # Combine legacy permissions and new RBAC role permissions
        perms = current_user.bvs_permissions or {}
        
        # New Role Based Permissions
        # Format: {"bvs.verification": {"read": true, "write": false, "delete": false}}
        role_perms = {}
        if current_user.role_rel and current_user.role_rel.permissions:
            role_perms = current_user.role_rel.permissions

        # Allow access if either legacy or generic role allows it
        has_access = False
        
        if sub_module:
            role_key = f"{module}.{sub_module}"
            
            # Check structured RBAC (Nested JSON)
            role_module_perms = role_perms.get(role_key)
            if isinstance(role_module_perms, dict):
                if role_module_perms.get(action, False):
                    has_access = True
            elif role_module_perms is True:
                 # Support fallback for legacy flat boolean structure during migration
                 if action == "read":
                     has_access = True

            # Check legacy nested
            if not has_access and current_user.bvs_permissions and current_user.bvs_permissions.get(module, {}).get(sub_module):
                # Legacy implies full access.
                if action in ["read", "write", "delete"]: 
                    has_access = True
                
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: Requires '{action}' permission on {module}/{sub_module}"
                )
        else:
            # Module-level check (e.g. "bms.applicants")
            role_module_perms = role_perms.get(module)
            
            # Check structured RBAC
            if isinstance(role_module_perms, dict):
                 if role_module_perms.get(action, False):
                     has_access = True
            elif role_module_perms is True:
                 # Legacy flat fallback
                 if action == "read":
                     has_access = True
            
            # Or if it's a category and they have access to any explicit submodule action
            if not has_access:
                if any(k.startswith(f"{module}.") and isinstance(v, dict) and v.get(action, False) for k, v in role_perms.items()):
                    has_access = True
                # Legacy flat fallback for submodules
                elif action == "read" and any(k.startswith(f"{module}.") and v is True for k, v in role_perms.items()):
                    has_access = True
            
            # Check legacy module access
            if not has_access:
                module_perms = perms.get(module, {})
                if any(module_perms.values()):
                    if action in ["read", "write", "delete"]:
                        has_access = True
                
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: Requires '{action}' permission on {module} module"
                )
                
        return current_user
    return permission_checker


@router.post("/login", response_model=schemas.Token)
@limiter.limit("5/minute")
def login_for_access_token(request: Request, db: Session = Depends(database.get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Merged permissions: legacy bvs_permissions + assigned role permissions
    permissions = user.bvs_permissions or {}
    if user.role_rel and user.role_rel.permissions:
        # Merge permissions (structured permissions like "bvs.verification": true)
        permissions.update(user.role_rel.permissions)

    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={
            "sub": user.email, 
            "role": user.role, 
            "full_name": user.full_name,
            "permissions": permissions
        }, 
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=schemas.User)
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    if len(user.password) < 8 or not re.search(r"[a-zA-Z]", user.password) or not re.search(r"\d", user.password):
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long and contain both letters and numbers")
        
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        role=user.role,
        status=user.status
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
