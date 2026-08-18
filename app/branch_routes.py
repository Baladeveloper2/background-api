from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

from .database import get_async_db
from . import models, auth_routes
from .visibility import get_tenant_filters

router = APIRouter(prefix="/branches", tags=["Branches"])

# Pydantic models for validation
class BranchCreate(BaseModel):
    customer_id: str
    branch_name: str
    branch_code: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = "ACTIVE"
    # User Details
    username: Optional[str] = None
    user_email: Optional[str] = None
    user_phone: Optional[str] = None
    password: Optional[str] = None
    confirm_password: Optional[str] = None

class BranchUpdate(BaseModel):
    branch_name: Optional[str] = None
    branch_code: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    # User Details
    username: Optional[str] = None
    user_email: Optional[str] = None
    user_phone: Optional[str] = None
    password: Optional[str] = None
    confirm_password: Optional[str] = None

class ZoneMinimal(BaseModel):
    id: str
    zone_name: str
    model_config = ConfigDict(from_attributes=True)

class CustomerMinimal(BaseModel):
    id: str
    company_name: Optional[str] = None
    name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class BranchResponse(BaseModel):
    id: str
    customer_id: str
    branch_name: str
    branch_code: Optional[str]
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    address: Optional[str]
    contact_person: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    status: str
    customer: Optional[CustomerMinimal] = None
    zone: Optional[ZoneMinimal] = None
    username: Optional[str] = None
    user_email: Optional[str] = None
    user_phone: Optional[str] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)


async def populate_branch_user(db_branch: models.Branch, db: AsyncSession):
    if not db_branch:
        return
    user_res = await db.execute(
        select(models.User).filter(
            models.User.branch_id == db_branch.id,
            models.User.role.in_([models.UserRole.BRANCH_ADMIN, models.UserRole.BRANCH_ADMIN_SPACED])
        )
    )
    branch_user = user_res.scalars().first()
    if branch_user:
        db_branch.username = branch_user.full_name
        db_branch.user_email = branch_user.email
        db_branch.user_phone = branch_user.phone
    else:
        db_branch.username = None
        db_branch.user_email = None
        db_branch.user_phone = None

async def populate_branches_users(db_branches: list, db: AsyncSession):
    if not db_branches:
        return
    branch_ids = [b.id for b in db_branches]
    user_res = await db.execute(
        select(models.User).filter(
            models.User.branch_id.in_(branch_ids),
            models.User.role.in_([models.UserRole.BRANCH_ADMIN, models.UserRole.BRANCH_ADMIN_SPACED])
        )
    )
    users = user_res.scalars().all()
    user_map = {u.branch_id: u for u in users}
    for b in db_branches:
        u = user_map.get(b.id)
        if u:
            b.username = u.full_name
            b.user_email = u.email
            b.user_phone = u.phone
        else:
            b.username = None
            b.user_email = None
            b.user_phone = None

