from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

from .database import get_async_db
from .auth_routes import get_current_user
from . import models
from .logging_config import logger

router = APIRouter(prefix="/address-change", tags=["address-change"])

class AddressChangeRequestCreate(BaseModel):
    case_id: str
    candidate_id: str
    new_address: str
    reason: Optional[str] = None
    proof_url: Optional[str] = None

class AddressChangeReview(BaseModel):
    status: str # "APPROVED" or "REJECTED"
    remarks: Optional[str] = None

@router.post("")
async def create_address_change_request(
    request_data: AddressChangeRequestCreate,
    req: Request,
    db: AsyncSession = Depends(get_async_db)
):
    try:
        # Prevent duplicate pending requests
        existing_q = select(models.AddressChangeRequest).filter(
            models.AddressChangeRequest.case_id == request_data.case_id,
            models.AddressChangeRequest.status == "PENDING"
        )
        existing_res = await db.execute(existing_q)
        if existing_res.scalar_one_or_none():
            raise HTTPException(400, "A pending address change request already exists for this case.")

        client_host = req.client.host if req.client else None

        new_request = models.AddressChangeRequest(
            candidate_id=request_data.candidate_id,
            case_id=request_data.case_id,
            old_address="Address fetched from DB", # Ideally fetch from candidate/case
            new_address=request_data.new_address,
            reason=request_data.reason,
            proof_url=request_data.proof_url,
            ip_address=client_host
        )
        db.add(new_request)
        await db.commit()
        await db.refresh(new_request)
        
        return {"message": "Address change request submitted successfully.", "id": new_request.id}
    except HTTPException as h:
        raise h
    except Exception as e:
        logger.error(f"Error creating address change request: {e}")
        raise HTTPException(500, "Internal Server Error")

@router.get("")
async def list_address_change_requests(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    try:
        query = select(models.AddressChangeRequest).order_by(desc(models.AddressChangeRequest.requested_at))
        res = await db.execute(query)
        requests = res.scalars().all()
        
        return {"data": requests}
    except Exception as e:
        logger.error(f"Error listing address change requests: {e}")
        raise HTTPException(500, "Internal Server Error")

@router.post("/{request_id}/review")
async def review_address_change_request(
    request_id: str,
    review_data: AddressChangeReview,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    try:
        query = select(models.AddressChangeRequest).filter(models.AddressChangeRequest.id == request_id)
        res = await db.execute(query)
        acr = res.scalar_one_or_none()
        
        if not acr:
            raise HTTPException(404, "Address change request not found.")
            
        acr.status = review_data.status
        acr.remarks = review_data.remarks
        acr.reviewed_at = datetime.utcnow()
        acr.reviewed_by = current_user.id
        
        await db.commit()
        
        # If approved, business logic here to expire old link & generate new digital verification
        
        return {"message": f"Address change request {review_data.status.lower()} successfully."}
    except Exception as e:
        logger.error(f"Error reviewing address change request: {e}")
        raise HTTPException(500, "Internal Server Error")
