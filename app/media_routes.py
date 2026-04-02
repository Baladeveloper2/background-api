from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
import cloudinary
import cloudinary.uploader
from .auth_routes import get_current_user
from .models import User
import os

router = APIRouter(prefix="/media", tags=["media"])

# Initializing Cloudinary
import os
from dotenv import load_dotenv
load_dotenv(override=True)

# Explicitly set credentials to ensure they are picked up correctly
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_URL').split('@')[-1] if os.getenv('CLOUDINARY_URL') else "dfrfq0ch8",
    api_key=os.getenv('CLOUDINARY_URL').split(':')[1].split('//')[-1] if os.getenv('CLOUDINARY_URL') else "257176576991427",
    api_secret=os.getenv('CLOUDINARY_URL').split(':')[2].split('@')[0] if os.getenv('CLOUDINARY_URL') else "L0Dsbb-q8rIUV-nAznSlVTpy5DY",
    secure=True
)

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Uploads a file to Cloudinary and returns the secure URL.
    Supports PDF, DOC, and images.
    """
    try:
        # Validate file extension
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png']:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF, DOC, or images.")

        # Cloudinary initialization is handled globally or via CLOUDINARY_URL in .env
        # The cloud name dfrfq0ch8 is confirmed working.
        
        # NOTE: Firebase migration is paused, prioritizing Cloudinary as requested.
        # if ext in ['.pdf', '.doc', '.docx']:
        #     try:
        #         from .firebase_config import get_firebase_bucket
        #         bucket = get_firebase_bucket()
        #         blob_path = f"bgv_documents/{os.path.splitext(file.filename)[0]}_{os.urandom(4).hex()}{ext}"
        #         blob = bucket.blob(blob_path)
        #         blob.upload_from_file(file.file, content_type=file.content_type)
        #         blob.make_public()
        #         return {
        #             "url": blob.public_url,
        #             "storage_provider": "firebase",
        #             "original_filename": file.filename
        #         }
        #     except Exception as fe:
        #         logging.error(f"Firebase upload error: {str(fe)}")
        #         pass

        # Default to Cloudinary
        resource_type = "auto"
        if ext in ['.pdf', '.doc', '.docx']:
            resource_type = "raw"
        
        # Ensure we are at the start of the file
        await file.seek(0)
        
        upload_result = cloudinary.uploader.upload(
            file.file,
            resource_type=resource_type,
            folder="bgv_documents",
            public_id=f"{os.path.splitext(file.filename)[0]}_{os.urandom(4).hex()}"
        )

        return {
            "url": upload_result.get("secure_url"),
            "storage_provider": "cloudinary",
            "original_filename": file.filename
        }
    except Exception as e:
        # Log the error details here for debugging if needed
        logging.error(f"Cloudinary upload error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file to storage: {str(e)}"
        )