async def check_branch_auth(branch_id: str = None, customer_id: str = None, current_user: models.User = None, db: AsyncSession = None):
    # Use visibility helper
    tenant_filter = get_tenant_filters(current_user, models.Branch)
    if tenant_filter is True:
        return True
    if tenant_filter is False:
        raise HTTPException(status_code=403, detail="Not authorized.")
        
    if branch_id:
        result = await db.execute(select(models.Branch).filter(models.Branch.id == branch_id))
        branch = result.scalars().first()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")
        # For simplicity, we enforce tenant logic explicitly since we don't have a single query to apply the filter to
        role_name = current_user.role_rel.name.upper() if current_user.role_rel else (current_user.role.name if hasattr(current_user.role, 'name') else str(current_user.role)).upper()
        if role_name in ["SUPER_ADMIN", "USERROLE.SUPER_ADMIN"]:
            pass # Super admins can access any branch
        elif role_name == "ZONE_ADMIN" or role_name == "ZONE ADMIN":
            customer_res = await db.execute(select(models.Customer).filter(models.Customer.id == branch.customer_id))
            customer = customer_res.scalars().first()
            if customer and customer.zone_id != current_user.zone_id:
                raise HTTPException(status_code=403, detail="Not authorized for this branch.")
        elif role_name in ["CUSTOMER_HEAD", "CUSTOMER HEAD", "CUSTOMER", "CUSTOMER_ADMIN", "USERROLE.CUSTOMER_ADMIN"]:
            if branch.customer_id != current_user.customer_id:
                raise HTTPException(status_code=403, detail="Not authorized for this branch.")
        else:
            if current_user.branch_id != branch.id:
                raise HTTPException(status_code=403, detail="Not authorized for this branch.")
                
    if customer_id:
        role_name = current_user.role_rel.name.upper() if current_user.role_rel else (current_user.role.name if hasattr(current_user.role, 'name') else str(current_user.role)).upper()
        if role_name in ["SUPER_ADMIN", "USERROLE.SUPER_ADMIN"]:
            pass # Super admins can access any branch
        elif role_name == "ZONE_ADMIN" or role_name == "ZONE ADMIN":
            customer_res = await db.execute(select(models.Customer).filter(models.Customer.id == customer_id))
            customer = customer_res.scalars().first()
            if customer and customer.zone_id != current_user.zone_id:
                raise HTTPException(status_code=403, detail="Not authorized for this customer.")
        elif role_name in ["CUSTOMER_HEAD", "CUSTOMER HEAD", "CUSTOMER", "CUSTOMER_ADMIN", "USERROLE.CUSTOMER_ADMIN"]:
            if current_user.customer_id != customer_id:
                 raise HTTPException(status_code=403, detail="Not authorized.")
        else:
            if current_user.customer_id != customer_id:
                 raise HTTPException(status_code=403, detail="Not authorized.")
                 
    return True


