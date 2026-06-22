from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, File, UploadFile, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from . import models, schemas, aws_utils
from .database import get_async_db
from .auth_routes import check_module_permission, get_current_user
from . import notification_utils
import uuid
from datetime import datetime


router = APIRouter(
    prefix="/verifications",
    tags=["verifications"]
)

def enrich_check(check: models.VerificationCheck) -> models.VerificationCheck:
    """Populates virtual fields for response schemas."""
    case_obj = check.case
    if case_obj:
        check.case_ref = case_obj.case_ref_no
        if case_obj.candidate:
            check.candidate_name = case_obj.candidate.name
            # Handle given_address enrichment
            addr_data = ""
            if case_obj.candidate.address_details:
                if "address" in case_obj.candidate.address_details:
                    addr_data = str(case_obj.candidate.address_details["address"])
                elif "addresses" in case_obj.candidate.address_details and case_obj.candidate.address_details["addresses"]:
                    first = case_obj.candidate.address_details["addresses"][0]
                    addr_data = str(first.get("address", first))
            check.given_address = addr_data or (case_obj.candidate.address or "")
            
        if case_obj.customer:
            check.customer_name = case_obj.customer.name
            

    return check

@router.post("/checks", response_model=schemas.VerificationCheck, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def create_verification_check(check: schemas.VerificationCheckCreate, db: AsyncSession = Depends(get_async_db)):
    db_check = models.VerificationCheck(**check.dict())
    db.add(db_check)
    await db.commit()
    await db.refresh(db_check)
    
    # Reload with relations for enrichment
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate),
        selectinload(models.VerificationCheck.case).selectinload(models.Case.customer),
        selectinload(models.VerificationCheck.documents).selectinload(models.VerificationDocument.uploader),
        selectinload(models.VerificationCheck.logs).selectinload(models.VerificationLog.performer),
        selectinload(models.VerificationCheck.assigned_verifier),
        selectinload(models.VerificationCheck.finalized_user)
    ).filter(models.VerificationCheck.id == db_check.id)
    res = await db.execute(stmt)
    db_check = res.scalar_one()
    
    return enrich_check(db_check)

@router.get("/checks", response_model=List[schemas.VerificationCheck], dependencies=[Depends(check_module_permission("bvs", "verification", action="read"))])
async def read_verification_checks(case_id: Optional[str] = None, type: Optional[str] = None, db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate),
        selectinload(models.VerificationCheck.case).selectinload(models.Case.customer),
        selectinload(models.VerificationCheck.documents).selectinload(models.VerificationDocument.uploader),
        selectinload(models.VerificationCheck.logs).selectinload(models.VerificationLog.performer),
        selectinload(models.VerificationCheck.assigned_verifier),
        selectinload(models.VerificationCheck.finalized_user)
    )
    if case_id:
        stmt = stmt.filter(models.VerificationCheck.case_id == case_id)
    if type:
        stmt = stmt.filter(models.VerificationCheck.check_type.ilike(f"%{type}%"))
    
    res = await db.execute(stmt)
    results = res.scalars().all()
    
    return [enrich_check(c) for c in results]

@router.patch("/checks/{check_id}", response_model=schemas.VerificationCheck, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def update_verification_check(check_id: str, check_update: schemas.VerificationCheckUpdate, db: AsyncSession = Depends(get_async_db)):
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate),
        selectinload(models.VerificationCheck.case).selectinload(models.Case.customer),
        selectinload(models.VerificationCheck.documents).selectinload(models.VerificationDocument.uploader),
        selectinload(models.VerificationCheck.logs).selectinload(models.VerificationLog.performer),
        selectinload(models.VerificationCheck.assigned_verifier),
        selectinload(models.VerificationCheck.finalized_user)
    ).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    db_check = res.scalar_one_or_none()
    
    if db_check is None:
        raise HTTPException(status_code=404, detail="Check not found")
    
    update_data = check_update.dict(exclude_unset=True)
    if update_data.get("status") == "QC_PENDING":
        final_res = update_data.get("final_result") or db_check.final_result
        if final_res:
            val = final_res.value if hasattr(final_res, "value") else str(final_res)
            if "." in val:
                val = val.split(".")[-1]
            new_status = val.upper()
            update_data["status"] = new_status
        else:
            update_data["status"] = "QC_VERIFIED"

    for key, value in update_data.items():
        setattr(db_check, key, value)
    
    await db.commit()
    
    # Reload with relations for enrichment (avoids MissingGreenlet after refresh)
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate),
        selectinload(models.VerificationCheck.case).selectinload(models.Case.customer),
        selectinload(models.VerificationCheck.documents).selectinload(models.VerificationDocument.uploader),
        selectinload(models.VerificationCheck.logs).selectinload(models.VerificationLog.performer),
        selectinload(models.VerificationCheck.assigned_verifier),
        selectinload(models.VerificationCheck.finalized_user)
    ).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    db_check = res.scalar_one()
    
    return enrich_check(db_check)

