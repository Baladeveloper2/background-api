from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
import cloudinary
import cloudinary.uploader
from .auth_routes import get_current_user
from .models import User
import os

router = APIRouter(prefix="/media", tags=["media"])

# Initializing Cloudinary
# It automatically picks up CLOUDINARY_URL from environment variables if present.
# We call config() to ensure it's initialized.
cloudinary.config(secure=True)

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

        # Determine optimal resource type to avoid 401 Unauthorized for PDFs
        resource_type = "raw" if ext in ['.pdf', '.doc', '.docx'] else "auto"

        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file.file,
            resource_type=resource_type,
            folder="bgv_documents",
            public_id=f"{os.path.splitext(file.filename)[0]}_{os.urandom(4).hex()}"
        )

        return {
            "url": upload_result.get("secure_url"),
            "public_id": upload_result.get("public_id"),
            "original_filename": file.filename
        }
    except Exception as e:
        # Log the error details here for debugging if needed
        print(f"Cloudinary upload error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file to storage: {str(e)}"
        )
