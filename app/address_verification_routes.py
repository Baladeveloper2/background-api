import math
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Form, UploadFile, File, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc, or_, and_
from sqlalchemy.orm import selectinload, joinedload
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

def derive_verification_status(check: models.VerificationCheck, verif: Optional[models.AddressVerification]) -> str:
    """Derives a human-readable status for a digital address verification check."""
    # 1. No digital_link ever generated OR no token exists — truly uninitiated
    if not check.data or "digital_link" not in check.data or not check.digital_token:
        if not verif:
            return "Initiated"

    dl = check.data["digital_link"]
    dl_status = dl.get("status", "UNUSED")

    # 2. Check for expiry first (skip if already USED/completed)
    if dl_status not in ("USED", "COMPLETED"):
        expires_at_str = dl.get("expires_at")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                now = datetime.utcnow()
                if expires_at.tzinfo:
                    from datetime import timezone
                    now = now.replace(tzinfo=timezone.utc)
                if now > expires_at:
                    return "Expired"
            except Exception:
                pass

    # 3. Map digital_link.status to display label
    if dl_status in ("USED", "COMPLETED") or (verif and verif.verification_status in ("VERIFIED", "Verified", "COMPLETED")):
        return "Completed"
    elif verif and verif.verification_status in ("ADDRESS_MISMATCH", "REJECTED", "FAILED", "UNABLE_TO_LOCATE"):
        return "Failed"
    elif dl_status in ("LINK_SENT", "SENT"):
        return "Sent"
    elif dl_status == "OPENED":
        return "Opened"
    elif dl_status == "CAMERA_GRANTED":
        return "Camera Granted"
    elif dl_status in ("LOCATION_GRANTED", "GPS_CAPTURED"):
        return "Location Granted"
    elif dl_status == "LINK_GENERATED" or dl_status == "UNUSED":
        return "Link Generated"

    # 4. Fallback to AddressVerification row status
    if verif:
        status = (verif.verification_status or "PENDING").upper()
        if status == "PENDING":
            return "Sent"
        elif status in ("VERIFIED", "PARTIALLY_VERIFIED", "COMPLETED", "VERIFIED_CLEAR"):
            return "Completed"
        elif status in ("REJECTED", "ADDRESS_MISMATCH", "UNABLE_TO_LOCATE", "INSUFFICIENT", "FAILED"):
            return "Failed"
        return status.replace("_", " ").title()

    return "Link Generated"