@router.patch("/checks/{check_id}/generate-link", response_model=schemas.VerificationCheck, dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def generate_verification_link(
    check_id: str, 
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    import secrets
    from datetime import datetime, timedelta
    from . import email_utils
    from sqlalchemy.orm.attributes import flag_modified
    
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate),
        selectinload(models.VerificationCheck.case).selectinload(models.Case.customer),
        selectinload(models.VerificationCheck.documents).selectinload(models.VerificationDocument.uploader),
        selectinload(models.VerificationCheck.logs).selectinload(models.VerificationLog.performer),
        selectinload(models.VerificationCheck.assigned_verifier),
        selectinload(models.VerificationCheck.finalized_user)
    ).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    db_check = res.scalar_one_or_none()
    
    if db_check is None:
        raise HTTPException(status_code=404, detail="Check not found")
        
    # Generate secure 32-byte cryptographically random token
    token = secrets.token_urlsafe(32)
    db_check.digital_token = token
    
    # Store token metadata in check.data
    expires_at = datetime.utcnow() + timedelta(hours=24)
    if not db_check.data:
        db_check.data = {}
    
    # Fetch registered address details if available to seed coordinates
    candidate = db_check.case.candidate if db_check.case else None
    expected_lat = None
    expected_lng = None
    if candidate and candidate.address_details:
        expected_lat = candidate.address_details.get("latitude")
        expected_lng = candidate.address_details.get("longitude")
        
    db_check.data["digital_link"] = {
        "expires_at": expires_at.isoformat(),
        "candidate_id": candidate.id if candidate else None,
        "case_id": db_check.case_id,
        "status": "UNUSED",
        "expected_latitude": expected_lat,
        "expected_longitude": expected_lng
    }
    flag_modified(db_check, "data")
    
    # Audit log
    audit_log = models.AuditLog(
        user_id=current_user.id,
        action="LINK_GENERATED",
        resource_id=db_check.case_id,
        details=f"Secure digital address verification link generated for Check ID {check_id}. Link expires in 24 hours."
    )
    db.add(audit_log)
    await db.commit()
    
    # Dispatch outreach messages via BackgroundTasks
    if candidate:
        origin = request.headers.get("origin") or "http://localhost:5173"
        verification_link = f"{origin}/verify/{token}"
        
        # Send Email
        if candidate.email:
            background_tasks.add_task(
                email_utils.send_digital_address_verification_email,
                candidate.email,
                candidate.name,
                verification_link
            )
            
        # Send SMS & WhatsApp Mock
        if candidate.phone:
            async def log_outreach_mock(phone: str, candidate_name: str, link: str):
                import os
                sms_log_path = r"d:\project\backend\scratch\sent_sms.log"
                wa_log_path = r"d:\project\backend\scratch\sent_whatsapp.log"
                os.makedirs(os.path.dirname(sms_log_path), exist_ok=True)
                
                sms_message = f"Dear {candidate_name}, please complete your Address Verification using this secure live-location link: {link} (Expires in 24h)"
                with open(sms_log_path, "a") as f:
                    f.write(f"[{datetime.now().isoformat()}] TO: {phone} | MESSAGE: {sms_message}\n")
                print(f"\n🚀 [SMS OUTREACH] To: {phone} | Msg: {sms_message}\n", flush=True)
                
                wa_message = f"Hello {candidate_name}, this is from BGVMS. Please complete your digital address verification by clicking the link: {link}"
                with open(wa_log_path, "a") as f:
                    f.write(f"[{datetime.now().isoformat()}] TO: {phone} | MESSAGE: {wa_message}\n")
                print(f"🚀 [WHATSAPP OUTREACH] To: {phone} | Msg: {wa_message}\n", flush=True)
                
            background_tasks.add_task(log_outreach_mock, candidate.phone, candidate.name, verification_link)

    # Reload with relations for enrichment
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate),
        selectinload(models.VerificationCheck.case).selectinload(models.Case.customer),
        selectinload(models.VerificationCheck.documents).selectinload(models.VerificationDocument.uploader),
        selectinload(models.VerificationCheck.logs).selectinload(models.VerificationLog.performer),
        selectinload(models.VerificationCheck.assigned_verifier),
        selectinload(models.VerificationCheck.finalized_user)
    ).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    db_check = res.scalar_one()
    
    return enrich_check(db_check)