@router.post("/", response_model=BranchResponse)
async def create_branch(
    branch: BranchCreate, 
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    await check_branch_auth(customer_id=branch.customer_id, current_user=current_user, db=db)
    
    if branch.branch_code:
        result = await db.execute(
            select(models.Branch).filter(
                models.Branch.branch_code == branch.branch_code
            )
        )
        existing_branch = result.scalars().first()
        if existing_branch:
            if getattr(existing_branch, "status", None) == "DELETED":
                import time
                existing_branch.branch_code = f"{existing_branch.branch_code[:20]}_del_{int(time.time())}"
                db.add(existing_branch)
                await db.flush()
            else:
                raise HTTPException(status_code=400, detail="Branch with this code already exists")
    
    if branch.password and branch.password != branch.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
        
    customer_result = await db.execute(select(models.Customer).filter(models.Customer.id == branch.customer_id))
    customer = customer_result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    if branch.user_email:
        existing_user = await db.execute(select(models.User).filter(models.User.email == branch.user_email))
        existing_user = existing_user.scalars().first()
        if existing_user:
            if getattr(existing_user, "status", None) in ["INACTIVE", "DELETED"]:
                import time
                existing_user.email = f"{int(time.time())}_del_{existing_user.email[:200]}"
                db.add(existing_user)
                await db.flush()
            else:
                raise HTTPException(status_code=400, detail="User with this email already exists")

    branch_data = branch.model_dump(exclude={"username", "user_email", "user_phone", "password", "confirm_password"})
    branch_data["zone_id"] = customer.zone_id
    
    db_branch = models.Branch(**branch_data)
    db.add(db_branch)
    await db.commit()
    await db.refresh(db_branch)
    
    # Create Branch Admin User
    if branch.user_email and branch.password:
        from .auth import get_password_hash
        from .enums import UserRole
        new_user = models.User(
            email=branch.user_email,
            hashed_password=get_password_hash(branch.password),
            full_name=branch.username or branch.branch_name + " Admin",
            phone=branch.user_phone,
            role=UserRole.BRANCH_ADMIN,
            customer_id=customer.id,
            branch_id=db_branch.id,
            zone_id=customer.zone_id,
            status="ACTIVE"
        )
        db.add(new_user)
        await db.commit()
        
    # Reload branch with relationships
    await db.refresh(db_branch)
    result = await db.execute(
        select(models.Branch).options(
            selectinload(models.Branch.customer).selectinload(models.Customer.zone),
            selectinload(models.Branch.zone)
        ).filter(models.Branch.id == db_branch.id)
    )
    db_br = result.scalars().first()
    await populate_branch_user(db_br, db)
    return db_br

@router.get("/", response_model=List[BranchResponse])
async def list_branches(
    customer_id: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    query = select(models.Branch).options(
        selectinload(models.Branch.customer).selectinload(models.Customer.zone),
        selectinload(models.Branch.zone)
    )
    
    # Filter based on Role scope
    tenant_filter = get_tenant_filters(current_user, models.Branch)
    if tenant_filter is not None:
        if tenant_filter is False:
            return []
        elif tenant_filter is not True:
            query = query.filter(tenant_filter)
            
    if customer_id:
        query = query.filter(models.Branch.customer_id == customer_id)
        
    result = await db.execute(query)
    branches = result.scalars().all()
    await populate_branches_users(branches, db)
    return branches

@router.get("/{branch_id}", response_model=BranchResponse)
async def get_branch(
    branch_id: str, 
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    await check_branch_auth(branch_id=branch_id, current_user=current_user, db=db)
    result = await db.execute(
        select(models.Branch)
        .options(selectinload(models.Branch.customer).selectinload(models.Customer.zone), selectinload(models.Branch.zone))
        .filter(models.Branch.id == branch_id)
    )
    branch = result.scalars().first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    await populate_branch_user(branch, db)
    return branch

@router.put("/{branch_id}", response_model=BranchResponse)
@router.patch("/{branch_id}", response_model=BranchResponse)
async def update_branch(
    branch_id: str, 
    branch_update: BranchUpdate, 
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    # Only CUSTOMER_ADMIN and above can update branches generally, or Branch Admin can update their own branch details
    await check_branch_auth(branch_id=branch_id, current_user=current_user, db=db)
    
    result = await db.execute(select(models.Branch).filter(models.Branch.id == branch_id))
    db_branch = result.scalars().first()
    if not db_branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    user_res = await db.execute(
        select(models.User).filter(
            models.User.branch_id == branch_id,
            models.User.role.in_([models.UserRole.BRANCH_ADMIN, models.UserRole.BRANCH_ADMIN_SPACED])
        )
    )
    branch_user = user_res.scalars().first()

    if branch_update.user_email:
        # Check if email is already taken by ANOTHER user
        if branch_user and branch_user.email != branch_update.user_email:
            existing_user = await db.execute(select(models.User).filter(models.User.email == branch_update.user_email))
            if existing_user.scalars().first():
                raise HTTPException(status_code=400, detail="User with this email already exists")
        elif not branch_user:
            existing_user = await db.execute(select(models.User).filter(models.User.email == branch_update.user_email))
            if existing_user.scalars().first():
                raise HTTPException(status_code=400, detail="User with this email already exists")

    # Update or create Branch Admin User
    if branch_update.user_email:
        from .auth import get_password_hash
        from .enums import UserRole
        if branch_user:
            if branch_update.username is not None:
                branch_user.full_name = branch_update.username
            branch_user.email = branch_update.user_email
            if branch_update.user_phone is not None:
                branch_user.phone = branch_update.user_phone
            if branch_update.password:
                if branch_update.password != branch_update.confirm_password:
                    raise HTTPException(status_code=400, detail="Passwords do not match")
                branch_user.hashed_password = get_password_hash(branch_update.password)
            db.add(branch_user)
        else:
            if branch_update.password:
                if branch_update.password != branch_update.confirm_password:
                    raise HTTPException(status_code=400, detail="Passwords do not match")
                new_user = models.User(
                    email=branch_update.user_email,
                    hashed_password=get_password_hash(branch_update.password),
                    full_name=branch_update.username or db_branch.branch_name + " Admin",
                    phone=branch_update.user_phone,
                    role=UserRole.BRANCH_ADMIN,
                    customer_id=db_branch.customer_id,
                    branch_id=db_branch.id,
                    zone_id=db_branch.zone_id,
                    status="ACTIVE"
                )
                db.add(new_user)
        
    exclude_keys = {"username", "user_email", "user_phone", "password", "confirm_password"}
    update_data = branch_update.model_dump(exclude=exclude_keys, exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_branch, key, value)
        
    await db.commit()
    
    # Reload branch with relationships
    await db.refresh(db_branch)
    result = await db.execute(
        select(models.Branch).options(
            selectinload(models.Branch.customer).selectinload(models.Customer.zone),
            selectinload(models.Branch.zone)
        ).filter(models.Branch.id == db_branch.id)
    )
    db_br = result.scalars().first()
    await populate_branch_user(db_br, db)
    return db_br

@router.delete("/{branch_id}")
async def delete_branch(
    branch_id: str, 
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    role_name = current_user.role_rel.name.upper() if current_user.role_rel else (current_user.role.name if hasattr(current_user.role, 'name') else str(current_user.role)).upper()
    if role_name not in ["SUPER_ADMIN", "ZONE_ADMIN", "CUSTOMER_ADMIN", "USERROLE.SUPER_ADMIN", "USERROLE.ZONE_ADMIN", "USERROLE.CUSTOMER_ADMIN"]:
        raise HTTPException(status_code=403, detail="Only Admins can delete branches")
        
    await check_branch_auth(branch_id=branch_id, current_user=current_user, db=db)
    
    result = await db.execute(select(models.Branch).filter(models.Branch.id == branch_id))
    db_branch = result.scalars().first()
    if not db_branch:
        raise HTTPException(status_code=404, detail="Branch not found")
        
    # Check for linked users or cases
    users = await db.execute(select(models.User).filter(models.User.branch_id == branch_id))
    if users.scalars().first():
        raise HTTPException(status_code=400, detail="Cannot delete branch with associated users. Reassign them first.")
        
    cases = await db.execute(select(models.Case).filter(models.Case.branch_id == branch_id))
    if cases.scalars().first():
        raise HTTPException(status_code=400, detail="Cannot delete branch with associated cases.")

    await db.delete(db_branch)
    await db.commit()
    return {"message": "Branch deleted successfully"}

@router.get("/workload/summary")
async def get_branch_workload(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    if not current_user.branch_id:
        raise HTTPException(status_code=403, detail="User is not associated with any branch")
        
    branch_id = current_user.branch_id
    
    from sqlalchemy import or_
    # Get users in this branch OR at the customer level (Customer Head), excluding the currently logged-in user
    filter_conditions = [
        models.User.id != current_user.id,
        or_(
            models.User.branch_id == branch_id,
            (models.User.customer_id == current_user.customer_id) & (models.User.branch_id.is_(None)) if current_user.customer_id else False
        )
    ]
    
    users_result = await db.execute(
        select(models.User).filter(*filter_conditions)
    )
    users = users_result.scalars().all()
    
    # Get all cases for this branch
    from sqlalchemy.orm import selectinload
    cases_result = await db.execute(
        select(models.Case)
        .options(selectinload(models.Case.candidate))
        .filter(models.Case.branch_id == branch_id)
    )
    cases = cases_result.scalars().all()
    
    # Compute stats per user
    user_stats = {}
    for u in users:
        role_val = u.role.value if hasattr(u.role, 'value') else str(u.role)
        role_cleaned = role_val.replace('UserRole.', '').replace('_', ' ').title()
        user_stats[u.id] = {
            "id": u.id,
            "name": u.full_name or u.email,
            "email": u.email,
            "role": role_cleaned,
            "total_cases": 0,
            "completed": 0,
            "in_progress": 0,
            "cases": []
        }
        
    for c in cases:
        user_ids = set()
        if c.candidate and c.candidate.created_by:
            user_ids.add(c.candidate.created_by)
        if c.assigned_to:
            user_ids.add(c.assigned_to)
            
        for uid in user_ids:
            if uid in user_stats:
                user_stats[uid]["total_cases"] += 1
                status_str = (c.status or "").upper()
                
                # Append case details
                case_info = {
                    "id": c.id,
                    "case_ref_no": c.case_ref_no,
                    "candidate_name": c.candidate.name if c.candidate else "Unknown",
                    "status": c.status,
                    "received_date": c.received_date.strftime("%Y-%m-%d") if c.received_date else None
                }
                user_stats[uid]["cases"].append(case_info)
                
                if status_str in ['FINALIZED', 'COMPLETED', 'POSITIVE', 'NEGATIVE', 'DISCREPANCY', 'UNABLE TO VERIFY', 'HOLD', 'INSUFFICIENT', 'QC_VERIFIED', 'CLOSED']:
                    user_stats[uid]["completed"] += 1
                else:
                    user_stats[uid]["in_progress"] += 1
                
    # Sort users by total cases descending
    sorted_users = sorted(user_stats.values(), key=lambda x: x["total_cases"], reverse=True)
    return {"users": sorted_users}

