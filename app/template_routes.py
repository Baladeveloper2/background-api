from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional

from . import models
from .database import get_async_db
from .auth_routes import get_current_user

router = APIRouter(prefix="/communication-templates", tags=["communication_templates"])

class TemplateCreateSchema(BaseModel):
    name: str
    type: str # 'EMAIL' or 'SMS'
    subject: Optional[str] = None
    body: str

class TemplateResponseSchema(TemplateCreateSchema):
    id: str

    class Config:
        orm_mode = True

@router.post("", response_model=TemplateResponseSchema)
async def create_template(
    payload: TemplateCreateSchema,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    if payload.type not in ["EMAIL", "SMS"]:
        raise HTTPException(status_code=400, detail="Invalid template type. Must be EMAIL or SMS.")
    
    new_template = models.CommunicationTemplate(
        name=payload.name,
        type=payload.type,
        subject=payload.subject if payload.type == "EMAIL" else None,
        body=payload.body,
        created_by=current_user.id
    )
    db.add(new_template)
    await db.commit()
    await db.refresh(new_template)
    return new_template

@router.get("", response_model=List[TemplateResponseSchema])
async def list_templates(
    type: Optional[str] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    query = select(models.CommunicationTemplate).order_by(models.CommunicationTemplate.created_at.desc())
    if type:
        query = query.filter(models.CommunicationTemplate.type == type)
    
    result = await db.execute(query)
    templates = result.scalars().all()
    return templates

@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    result = await db.execute(select(models.CommunicationTemplate).filter_by(id=template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    await db.delete(template)
    await db.commit()
    return {"message": "Template deleted successfully"}
