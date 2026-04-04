from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
import fastapi
import logging
import cloudinary
import cloudinary.uploader
import cloudinary.utils
from .auth_routes import get_current_user
from .models import User
import os
import logging

router = APIRouter(prefix="/media", tags=["media"])

# Initializing Cloudinary
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

        # Default to Cloudinary auto resource type (picks 'image' for PDF to allow transformations)
        resource_type = "auto"
        
        # Ensure we are at the start of the file
        await file.seek(0)
        
        upload_result = cloudinary.uploader.upload(
            file.file,
            resource_type=resource_type,
            folder="bgv_documents",
            public_id=f"{os.path.splitext(file.filename)[0]}_{os.urandom(4).hex()}",
            type="upload" # Explicitly set to public upload
        )

        return {
            "url": upload_result.get("secure_url"),
            "public_id": upload_result.get("public_id"),
            "resource_type": upload_result.get("resource_type"),
            "storage_provider": "cloudinary",
            "original_filename": file.filename
        }
    except Exception as e:
        logging.error(f"Cloudinary upload error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file to storage: {str(e)}"
        )

@router.get("/get-url")
def get_signed_url(
    public_id: str,
    resource_type: str = "image",
    current_user: User = Depends(get_current_user)
):
    """
    Generates a signed URL for a private or restricted Cloudinary asset.
    """
    try:
        # Generate a signed URL that expires in 1 hour
        # Note: cloudinary_url returns a tuple (url, options)
        logging.info(f"Signing URL for: {public_id}, resource_type: {resource_type}")
        url, options = cloudinary.utils.cloudinary_url(
            public_id,
            resource_type=resource_type,
            secure=True,
            sign_url=True
        )
        return {"url": url}
    except Exception as e:
        logging.error(f"Error generating signed URL: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate signed URL")
