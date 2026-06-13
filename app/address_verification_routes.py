import math
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel

from .database import get_async_db
from .auth_routes import get_current_user
from . import models
from .logging_config import logger
from .aws_utils import upload_to_s3
from .auth import create_access_token, SECRET_KEY, ALGORITHM
from jose import jwt, JWTError

router = APIRouter(prefix="/address-verification", tags=["address-verification"])

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000 # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

class GenerateLinkRequest(BaseModel):
    candidate_id: str
    case_id: str
    check_id: Optional[str] = None
    expected_latitude: Optional[float] = None
    expected_longitude: Optional[float] = None
    expected_address: Optional[str] = None

@router.post("/generate-link")
async def generate_verification_link(
    req: GenerateLinkRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    try:
        # Create address verification entry
        verif = models.AddressVerification(
            candidate_id=req.candidate_id,
            case_id=req.case_id,
            check_id=req.check_id,
            submitted_address=req.expected_address,
            submitted_latitude=req.expected_latitude,
            submitted_longitude=req.expected_longitude,
            verification_status="PENDING"
        )
        db.add(verif)
        await db.commit()
        await db.refresh(verif)

        # Generate JWT Token for candidate
        payload = {
            "sub": "address-verification",
            "verification_id": verif.id,
            "exp": datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        # MOCK: Send SMS/Email
        logger.info(f"Generated Link for Candidate {req.candidate_id}: /verify/address?token={token}")

        return {"message": "Verification link sent successfully.", "token": token, "verification_id": verif.id}
    except Exception as e:
        logger.error(f"Error generating link: {e}")
        raise HTTPException(500, "Internal Server Error")

@router.get("/validate-token")
async def validate_verification_token(
    token: str,
    db: AsyncSession = Depends(get_async_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        verif_id = payload.get("verification_id")
        if not verif_id:
            raise HTTPException(400, "Invalid token payload.")
            
        q = select(models.AddressVerification).filter(models.AddressVerification.id == verif_id)
        res = await db.execute(q)
        verif = res.scalar_one_or_none()
        
        if not verif:
            raise HTTPException(404, "Verification record not found.")
            
        if verif.verification_status != "PENDING":
            raise HTTPException(400, f"Link is already {verif.verification_status.lower()}.")
            
        # Fetch candidate name
        cand_q = select(models.Candidate).filter(models.Candidate.id == verif.candidate_id)
        cand_res = await db.execute(cand_q)
        candidate = cand_res.scalar_one_or_none()

        return {
            "verification_id": verif.id,
            "candidate_name": candidate.name if candidate else "Unknown",
            "expected_address": verif.submitted_address
        }
    except JWTError:
        raise HTTPException(401, "Token expired or invalid.")
    except HTTPException as h:
        raise h
    except Exception as e:
        logger.error(f"Error validating token: {e}")
        raise HTTPException(500, "Internal Server Error")

@router.post("/submit")
async def submit_address_verification(
    request: Request,
    verification_id: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    accuracy: float = Form(...),
    device_info: str = Form(...), # JSON string
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        q = select(models.AddressVerification).filter(models.AddressVerification.id == verification_id)
        res = await db.execute(q)
        verif = res.scalar_one_or_none()
        
        if not verif:
            raise HTTPException(404, "Verification record not found.")
            
        if verif.verification_status != "PENDING":
            raise HTTPException(400, "Verification already completed.")

        # Read File
        contents = await image.read()
        
        # MOCK: AI Validation Checks
        ai_score = 96.0
        
        # Upload to S3
        file_url = await upload_to_s3(contents, image.filename, "address_verifications")

        # Reverse Geocoding MOCK
        reverse_address = f"Reverse geocoded from {latitude}, {longitude}"
        
        # Distance calculation
        distance = None
        status = "Manual Review"
        if verif.submitted_latitude and verif.submitted_longitude:
            distance = haversine(latitude, longitude, verif.submitted_latitude, verif.submitted_longitude)
            if distance <= 50:
                status = "Verified"
            elif distance > 100:
                status = "Rejected"

        # Save metadata
        verif.latitude = latitude
        verif.longitude = longitude
        verif.accuracy = accuracy
        verif.captured_address = reverse_address
        verif.distance_meters = distance
        verif.verification_status = status
        verif.verified_at = datetime.utcnow()
        try:
            verif.device_info = json.loads(device_info)
        except:
            verif.device_info = {"raw": device_info}
            
        # Create Photo record
        photo = models.AddressVerificationPhoto(
            verification_id=verif.id,
            image_url=file_url,
            photo_type="live_capture",
            latitude=latitude,
            longitude=longitude,
            captured_at=datetime.utcnow()
        )
        db.add(photo)
        await db.commit()

        return {
            "message": "Verification submitted successfully",
            "status": status,
            "distance": distance,
            "ai_score": ai_score
        }
    except Exception as e:
        logger.error(f"Error submitting address verification: {e}")
        raise HTTPException(500, "Internal Server Error")

@router.get("/all")
async def get_all_verifications(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    try:
        q = select(models.AddressVerification).order_by(desc(models.AddressVerification.created_at))
        res = await db.execute(q)
        records = res.scalars().all()
        
        result = []
        for r in records:
            # Need candidate and customer info for the table
            cand_q = select(models.Candidate).filter(models.Candidate.id == r.candidate_id)
            cand_res = await db.execute(cand_q)
            cand = cand_res.scalar_one_or_none()
            
            result.append({
                "id": r.id,
                "candidate_id": r.candidate_id,
                "candidate_name": cand.name if cand else "Unknown",
                "customer_name": "Unknown", # Would need a join to case -> customer
                "expected_address": r.submitted_address,
                "captured_address": r.captured_address,
                "distance": r.distance_meters,
                "status": r.verification_status,
                "verified_at": r.verified_at,
                "created_at": r.created_at
            })
            
        return {"data": result}
    except Exception as e:
        logger.error(f"Error fetching address verifications: {e}")
        raise HTTPException(500, "Internal Server Error")