@router.patch("/checks/{check_id}/mark-link-sent", dependencies=[Depends(check_module_permission("bvs", "verification", action="write"))])
async def mark_digital_link_sent(
    check_id: str,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Track which communication channel (sms/whatsapp/email) was used to share the digital verification link."""
    from sqlalchemy.orm.attributes import flag_modified
    from datetime import datetime

    stmt = select(models.VerificationCheck).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    db_check = res.scalar_one_or_none()
    if db_check is None:
        raise HTTPException(status_code=404, detail="Check not found")

    channel = payload.get("channel", "unknown")  # sms, whatsapp, email

    if not db_check.data:
        db_check.data = {}
    if "digital_link" not in db_check.data:
        db_check.data["digital_link"] = {}

    channels_sent = db_check.data["digital_link"].get("channels_sent", [])
    channels_sent.append({
        "channel": channel,
        "sent_at": datetime.utcnow().isoformat(),
        "sent_by": current_user.full_name or current_user.email
    })
    db_check.data["digital_link"]["channels_sent"] = channels_sent
    db_check.data["digital_link"]["status"] = "LINK_SENT"
    flag_modified(db_check, "data")

    # Audit log
    db.add(models.AuditLog(
        user_id=current_user.id,
        action="LINK_SENT",
        resource_id=db_check.case_id,
        details=f"Digital verification link sent via {channel.upper()} by {current_user.full_name or current_user.email}"
    ))
    await db.commit()
    return {"status": "ok", "channel": channel, "message": f"Link marked as sent via {channel}"}

@router.get("/public/{token}", response_model=Dict[str, Any])
async def get_public_verification(token: str, db: AsyncSession = Depends(get_async_db)):
    from datetime import datetime
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate)
    ).filter(models.VerificationCheck.digital_token == token)
    res = await db.execute(stmt)
    db_check = res.scalar_one_or_none()
    
    if db_check is None:
        raise HTTPException(status_code=404, detail="Invalid or expired verification link.")
        
    digital_link = db_check.data.get("digital_link") if db_check.data else None
    if not digital_link:
        raise HTTPException(status_code=400, detail="Malformed verification token metadata.")
        
    # Check Expiration (24-hour limit)
    expires_at_str = digital_link.get("expires_at")
    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str)
        if datetime.utcnow() > expires_at:
            raise HTTPException(status_code=400, detail="Verification link has expired (24-hour validity exceeded).")
            
    # Check Single-Use
    if digital_link.get("status") == "USED" or db_check.status in [models.CheckStatus.QC_PENDING, models.CheckStatus.QC_VERIFIED]:
        raise HTTPException(status_code=400, detail="Verification link has already been used.")
        
    # Audit trail logging
    audit = models.AuditLog(
        action="LINK_OPENED",
        resource_id=db_check.case_id,
        details=f"Address verification link opened. Candidate: {db_check.case.candidate.name if db_check.case and db_check.case.candidate else 'Unknown'}."
    )
    db.add(audit)
    await db.commit()
    
    case_obj = db_check.case
    candidate = case_obj.candidate if case_obj else None
    if not candidate:
        raise HTTPException(status_code=400, detail="Candidate not found for this check.")
    
    # Resolve given address with fallbacks
    given_addr = {}
    if candidate.address_details:
        if "address" in candidate.address_details:
            given_addr = candidate.address_details["address"]
        elif "addresses" in candidate.address_details and candidate.address_details["addresses"]:
            first = candidate.address_details["addresses"][0]
            given_addr = first.get("address", first)
            
    if not given_addr and candidate.address:
        given_addr = {"line1": candidate.address}

    return {
        "check_id": db_check.id,
        "candidate_id": candidate.id,
        "case_id": case_obj.id,
        "candidate_name": candidate.name,
        "check_type": db_check.check_type,
        "given_address": given_addr,
        "expected_latitude": digital_link.get("expected_latitude") or db_check.data.get("expected_latitude"),
        "expected_longitude": digital_link.get("expected_longitude") or db_check.data.get("expected_longitude")
    }

@router.post("/public/{token}")
async def submit_public_verification(
    token: str, 
    submission: Dict[str, Any], 
    background_tasks: BackgroundTasks, 
    db: AsyncSession = Depends(get_async_db)
):
    import hashlib
    import base64
    import math
    from datetime import datetime
    from . import aws_utils
    from sqlalchemy.orm.attributes import flag_modified
    
    # 1. Fetch check and validate token
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case).selectinload(models.Case.candidate)
    ).filter(models.VerificationCheck.digital_token == token)
    res = await db.execute(stmt)
    db_check = res.scalar_one_or_none()
    
    if db_check is None:
        raise HTTPException(status_code=404, detail="Invalid or expired verification link.")
        
    digital_link = db_check.data.get("digital_link") if db_check.data else None
    if not digital_link or digital_link.get("status") == "USED":
        raise HTTPException(status_code=400, detail="Verification link has already been used.")
        
    # Enforce Expiry (24 hours)
    expires_at_str = digital_link.get("expires_at")
    if expires_at_str:
        if datetime.utcnow() > datetime.fromisoformat(expires_at_str):
            raise HTTPException(status_code=400, detail="Verification link has expired.")
            
    # 2. Extract submission details
    lat = submission.get("latitude")
    lng = submission.get("longitude")
    accuracy = submission.get("accuracy")
    altitude = submission.get("altitude")
    photo_base64 = submission.get("photo") # base64 data URL
    device_info = submission.get("device_info", {})
    captured_address = submission.get("captured_address", "")
    
    candidate = db_check.case.candidate if db_check.case else None
    
    # 3. Quality & Spoofing Validations
    if device_info.get("webdriver"):
        raise HTTPException(status_code=400, detail="Verification Failed: Browser automation detected. Live capture required.")
    if device_info.get("is_mocked"):
        raise HTTPException(status_code=400, detail="Verification Failed: Location emulator detected. Live location required.")
    if device_info.get("is_rooted") or device_info.get("jailbroken"):
        raise HTTPException(status_code=400, detail="Verification Failed: Rooted/Jailbroken device status detected. Submission blocked.")
        
    # Image Hashing & Duplication check
    if not photo_base64 or "," not in photo_base64:
        raise HTTPException(status_code=400, detail="Verification Failed: Geotagged camera capture is mandatory.")
        
    header, encoded = photo_base64.split(",", 1)
    image_bytes = base64.b64decode(encoded)
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    
    # Uniqueness check
    dup_stmt = select(models.AddressVerificationPhoto).filter(models.AddressVerificationPhoto.file_hash == image_hash)
    dup_res = await db.execute(dup_stmt)
    if dup_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Verification Failed: Duplicate image hash found. Live capture required.")
        
    # 4. Upload photo to S3
    class BytesFile:
        def __init__(self, content: bytes, content_type: str = "image/jpeg"):
            self.content = content
            self.content_type = content_type
        async def read(self):
            return self.content
            
    filename = f"digital_address_{db_check.id}_{int(datetime.utcnow().timestamp())}.jpg"
    s3_path = f"evidence/{db_check.id}/{filename}"
    file_wrapper = BytesFile(image_bytes, "image/jpeg")
    
    uploaded_path = await aws_utils.upload_to_s3(file_wrapper, s3_path)
    file_url = await aws_utils.generate_presigned_url(uploaded_path)
    
    # 5. Geolocation Math: Distance calculation (registered address vs captured coordinates)
    expected_lat = digital_link.get("expected_latitude") or db_check.data.get("expected_latitude")
    expected_lng = digital_link.get("expected_longitude") or db_check.data.get("expected_longitude")
    
    # Check if we can extract expected coordinates from candidate address details directly
    if not expected_lat or not expected_lng:
        if candidate and candidate.address_details:
            expected_lat = candidate.address_details.get("latitude")
            expected_lng = candidate.address_details.get("longitude")
            
    distance = None
    verification_status = "PENDING"
    risk_flags = []
    
    if expected_lat and expected_lng and lat and lng:
        # Haversine distance
        R = 6371000 # meters
        phi1, phi2 = math.radians(lat), math.radians(expected_lat)
        dphi = math.radians(expected_lat - lat)
        dlambda = math.radians(expected_lng - lng)
        a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
        distance = 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        if distance <= 100:
            verification_status = "VERIFIED"
        else:
            verification_status = "ADDRESS_MISMATCH"
            risk_flags.append("Location Mismatch")
            
    # Fetch candidate registered address string
    registered_address_str = ""
    if candidate:
        if candidate.address_details:
            addr = candidate.address_details.get("address") or {}
            if isinstance(addr, dict):
                registered_address_str = addr.get("line1", "")
            else:
                registered_address_str = str(addr)
        if not registered_address_str:
            registered_address_str = candidate.address or ""
            
    # 6. Database storage updates
    # Create AddressVerification row
    verif = models.AddressVerification(
        candidate_id=db_check.case.candidate_id,
        case_id=db_check.case_id,
        check_id=db_check.id,
        latitude=lat,
        longitude=lng,
        accuracy=accuracy,
        altitude=altitude,
        captured_address=captured_address or f"Coordinates: {lat}, {lng}",
        submitted_address=registered_address_str,
        submitted_latitude=expected_lat,
        submitted_longitude=expected_lng,
        distance_meters=distance,
        verification_status=verification_status,
        verified_at=datetime.utcnow(),
        risk_score=50 if verification_status == "ADDRESS_MISMATCH" else 0,
        risk_flags=risk_flags,
        device_info=device_info
    )
    db.add(verif)
    await db.flush() # Get verif.id
    
    # Create Photo row
    photo = models.AddressVerificationPhoto(
        verification_id=verif.id,
        image_url=file_url,
        s3_key=uploaded_path,
        photo_type="selfie",
        latitude=lat,
        longitude=lng,
        captured_at=datetime.utcnow(),
        watermark_text=f"Lat: {lat}, Lng: {lng}, Acc: {accuracy}m, Time: {datetime.utcnow().isoformat()}",
        file_hash=image_hash
    )
    db.add(photo)
    
    # 7. Update check.data and status for verifier workspace compatibility
    if not db_check.data:
        db_check.data = {}
        
    db_check.data["digital_data"] = {
        "line1": submission.get("line1", ""),
        "city": submission.get("city", ""),
        "pincode": submission.get("pincode", ""),
        "duration": submission.get("duration", ""),
        "photo": file_url,
        "location": {
            "lat": lat,
            "lng": lng,
            "acc": accuracy
        },
        "distance": distance,
        "status": verification_status
    }
    
    # Mark token as USED
    db_check.data["digital_link"]["status"] = "USED"
    
    # Mark check status to VERIFICATION (ready for verifier audit review)
    db_check.status = models.CheckStatus.VERIFICATION
    db_check.verifier_remarks = f"Digital Address submitted by candidate. Status: {verification_status}."
    
    flag_modified(db_check, "data")
    
    # Audit Logs
    audit_permissions = models.AuditLog(
        action="LOCATION_GRANTED",
        resource_id=db_check.case_id,
        details="Live location access granted by candidate."
    )
    audit_camera = models.AuditLog(
        action="CAMERA_GRANTED",
        resource_id=db_check.case_id,
        details="Camera access granted by candidate."
    )
    audit_photo = models.AuditLog(
        action="PHOTO_CAPTURED",
        resource_id=db_check.case_id,
        details="Live camera photo successfully captured by candidate."
    )
    audit_gps = models.AuditLog(
        action="GPS_CAPTURED",
        resource_id=db_check.case_id,
        details=f"Live GPS coordinates captured: {lat}, {lng} (Accuracy: {accuracy}m)."
    )
    audit_geotag = models.AuditLog(
        action="GEOTAG_CREATED",
        resource_id=db_check.case_id,
        details="Geotag watermark embedded into the photo canvas."
    )
    audit_submit = models.AuditLog(
        action="SUBMITTED",
        resource_id=db_check.case_id,
        details=f"Digital address verification form successfully submitted. Status: {verification_status}."
    )
    
    db.add_all([audit_permissions, audit_camera, audit_photo, audit_gps, audit_geotag, audit_submit])
    
    # Notify verifier if assigned
    if db_check.case and db_check.case.assigned_to:
        await notification_utils.create_notification(
            db, db_check.case.assigned_to,
            "Digital Form Submitted",
            f"Candidate has submitted digital address verification for Case {db_check.case.case_ref_no}.",
            models.NotificationCategory.FORM_SUBMITTED,
            case_id=db_check.case_id,
            background_tasks=background_tasks
        )
        
    await db.commit()
    
    return {"status": "success", "message": "Verification submitted successfully", "verification_status": verification_status, "distance": distance}
    
@router.post("/checks/{check_id}/upload")
async def upload_verification_document(
    check_id: str, 
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Uploads evidence to S3 and registers it in the database."""
    stmt = select(models.VerificationCheck).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    check = res.scalar_one_or_none()
    if not check:
        raise HTTPException(404, detail="Verification check not found")

    # Upload to S3
    ext = file.filename.split('.')[-1]
    s3_path = f"evidence/{check_id}/{uuid.uuid4()}.{ext}"
    uploaded_path = await aws_utils.upload_to_s3(file, s3_path)
    
    # Get Public/Presigned URL
    file_url = await aws_utils.generate_presigned_url(uploaded_path)
    
    # Save to DB
    doc = models.VerificationDocument(
        check_id=check_id,
        file_name=file.filename,
        file_url=file_url,
        file_type=file.content_type,
        s3_key=uploaded_path,
        uploaded_by_id=current_user.id,
        is_primary=False # Default to false on upload
    )
    db.add(doc)
    
    # Log Action
    log = models.VerificationLog(
        case_id=check.case_id,
        check_id=check_id,
        action="DOCUMENT_UPLOADED",
        performed_by_id=current_user.id,
        remarks=f"Evidence document '{file.filename}' uploaded."
    )
    db.add(log)
    
    await db.commit()
    await db.refresh(doc)
    
    return doc

class RegisterDocumentRequest(schemas.BaseModel):
    file_name: str
    file_type: str
    s3_key: str
    file_url: str

@router.post("/checks/{check_id}/register-document")
async def register_uploaded_document(
    check_id: str,
    req: RegisterDocumentRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Registers an ALREADY-uploaded S3 artifact (via pre-signed PUT) to this specific check audits."""
    stmt = select(models.VerificationCheck).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    check = res.scalar_one_or_none()
    if not check:
        raise HTTPException(404, detail="Check target not found")

    # Save metadata reference
    doc = models.VerificationDocument(
        check_id=check_id,
        file_name=req.file_name,
        file_url=req.file_url,
        file_type=req.file_type,
        s3_key=req.s3_key,
        uploaded_by_id=current_user.id,
        is_primary=False
    )
    db.add(doc)
    
    # Log standard audit hook
    log = models.VerificationLog(
        case_id=check.case_id,
        check_id=check_id,
        action="DOCUMENT_UPLOADED",
        performed_by_id=current_user.id,
        remarks=f"External evidence source '{req.file_name}' registered securely."
    )
    db.add(log)
    
    await db.commit()
    await db.refresh(doc)
    return doc

@router.patch("/checks/{check_id}/status-ops")
async def update_check_status_ops(
    check_id: str,
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Updates status with granular logging and remarks."""
    stmt = select(models.VerificationCheck).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    check = res.scalar_one_or_none()
    if not check:
        raise HTTPException(404, detail="Verification check not found")

    old_status = check.status
    new_status = data.get("status")
    remarks = data.get("remarks")
    confidence = data.get("confidence_score")
    
    if new_status: check.status = new_status
    if remarks: check.verifier_remarks = remarks
    if confidence is not None: check.confidence_score = confidence
    
    if new_status and new_status != old_status:
        check.verified_date = datetime.utcnow()
        
    # Log the operation
    log = models.VerificationLog(
        case_id=check.case_id,
        check_id=check_id,
        action="STATUS_UPDATED",
        performed_by_id=current_user.id,
        old_status=old_status,
        new_status=new_status,
        remarks=remarks or f"Status changed from {old_status} to {new_status}"
    )
    db.add(log)
    
    await db.commit()
    return {"status": "success", "new_status": new_status}

@router.post("/checks/{check_id}/qc-issues", response_model=schemas.QCFieldIssueRead)
async def raise_qc_issue(
    check_id: str,
    issue: schemas.QCFieldIssueCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Raise a granular QC discrepancy on a specific field."""
    stmt = select(models.VerificationCheck).options(
        selectinload(models.VerificationCheck.case)
    ).filter(models.VerificationCheck.id == check_id)
    res = await db.execute(stmt)
    check = res.scalar_one_or_none()
    if not check:
        raise HTTPException(404, detail="Check not found")

    # If assignee not provided, default to the verifier who worked on the check
    assignee_id = issue.assigned_to or check.assigned_verifier_id or check.case.assigned_to

    db_issue = models.QCFieldIssue(
        case_id=check.case_id,
        check_id=check_id,
        field_name=issue.field_name,
        issue_type=issue.issue_type,
        comment=issue.comment,
        raised_by=current_user.id,
        assigned_to=assignee_id,
        status=models.QCIssueStatus.OPEN
    )
    db.add(db_issue)
    
    # Update check status to signify it has open issues
    check.qc_status = "REJECTED" # Or similar
    
    # Log the operation
    log = models.VerificationLog(
        case_id=check.case_id,
        check_id=check_id,
        action="QC_ISSUE_RAISED",
        performed_by_id=current_user.id,
        remarks=f"QC Query raised on field '{issue.field_name}': {issue.issue_type}"
    )
    db.add(log)
    
    # Notify the assignee
    if assignee_id:
        await notification_utils.create_notification(
            db, assignee_id,
            "QC Query Raised",
            f"QC has raised a query on {check.check_type} - {issue.field_name}.",
            models.NotificationCategory.SYSTEM_ALERT,
            case_id=check.case_id,
            background_tasks=background_tasks
        )

    await db.commit()
    await db.refresh(db_issue)
        
    return db_issue

@router.get("/checks/{check_id}/qc-issues", response_model=List[schemas.QCFieldIssueRead])
async def get_check_qc_issues(check_id: str, db: AsyncSession = Depends(get_async_db)):
    """Fetch all QC issues for a specific check."""
    stmt = select(models.QCFieldIssue).options(
        selectinload(models.QCFieldIssue.raiser),
        selectinload(models.QCFieldIssue.assignee)
    ).filter(models.QCFieldIssue.check_id == check_id)
    res = await db.execute(stmt)
    issues = res.scalars().all()
    
    # Map names for response
    for issue in issues:
        issue.raised_by_name = issue.raiser.full_name if issue.raiser else "Unknown"
        issue.assigned_to_name = issue.assignee.full_name if issue.assignee else "Unassigned"
        
    return issues

@router.patch("/qc-issues/{issue_id}/resolve")
async def resolve_qc_issue(
    issue_id: str,
    resolve_data: schemas.QCFieldIssueResolve,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Mark a QC issue as resolved."""
    stmt = select(models.QCFieldIssue).filter(models.QCFieldIssue.id == issue_id)
    res = await db.execute(stmt)
    issue = res.scalar_one_or_none()
    if not issue:
        raise HTTPException(404, detail="Issue not found")
        
    issue.status = models.QCIssueStatus.RESOLVED
    issue.resolved_at = datetime.utcnow()
    if resolve_data.comment:
        issue.comment = (issue.comment or "") + f"\n\nResolution: {resolve_data.comment}"
        
    # Log the resolution
    log = models.VerificationLog(
        case_id=issue.case_id,
        check_id=issue.check_id,
        action="QC_ISSUE_RESOLVED",
        performed_by_id=current_user.id,
        remarks=f"QC Query for field '{issue.field_name}' marked as resolved."
    )
    db.add(log)
    
    await db.commit()
    return {"status": "success", "message": "Issue resolved"}

@router.patch("/documents/{doc_id}/primary")
async def toggle_document_primary(
    doc_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: models.User = Depends(get_current_user)
):
    """Toggles the 'Primary Evidence' flag for a document."""
    stmt = select(models.VerificationDocument).filter(models.VerificationDocument.id == doc_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, detail="Document not found")
    
    # Toggle logic
    doc.is_primary = not doc.is_primary
    
    await db.commit()
    await db.refresh(doc)
    return doc