@router.get("/all")
async def get_all_verifications(
    response: Response,
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    try:
        # Base query joining VerificationCheck, Case, Candidate, Customer, and AddressVerification
        stmt = (
            select(models.VerificationCheck, models.AddressVerification)
            .filter(models.VerificationCheck.check_type.ilike('%address%'))
            .outerjoin(models.Case, models.VerificationCheck.case_id == models.Case.id)
            .outerjoin(models.Candidate, models.Case.candidate_id == models.Candidate.id)
            .outerjoin(models.Customer, models.Case.customer_id == models.Customer.id)
            .outerjoin(models.AddressVerification, models.AddressVerification.check_id == models.VerificationCheck.id)
        )
        
        # Conditions list
        conditions = []
        
        # If the user is a CUSTOMER, restrict to their customer_id
        if current_user.role == models.UserRole.CUSTOMER:
            conditions.append(models.Case.customer_id == current_user.customer_id)
            
        if status and status != "ALL":
            if status == "PENDING":
                conditions.append(
                    or_(
                        models.AddressVerification.id.is_(None),
                        models.AddressVerification.verification_status == "PENDING"
                    )
                )
            else:
                conditions.append(models.AddressVerification.verification_status == status)
            
        if search:
            search_filter = or_(
                models.Candidate.name.ilike(f"%{search}%"),
                models.Candidate.client_emp_code.ilike(f"%{search}%"),
                models.Candidate.id.ilike(f"%{search}%"),
                models.Customer.name.ilike(f"%{search}%"),
                models.Candidate.phone.ilike(f"%{search}%")
            )
            conditions.append(search_filter)
            
        if conditions:
            stmt = stmt.filter(*conditions)
            
        # Count query
        count_stmt = (
            select(func.count(models.VerificationCheck.id))
            .filter(models.VerificationCheck.check_type.ilike('%address%'))
            .outerjoin(models.Case, models.VerificationCheck.case_id == models.Case.id)
            .outerjoin(models.Candidate, models.Case.candidate_id == models.Candidate.id)
            .outerjoin(models.Customer, models.Case.customer_id == models.Customer.id)
            .outerjoin(models.AddressVerification, models.AddressVerification.check_id == models.VerificationCheck.id)
        )
        if conditions:
            count_stmt = count_stmt.filter(*conditions)
            
        total_count_res = await db.execute(count_stmt)
        total_count = total_count_res.scalar() or 0
        
        # Sorting
        sort_column = models.Case.received_date
        if sort_by == "candidate_name":
            sort_column = models.Candidate.name
        elif sort_by == "client_name":
            sort_column = models.Customer.name
        elif sort_by == "status":
            sort_column = models.AddressVerification.verification_status
        elif sort_by == "completed_date":
            sort_column = models.AddressVerification.verified_at
            
        if sort_order == "asc":
            stmt = stmt.order_by(asc(sort_column))
        else:
            stmt = stmt.order_by(desc(sort_column))
            
        # Preload relationships
        stmt = stmt.options(
            joinedload(models.VerificationCheck.case).joinedload(models.Case.candidate),
            joinedload(models.VerificationCheck.case).joinedload(models.Case.customer),
            selectinload(models.AddressVerification.photos)
        )
        
        # Pagination
        stmt = stmt.offset(skip).limit(limit)
        
        res = await db.execute(stmt)
        records = res.all() # Returns list of tuples (VerificationCheck, AddressVerification)
        
        result = []
        for check, verif in records:
            case = check.case
            cand = case.candidate if case else None
            cust = case.customer if case else None
            
            # Derived columns
            v_status = derive_verification_status(check, verif)
            
            gps_status = "PENDING"
            if verif and verif.verified_at:
                gps_status = "MATCHED" if (verif.distance_meters is not None and verif.distance_meters <= 50) or verif.verification_status == "VERIFIED" else "MISMATCH"
                
            photo_status = "PENDING"
            if verif and verif.verified_at:
                photo_status = "VERIFIED" if verif.verification_status == "VERIFIED" else "REJECTED"
                
            # Derive link_status string
            link_status = "INITIATED"
            if v_status == "Completed":
                link_status = "COMPLETED"
            elif v_status == "Failed":
                link_status = "FAILED"
            elif v_status == "Expired":
                link_status = "EXPIRED"
            elif v_status == "Opened":
                link_status = "OPENED"
            elif v_status in ("Sent", "Camera Granted", "Location Granted"):
                link_status = "SENT"
            elif v_status == "Link Generated":
                link_status = "LINK_GENERATED"
            elif v_status == "Initiated":
                link_status = "INITIATED"
            
            if not check.digital_token and not verif:
                link_status = "INITIATED"

            # Extract digital_link metadata for the row
            dl = (check.data or {}).get("digital_link", {})
            generated_at_raw = dl.get("generated_at")
            expires_at_raw = dl.get("expires_at")

            def _fmt_dt(dt_str):
                if not dt_str:
                    return "—"
                try:
                    return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).strftime("%d %b %Y, %I:%M %p")
                except Exception:
                    return dt_str

            result.append({
                "id": verif.id if verif else check.id,
                "check_id": check.id,
                "candidateId": cand.client_emp_code if cand and cand.client_emp_code else (cand.id[:8] if cand else "—"),
                "candidateName": cand.name if cand else "Unknown",
                "clientName": cust.name if cust else "—",
                "mobileNumber": cand.phone if cand else "—",
                "verificationType": "Digital Address",
                "linkStatus": link_status,
                "gpsStatus": gps_status,
                "photoStatus": photo_status,
                "locationCaptured": verif.captured_address if verif else "—",
                "createdDate": _fmt_dt(generated_at_raw) if generated_at_raw else (case.received_date.strftime("%d %b %Y, %I:%M %p") if case and case.received_date else "—"),
                "completedDate": verif.verified_at.strftime("%d %b %Y, %I:%M %p") if verif and verif.verified_at else "—",
                "verificationStatus": v_status,
                "digitalToken": check.digital_token or ""
            })
            
        response.headers["X-Total-Count"] = str(total_count)
        response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
        
        return {"data": result}
    except Exception as e:
        logger.error(f"Error fetching address verifications: {e}")
        raise HTTPException(500, "Internal Server Error")

