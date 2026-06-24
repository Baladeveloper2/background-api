import os
import sys
import logging
import asyncio
from datetime import datetime
from sqlalchemy import select
from .celery_app import celery_app
from io import BytesIO
import boto3
from dotenv import load_dotenv
import time
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
from sqlalchemy.orm.attributes import flag_modified
from .database import SessionLocal, AsyncSessionLocal
from . import models, aws_utils
from .notification_utils import create_notification
from .enums import NotificationCategory

load_dotenv()

logger = logging.getLogger("celery_worker")
logger.setLevel(logging.INFO)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip('/')

@celery_app.task(bind=True, max_retries=2, name="app.worker.generate_case_pdf")
def generate_case_pdf(self, case_id: str, user_token: str, custom_frontend_url: str = None):
    """
    Orchestrates a headless browser session to navigate to the exact React ReportView page,
    authenticates via direct localStorage injection, renders a pixel-perfect PDF, 
    and streams resultant binary directly to AWS S3.
    """
    if not sync_playwright:
        logger.error("Playwright library is not installed/available. Cannot generate PDF report.")
        raise RuntimeError("Playwright is not installed on this host environment. Headless PDF generation is disabled.")

    base_url = custom_frontend_url or FRONTEND_URL
    report_url = f"{base_url}/report/{case_id}" 

    logger.info(f"LAUNCH: Pixel-Perfect Headless Render started for Case={case_id}")
    
    try:
        with sync_playwright() as p:
            # Launch lightweight headless runtime
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            
            # Emulate print media and desktop dimension for perfect scaling
            context = browser.new_context(
                viewport={'width': 1200, 'height': 1600},
                user_agent='Mozilla/5.0 ChecklinePDFRenderer/1.0'
            )
            
            page = context.new_page()
            
            # Seed localStorage with the triggering user's credentials instantly.
            # First, navigate to target domain briefly to establish origin, then inject.
            page.goto(f"{base_url}/login")
            page.evaluate(f"window.localStorage.setItem('token', '{user_token}');")
            
            logger.info(f"TRANSIT: Authenticated. Navigating to report...")
            
            # Navigate to dynamic view, set networkidle to await asset rendering (seals, logos)
            page.goto(report_url, wait_until="networkidle")
            
            # Allow subtle final script triggers to complete, then emit vector binary
            time.sleep(2) 
            
            logger.info("CAPTURE: Generating raw print binary streams...")
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                margin={"top": "0px", "bottom": "0px", "left": "0px", "right": "0px"}
            )
            
            browser.close()
        
        logger.info(f"TRANSPORT: Streaming {len(pdf_bytes)} bytes to AWS storage.")
        
        # S3 Pipe
        s3 = boto3.client(
            's3',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION")
        )
        
        bucket = os.getenv("AWS_S3_BUCKET")
        timestamp = int(time.time())
        s3_key = f"generated_reports/{case_id}_report_{timestamp}.pdf"
        
        s3.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=pdf_bytes,
            ContentType='application/pdf',
            ContentDisposition=f'inline; filename="case_report_{case_id}.pdf"'
        )
        
        file_url = f"https://{bucket}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/{s3_key}"
        
        logger.info(f"FINALIZED: Report persisted at {file_url}. Committing linkage to operational store...")
        
        # --- DATABASE PERSISTENCE LAYER ---
        # Create dedicated transaction context for asynchronous persistent store commit
        db = SessionLocal()
        try:
            c = db.query(models.Case).filter(models.Case.id == case_id).first()
            if c and c.candidate:
                cand = c.candidate
                current_docs = list(cand.documents) if cand.documents else []
                
                # Create structural pointer entity identical to standardized artifact storage schema
                final_report_entry = {
                    "original_filename": f"Case_Report_{c.case_ref_no}.pdf",
                    "name": f"Background Report - {c.case_ref_no}",
                    "url": file_url,
                    "path": s3_key,
                    "mimetype": "application/pdf",
                    "check_type": "Final Report",
                    "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
                
                current_docs.append(final_report_entry)
                cand.documents = current_docs
                # Force flag attribute mutation for dynamic column types explicitly
                flag_modified(cand, "documents")
                
                db.commit()
                logger.info("PERSISTENCE SUCCESS: Artifact explicitly appended to candidate vault.")
                
                # Notify customer users asynchronously
                if c.customer_id:
                    case_id_val = c.id
                    cust_id_val = c.customer_id
                    ref_no_val = c.case_ref_no
                    cand_name_val = c.candidate.name if c.candidate else "Unknown"
                    
                    async def async_notify():
                        async with AsyncSessionLocal() as adb:
                            res = await adb.execute(select(models.User).filter(models.User.customer_id == cust_id_val))
                            customer_users = res.scalars().all()
                            for u in customer_users:
                                await create_notification(
                                    adb, u.id, 
                                    "Final Report Ready", 
                                    f"The final verification report for {ref_no_val} ({cand_name_val}) has been generated and is ready to download.",
                                    NotificationCategory.QC_REPORT_READY, 
                                    case_id=case_id_val
                                )
                            await adb.commit()
                    
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.ensure_future(async_notify())
                        else:
                            loop.run_until_complete(async_notify())
                    except RuntimeError:
                        asyncio.run(async_notify())
                        
            else:
                logger.warning(f"PERSISTENCE ABORT: Case or Candidate not locatable for ID {case_id}")
        except Exception as db_err:
            logger.error(f"PERSISTENCE FAULT during lifecycle callback: {str(db_err)}")
            db.rollback()
        finally:
            db.close()

        return {
            "status": "SUCCESS",
            "case_id": case_id,
            "s3_key": s3_key,
            "url": file_url
        }

    except Exception as e:
        logger.error(f"CRITICAL RENDER ABORT: {str(e)}")
        raise self.retry(exc=e, countdown=15)


@celery_app.task(name="app.worker.process_ocr_document_task")
def process_ocr_document_task(job_id: str):
    import requests
    from .idp.engine import get_idp_engine
    from .ocr_utils import check_duplicate_records
    from .ws import manager
    import asyncio
    
    logger.info(f"OCR TASK: Started processing job {job_id}")
    
    db = SessionLocal()
    try:
        job = db.query(models.OcrExtraction).filter(models.OcrExtraction.id == job_id).first()
        if not job:
            logger.error(f"OCR TASK: Job {job_id} not found in database.")
            return
            
        # 1. Fetch settings from DB
        settings = {}
        for s in db.query(models.SystemSetting).all():
            settings[s.key] = s.value.lower() == "true"
            
        enable_ocr = settings.get("enable_ocr", True)
        enable_ai_validation = settings.get("enable_ai_validation", True)
        enable_fraud_detection = settings.get("enable_fraud_detection", True)
        
        # Async broadcast helper
        def broadcast_progress(status: str, progress: int, doc_type: str = "Unknown", extra: dict = None):
            msg = {
                "type": "OCR_PROGRESS",
                "job_id": job_id,
                "status": status,
                "progress": progress,
                "document_type": doc_type
            }
            if extra:
                msg.update(extra)
            try:
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(manager.broadcast(msg), loop)
                else:
                    loop.run_until_complete(manager.broadcast(msg))
            except Exception as e:
                logger.warning(f"Failed to broadcast websocket progress: {e}")

        # If OCR is disabled, skip processing
        if not enable_ocr:
            job.ocr_status = "COMPLETED"
            job.ocr_progress = 100
            db.commit()
            broadcast_progress("COMPLETED", 100)
            return

        # Start timer
        job.ocr_started_at = datetime.utcnow()

        # Update to Loading OCR Engine (10%)
        job.ocr_status = "QUEUED"
        job.ocr_progress = 10
        db.commit()
        broadcast_progress("Loading OCR Engine", 10)

        # 2. Download the document
        try:
            s3_key = job.s3_key
            if not s3_key and job.file_url:
                from urllib.parse import urlparse
                parsed = urlparse(job.file_url)
                path = parsed.path.lstrip('/')
                s3_key = path

            if s3_key and aws_utils.s3_client:
                logger.info(f"OCR TASK: Downloading via direct S3 Client: {s3_key}")
                s3_response = aws_utils.s3_client.get_object(
                    Bucket=aws_utils.aws_bucket,
                    Key=s3_key
                )
                file_bytes = s3_response['Body'].read()
            else:
                logger.info(f"OCR TASK: Downloading via HTTP GET: {job.file_url}")
                import requests
                res = requests.get(job.file_url, timeout=20)
                if res.status_code != 200:
                    raise Exception(f"HTTP GET returned status code {res.status_code}")
                file_bytes = res.content
        except Exception as dl_err:
            logger.error(f"OCR TASK: Download failed for {job.file_url}: {dl_err}")
            job.ocr_status = "FAILED"
            job.ocr_progress = 100
            job.ocr_completed_at = datetime.utcnow()
            error_details = {
                "__error__": f"Failed to retrieve document: {str(dl_err)}",
                "__failed_stage__": "DOWNLOAD",
                "__timestamp__": datetime.utcnow().isoformat()
            }
            job.extracted_data = error_details
            job.ocr_json = error_details
            job.ocr_error = str(dl_err)
            db.commit()
            broadcast_progress("FAILED", 100, extra={
                "error": "Failed to retrieve document",
                **error_details
            })
            return

        # Preprocessing Image (25%)
        job.ocr_status = "PROCESSING"
        job.ocr_progress = 25
        db.commit()
        broadcast_progress("Preprocessing Image", 25)

        # 3. OCR Text Extraction via Multi-Engine Pipeline (45%)
        job.ocr_status = "EXTRACTING"
        job.ocr_progress = 45
        db.commit()
        broadcast_progress("Extracting Text", 45)
        
        engine = get_idp_engine()
        extraction_start = time.time()
        
        result = engine.process_document(file_bytes, source_url=job.file_url, progress_callback=broadcast_progress)
        
        extraction_time_ms = int((time.time() - extraction_start) * 1000)
        
        if not result.get("success"):
            error_msg = result.get("reason", "Unknown OCR engine error")
            if "No OCR engine installed" in error_msg:
                error_msg = "No OCR engine configured. Please install PaddleOCR or EasyOCR."
            logger.error(f"OCR TASK: Extraction failed. Reason: {error_msg}")
            raise Exception(error_msg)
            
        is_manual_review = result.get("status") == "MANUAL_REVIEW_REQUIRED"

        engine_used = result.get("engine_used", "UNKNOWN")
        ocr_confidence = result.get("confidence", 0.0)
        retry_count = result.get("retry_count", 0)
        preprocessing_steps = result.get("preprocessing_steps", [])
        
        try:
            logger.info(f"Python Executable:\n{sys.executable}\n\n"
                        f"OCR Engine:\n{engine_used}\n\n"
                        f"Document Type:\n{result.get('documentType', 'Unknown Document')}\n\n"
                        f"Processing Time:\n{extraction_time_ms / 1000.0} sec\n\n"
                        f"Confidence:\n{ocr_confidence:.1f}%\n\n"
                        f"Fallback:\n{'Yes' if retry_count > 0 or is_manual_review else 'No'}")
        except Exception as log_err:
            logger.warning(f"Diagnostic logging failed: {log_err}")

        # 4. Field Extraction and Classification (70%)
        job.ocr_status = "VALIDATING"
        job.ocr_progress = 70
        db.commit()
        broadcast_progress("Mapping Fields", 70)

        doc_type = result["documentType"]
        fields = result["extractedFields"]
        confidence_scores = {k: 99 if result["validation"].get(k, False) else 50 for k in fields}
        overall_conf = ocr_confidence

        # Validating Data (85%)
        job.ocr_progress = 85
        db.commit()
        broadcast_progress("Validating Data", 85)

        fraud_flags = []
        if enable_fraud_detection and result["fraudScore"] > 0:
            fraud_flags.append(f"Fraud Score calculated as {result['fraudScore']}/100")
            if result["fraudScore"] >= 50:
                 fraud_flags.append("High probability of document tampering or fake document.")

            id_no = fields.get("id_number")
            if id_no and id_no != "N/A":
                async def run_dup():
                    return await check_duplicate_records(AsyncSessionLocal(), doc_type, id_no)
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        dup_emp = asyncio.run_coroutine_threadsafe(run_dup(), loop).result()
                    else:
                        dup_emp = asyncio.run(run_dup())
                except Exception:
                    dup_emp = None
                if dup_emp:
                    fraud_flags.append(f"Document ID already linked with Candidate {dup_emp}")

        # 6. Compute missing fields for analytics
        missing_fields = [k for k, v in fields.items() 
                          if not v or v == "N/A" or str(v).strip() == ""
                          if k not in ("qr_code_data", "barcode_data", "signature_detected", "raw_text_preview")]
                          
        logger.info(f"Extracted Fields:\n{len(fields) - len(missing_fields)}/{len(fields)}")

        # Saving Results (95%)
        job.ocr_progress = 95
        db.commit()
        broadcast_progress("Saving Results", 95)

        # 7. Write results to DB
        final_status = "LOW_CONFIDENCE" if (overall_conf < 80.0 or is_manual_review) else "COMPLETED"
        job.ocr_status = final_status
        job.ocr_progress = 100
        job.document_type = doc_type
        job.confidence_score = float(overall_conf)
        job.ocr_duration_ms = extraction_time_ms
        job.ocr_completed_at = datetime.utcnow()
        job.ocr_engine = engine_used
        
        # Ensure extracted_data explicitly maps to the exact required schema representation if needed, 
        # though the frontend typically just reads the fields directly from job.extracted_data
        job.extracted_data = fields
        job.ocr_json = fields
        job.confidence_scores = confidence_scores
        job.fraud_flags = fraud_flags

        # 8. Persist OcrAnalytics record
        try:
            analytics_record = models.OcrAnalytics(
                extraction_id=job.id,
                engine_used=engine_used,
                processing_time_ms=extraction_time_ms,
                retry_count=retry_count,
                overall_confidence=float(overall_conf),
                missing_fields=missing_fields,
                preprocessing_steps=preprocessing_steps
            )
            db.add(analytics_record)
        except Exception as analytics_err:
            logger.warning(f"OCR TASK: Failed to persist analytics: {analytics_err}")

        # 9. Persist OcrProcessingLog records for each preprocessing step
        try:
            for step_name in preprocessing_steps:
                log_entry = models.OcrProcessingLog(
                    extraction_id=job.id,
                    step=step_name,
                    status="SUCCESS",
                    details=f"Applied {step_name} during preprocessing",
                    duration_ms=0  # Individual step timing not tracked
                )
                db.add(log_entry)
            
            # Log the OCR engine execution step
            engine_log = models.OcrProcessingLog(
                extraction_id=job.id,
                step="OCR_EXTRACTION",
                status="SUCCESS",
                details=f"Engine: {engine_used}, Confidence: {ocr_confidence:.1f}%, Retries: {retry_count}",
                duration_ms=extraction_time_ms
            )
            db.add(engine_log)
            
            # Log validation step
            validation_log = models.OcrProcessingLog(
                extraction_id=job.id,
                step="FIELD_VALIDATION",
                status="SUCCESS",
                details=f"Document: {doc_type}, Fields: {len(fields)}, Missing: {len(missing_fields)}",
                duration_ms=0
            )
            db.add(validation_log)
            
            # Log fraud detection step if enabled
            if enable_fraud_detection:
                fraud_log = models.OcrProcessingLog(
                    extraction_id=job.id,
                    step="FRAUD_DETECTION",
                    status="FLAGGED" if fraud_flags else "CLEAN",
                    details=f"Flags: {len(fraud_flags)} - {', '.join(fraud_flags) if fraud_flags else 'None'}",
                    duration_ms=0
                )
                db.add(fraud_log)
                
            # Write to Cache if successful
            if final_status == "COMPLETED" and doc_type != "Unknown" and overall_conf >= 90.0:
                import hashlib
                file_hash = hashlib.sha256(file_bytes).hexdigest()
                existing_cache = db.query(models.OcrResultCache).filter_by(file_hash=file_hash).first()
                if not existing_cache:
                    new_cache = models.OcrResultCache(
                        file_hash=file_hash,
                        document_type=doc_type,
                        extracted_fields=fields,
                        confidence_scores=confidence_scores,
                        overall_confidence=float(overall_conf),
                        engine_used=engine_used
                    )
                    db.add(new_cache)
                
        except Exception as log_err:
            logger.warning(f"OCR TASK: Failed to persist processing logs/cache: {log_err}")

        db.commit()
        broadcast_progress("COMPLETED", 100, doc_type, extra={
            "document_type": doc_type,
            "fields": fields,
            "confidence_scores": confidence_scores,
            "fraud_flags": fraud_flags,
            "engine_used": engine_used,
            "processing_time_ms": extraction_time_ms,
            "retry_count": retry_count,
            "missing_fields": missing_fields
        })
        logger.info(f"OCR TASK: Completed job {job_id} successfully. "
                     f"Engine={engine_used}, Confidence={overall_conf:.1f}%, "
                     f"Missing={len(missing_fields)} fields, Flags={len(fraud_flags)}")

    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        logger.error(f"OCR TASK: Failed processing job {job_id}: {str(e)}\n{tb_str}")
        try:
            job = db.query(models.OcrExtraction).filter(models.OcrExtraction.id == job_id).first()
            if job:
                job.ocr_status = "FAILED"
                job.ocr_progress = 100
                job.ocr_completed_at = datetime.utcnow()
                error_details = {
                    "__error__": f"Extraction engine error: {str(e)}\n{tb_str}",
                    "__failed_stage__": "TEXT_EXTRACTION",
                    "__timestamp__": datetime.utcnow().isoformat()
                }
                job.extracted_data = error_details
                job.ocr_json = error_details
                job.ocr_error = str(e)
                db.commit()
                # Broadcast failure
                msg = {
                    "type": "OCR_PROGRESS",
                    "job_id": job_id,
                    "status": "FAILED",
                    "progress": 100,
                    "document_type": "Unknown",
                    "error": str(e),
                    **error_details
                }
                asyncio.run(manager.broadcast(msg))
        except Exception as db_err:
            logger.error(f"OCR TASK: DB update on failure failed: {db_err}")
    finally:
        db.close()

