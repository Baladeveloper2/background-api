import os
import logging
from .celery_app import celery_app
from io import BytesIO
import boto3
from dotenv import load_dotenv
import time
from playwright.sync_api import sync_playwright
from sqlalchemy.orm.attributes import flag_modified
from .database import SessionLocal
from . import models

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