@router.get("/{verification_id}/details")
async def get_verification_details(
    verification_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    try:
        # 1. Try to find by AddressVerification.id
        stmt = (
            select(models.AddressVerification)
            .options(
                joinedload(models.AddressVerification.candidate),
                joinedload(models.AddressVerification.case).joinedload(models.Case.customer),
                selectinload(models.AddressVerification.photos),
                joinedload(models.AddressVerification.check)
            )
            .filter(models.AddressVerification.id == verification_id)
        )
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()
        
        # 2. If not found, try to find by VerificationCheck.id (pending checks)
        check_record = None
        if not record:
            check_stmt = (
                select(models.VerificationCheck)
                .options(
                    joinedload(models.VerificationCheck.case).joinedload(models.Case.candidate),
                    joinedload(models.VerificationCheck.case).joinedload(models.Case.customer)
                )
                .filter(models.VerificationCheck.id == verification_id)
            )
            check_res = await db.execute(check_stmt)
            check_record = check_res.scalar_one_or_none()
            
            if not check_record:
                raise HTTPException(status_code=404, detail="Verification request not found")
        
        # Extract variables based on which record we found
        if record:
            check_obj = record.check
            case_obj = record.case
            cand_obj = record.candidate
            cust_obj = case_obj.customer if case_obj else None
            
            latitude = record.latitude
            longitude = record.longitude
            accuracy = record.accuracy
            altitude = record.altitude
            captured_address = record.captured_address
            submitted_address = record.submitted_address
            submitted_latitude = record.submitted_latitude
            submitted_longitude = record.submitted_longitude
            distance_meters = record.distance_meters
            v_status = derive_verification_status(check_obj, record) if check_obj else record.verification_status
            verified_at = record.verified_at
            created_at = record.created_at
            device_info = record.device_info or {}
            photos = record.photos or []
            case_id = record.case_id
            candidate_id = record.candidate_id
            check_id = record.check_id
        else:
            check_obj = check_record
            case_obj = check_record.case
            cand_obj = case_obj.candidate if case_obj else None
            cust_obj = case_obj.customer if case_obj else None
            
            latitude = None
            longitude = None
            accuracy = None
            altitude = None
            captured_address = None
            
            # Extract expected address from candidate profile
            registered_address_str = ""
            if cand_obj:
                if cand_obj.address_details:
                    addr = cand_obj.address_details.get("address") or {}
                    if isinstance(addr, dict):
                        registered_address_str = addr.get("line1", "")
                    else:
                        registered_address_str = str(addr)
                if not registered_address_str:
                    registered_address_str = cand_obj.address or ""
                    
            submitted_address = registered_address_str
            
            # Extract expected coordinates from digital link
            dl = check_record.data.get("digital_link", {}) if check_record.data else {}
            submitted_latitude = dl.get("expected_latitude")
            submitted_longitude = dl.get("expected_longitude")
            distance_meters = None
            v_status = derive_verification_status(check_record, None)
            verified_at = None
            created_at = case_obj.received_date if case_obj else None
            device_info = {}
            photos = []
            case_id = check_record.case_id
            candidate_id = case_obj.candidate_id if case_obj else None
            check_id = check_record.id
            
        # Fetch Audit Logs for this verification
        audit_q = (
            select(models.AuditLog)
            .filter(
                or_(
                    models.AuditLog.resource_id == verification_id,
                    models.AuditLog.resource_id == case_id,
                    models.AuditLog.resource_id == candidate_id
                )
            )
            .order_by(desc(models.AuditLog.timestamp))
            .limit(50)
        )
        audit_res = await db.execute(audit_q)
        audit_logs = audit_res.scalars().all()
        
        # Fetch Verification Logs
        verif_log_q = (
            select(models.VerificationLog)
            .options(joinedload(models.VerificationLog.performer))
            .filter(
                or_(
                    models.VerificationLog.check_id == check_id,
                    models.VerificationLog.case_id == case_id
                )
            )
            .order_by(desc(models.VerificationLog.created_at))
            .limit(50)
        )
        verif_log_res = await db.execute(verif_log_q)
        verif_logs = verif_log_res.scalars().all()
        
        # Build timeline
        timeline = []
        
        if created_at:
            timeline.append({
                "event": "LINK_GENERATED",
                "title": "Verification Link Generated",
                "description": f"Secure address verification link generated for {cand_obj.name if cand_obj else 'candidate'}.",
                "timestamp": created_at.isoformat(),
                "actor": "System"
            })
            
        # Add entries from verification logs
        for l in verif_logs:
            timeline.append({
                "event": l.action,
                "title": l.action.replace("_", " ").title(),
                "description": l.remarks or f"Status changed from {l.old_status} to {l.new_status}.",
                "timestamp": l.created_at.isoformat(),
                "actor": l.performer.full_name if l.performer else "System"
            })
            
        if verified_at:
            timeline.append({
                "event": "COMPLETED",
                "title": "Verification Submitted",
                "description": f"Verification completed. Captured Address: {captured_address}.",
                "timestamp": verified_at.isoformat(),
                "actor": "Candidate"
            })
            
        # Sort timeline by timestamp ascending
        timeline = sorted(timeline, key=lambda x: x["timestamp"])
        
        # Format audit logs
        formatted_audit_logs = [
            {
                "id": log.id,
                "action": log.action,
                "details": log.details,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "actor": "System"
            }
            for log in audit_logs
        ]
        
        # Extract digital_link metadata from check data
        digital_link_meta = {}
        check_data_obj = check_obj.data if check_obj else {}
        if check_data_obj and "digital_link" in check_data_obj:
            digital_link_meta = check_data_obj["digital_link"]

        def _fmt_iso(dt_str):
            if not dt_str:
                return None
            try:
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).strftime("%d %b %Y, %I:%M %p")
            except Exception:
                return dt_str

        digital_token = check_obj.digital_token if check_obj else None
        generated_at_iso = digital_link_meta.get("generated_at")
        expires_at_iso = digital_link_meta.get("expires_at")
        opened_at_iso = digital_link_meta.get("opened_at")
        generated_by_name = digital_link_meta.get("generated_by_name", "System")
        dl_status = digital_link_meta.get("status", "UNUSED")

        # Derive current lifecycle stage
        if not digital_link_meta or not digital_token:
            current_stage = "INITIATED"
        elif verified_at:
            current_stage = "SUBMITTED"
        elif opened_at_iso:
            current_stage = "OPENED"
        elif dl_status in ("LINK_SENT", "SENT"):
            current_stage = "SMS_SENT"
        else:
            current_stage = "LINK_GENERATED"

        return {
            "id": verification_id,
            "checkId": check_id,
            "caseId": case_id,
            "candidateId": cand_obj.client_emp_code if cand_obj and cand_obj.client_emp_code else "—",
            "candidateName": cand_obj.name if cand_obj else "Unknown",
            "candidateEmail": cand_obj.email if cand_obj else "—",
            "candidatePhone": cand_obj.phone if cand_obj else "—",
            "customerName": cust_obj.name if cust_obj else "—",
            # GPS / Location Data
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": accuracy,
            "altitude": altitude,
            "capturedAddress": captured_address or "—",
            "submittedAddress": submitted_address or "—",
            "submittedLatitude": submitted_latitude,
            "submittedLongitude": submitted_longitude,
            "distanceMeters": distance_meters,
            # Status & Lifecycle
            "verificationStatus": v_status,
            "currentStage": current_stage,
            "digitalToken": digital_token,
            # Lifecycle Timestamps
            "generatedAt": _fmt_iso(generated_at_iso),
            "expiresAt": _fmt_iso(expires_at_iso),
            "openedAt": _fmt_iso(opened_at_iso),
            "submittedAt": verified_at.strftime("%d %b %Y, %I:%M %p") if verified_at else None,
            "verifiedAt": verified_at.strftime("%d %b %Y, %I:%M %p") if verified_at else None,
            "createdAt": created_at.strftime("%d %b %Y, %I:%M %p") if created_at else None,
            # Link Metadata
            "generatedByName": generated_by_name,
            "dlStatus": dl_status,
            # Device & Photos
            "deviceInfo": device_info,
            "photos": [
                {
                    "id": p.id,
                    "imageUrl": p.image_url,
                    "photoType": p.photo_type or "live_capture",
                    "latitude": p.latitude,
                    "longitude": p.longitude,
                    "capturedAt": p.captured_at.strftime("%d %b %Y, %I:%M %p") if p.captured_at else None
                }
                for p in photos
            ],
            "timeline": timeline,
            "auditLogs": formatted_audit_logs
        }
        
    except Exception as e:
        logger.error(f"Error fetching verification details: {e}")
        raise HTTPException(500, "Internal Server Error")


