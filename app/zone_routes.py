from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

from .database import get_async_db
from . import models, auth_routes
from .visibility import get_tenant_filters

router = APIRouter(prefix="/zones", tags=["Zones"])

# Pydantic models for validation
class ZoneCreate(BaseModel):
    zone_name: str
    zone_code: str
    status: Optional[str] = "ACTIVE"

class ZoneUpdate(BaseModel):
    zone_name: Optional[str] = None
    zone_code: Optional[str] = None
    status: Optional[str] = None

class ZoneResponse(BaseModel):
    id: str
    zone_name: str
    zone_code: str
    status: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)

# Require Super Admin for Zone Management
async def require_super_admin(current_user: models.User = Depends(auth_routes.get_current_user)):
    if current_user.role.name != "SUPER_ADMIN": # or role.value if Enum
        raise HTTPException(status_code=403, detail="Only Super Admins can manage zones.")
    return current_user

@router.post("/", response_model=ZoneResponse)
async def create_zone(
    zone: ZoneCreate, 
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(require_super_admin)
):
    # Check for existing zone name or code
    result = await db.execute(
        select(models.Zone).filter(
            (models.Zone.zone_name == zone.zone_name) | 
            (models.Zone.zone_code == zone.zone_code)
        )
    )
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Zone with this name or code already exists")
        
    db_zone = models.Zone(
        zone_name=zone.zone_name,
        zone_code=zone.zone_code,
        status=zone.status
    )
    db.add(db_zone)
    await db.commit()
    await db.refresh(db_zone)
    return db_zone

@router.get("/", response_model=List[ZoneResponse])
async def list_zones(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    # Apply tenant visibility filter
    query = select(models.Zone).filter(models.Zone.status != "DELETED")
    tenant_filter = get_tenant_filters(current_user, models.Zone)
    
    if tenant_filter is not None:
        if tenant_filter is False:
            return []
        elif tenant_filter is not True:
            query = query.filter(tenant_filter)
            
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{zone_id}", response_model=ZoneResponse)
async def get_zone(
    zone_id: str, 
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(auth_routes.get_current_user)
):
    # Authorization
    if current_user.role.name != "SUPER_ADMIN" and current_user.zone_id != zone_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this zone")
        
    result = await db.execute(select(models.Zone).filter(models.Zone.id == zone_id))
    zone = result.scalars().first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone

@router.put("/{zone_id}", response_model=ZoneResponse)
async def update_zone(
    zone_id: str, 
    zone_update: ZoneUpdate, 
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(require_super_admin)
):
    result = await db.execute(select(models.Zone).filter(models.Zone.id == zone_id))
    db_zone = result.scalars().first()
    if not db_zone:
        raise HTTPException(status_code=404, detail="Zone not found")
        
    if zone_update.zone_name is not None:
        db_zone.zone_name = zone_update.zone_name
    if zone_update.zone_code is not None:
        db_zone.zone_code = zone_update.zone_code
    if zone_update.status is not None:
        db_zone.status = zone_update.status
        
    await db.commit()
    await db.refresh(db_zone)
    return db_zone

@router.delete("/{zone_id}")
async def delete_zone(
    zone_id: str, 
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(require_super_admin)
):
    result = await db.execute(select(models.Zone).filter(models.Zone.id == zone_id))
    db_zone = result.scalars().first()
    if not db_zone:
        raise HTTPException(status_code=404, detail="Zone not found")
        
    # Check if there are customers in this zone
    customers = await db.execute(select(models.Customer).filter(models.Customer.zone_id == zone_id, models.Customer.status != "DELETED"))
    if customers.scalars().first():
        raise HTTPException(status_code=400, detail="Cannot delete zone with associated customers. Reassign them first.")
        
    # Soft delete the zone
    db_zone.status = "DELETED"
    await db.commit()
    return {"message": "Zone deleted successfully"}