@router.get("/change-requests")
async def get_address_change_requests(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Admin endpoint to list all pending address change requests."""
    stmt = (
        select(models.AddressChangeRequest)
        .options(
            joinedload(models.AddressChangeRequest.candidate),
            joinedload(models.AddressChangeRequest.case).joinedload(models.Case.customer)
        )
        .filter(models.AddressChangeRequest.status == "PENDING")
        .order_by(desc(models.AddressChangeRequest.requested_at))
    )
    res = await db.execute(stmt)
    requests = res.scalars().all()
    
    data = []
    for r in requests:
        data.append({
            "id": r.id,
            "candidateName": r.candidate.name if r.candidate else "Unknown",
            "clientName": r.case.customer.name if r.case and r.case.customer else "Unknown",
            "oldAddress": r.old_address,
            "newAddress": r.new_address,
            "distanceMeters": r.distance_meters,
            "reason": r.reason,
            "proofUrls": r.proof_urls,
            "requestedAt": r.requested_at.isoformat() if r.requested_at else None,
            "status": r.status
        })
    return data


@router.post("/change-requests/{request_id}/approve")
async def approve_address_change(
    request_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Approve address change, update master, save history, suspend old link."""
    stmt = select(models.AddressChangeRequest).options(
        selectinload(models.AddressChangeRequest.candidate)
    ).filter(models.AddressChangeRequest.id == request_id)
    res = await db.execute(stmt)
    req = res.scalar_one_or_none()
    
    if not req:
        raise HTTPException(404, "Request not found")
        
    req.status = "APPROVED"
    req.reviewed_at = datetime.utcnow()
    req.reviewed_by = current_user.id
    
    # Update candidate address and save history
    candidate = req.candidate
    if candidate:
        # History
        hist = models.CandidateAddressHistory(
            candidate_id=candidate.id,
            old_address=req.old_address,
            new_address=req.new_address,
            reason=req.reason,
            changed_by=current_user.id
        )
        db.add(hist)
        
        # Update Master
        candidate.address = req.new_address
        if not candidate.address_details:
            candidate.address_details = {}
        candidate.address_details["address"] = {"line1": req.new_address}
        
    # Create audit log
    db.add(models.AuditLog(
        action="ADDRESS_CHANGE_APPROVED",
        resource_id=req.case_id,
        user_id=current_user.id,
        details=f"Address change approved. Candidate's master address updated."
    ))
    
    await db.commit()
    return {"status": "ok", "message": "Address change approved. You can now generate a new link."}


@router.post("/change-requests/{request_id}/reject")
async def reject_address_change(
    request_id: str,
    body: dict,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Reject address change request."""
    remarks = body.get("remarks", "")
    
    stmt = select(models.AddressChangeRequest).filter(models.AddressChangeRequest.id == request_id)
    res = await db.execute(stmt)
    req = res.scalar_one_or_none()
    
    if not req:
        raise HTTPException(404, "Request not found")
        
    req.status = "REJECTED"
    req.remarks = remarks
    req.reviewed_at = datetime.utcnow()
    req.reviewed_by = current_user.id
    
    # Audit log
    db.add(models.AuditLog(
        action="ADDRESS_CHANGE_REJECTED",
        resource_id=req.case_id,
        user_id=current_user.id,
        details=f"Address change rejected. Reason: {remarks}"
    ))
    
    await db.commit()
    return {"status": "ok", "message": "Request rejected"}


@router.get("/dashboard-stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get stats for dashboard widgets."""
    today = datetime.utcnow().date()
    
    # Pending requests
    pending_stmt = select(func.count(models.AddressChangeRequest.id)).filter(models.AddressChangeRequest.status == "PENDING")
    pending_count = await db.scalar(pending_stmt)
    
    # Approved today
    approved_stmt = select(func.count(models.AddressChangeRequest.id)).filter(
        models.AddressChangeRequest.status == "APPROVED",
        func.date(models.AddressChangeRequest.reviewed_at) == today
    )
    approved_count = await db.scalar(approved_stmt)
    
    # Rejected today
    rejected_stmt = select(func.count(models.AddressChangeRequest.id)).filter(
        models.AddressChangeRequest.status == "REJECTED",
        func.date(models.AddressChangeRequest.reviewed_at) == today
    )
    rejected_count = await db.scalar(rejected_stmt)
    
    return {
        "pendingRequests": pending_count or 0,
        "approvedToday": approved_count or 0,
        "rejectedToday": rejected_count or 0
    }

