from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
import logging
import cloudinary
import cloudinary.uploader
import cloudinary.utils
from .auth_routes import get_current_user
from .models import User
import os

router = APIRouter(prefix="/media", tags=["media"])

# Initializing Cloudinary
from dotenv import load_dotenv
load_dotenv(override=True)

# Prefer CLOUDINARY_URL for simplicity and robustness
# Cloudinary Python library handles the parsing of the URL automatically
cloudinary_url = os.getenv('CLOUDINARY_URL')
if cloudinary_url:
    cloudinary.config(cloudinary_url=cloudinary_url, secure=True)
else:
    # Explicit fallbacks if URL is missing
    cloudinary.config(
        cloud_name="dfrfq0ch8",
        api_key="257176576991427",
        api_secret="L0Dsbb-q8rIUV-nAznSlVTpy5DY",
        secure=True
    )

@router.post("/upload")
def upload_file(
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
        allowed_exts = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.webp', '.gif']
        if ext not in allowed_exts:
            raise HTTPException(status_code=400, detail=f"Unsupported file format ({ext}). Please upload PDF, DOC, or images.")

        # Determine resource type based on extension
        # Cloudinary treats PDFs as 'image' to allow thumbnails/previews
        if ext in ['.pdf', '.jpg', '.jpeg', '.png']:
            resource_type = "image"
        else:
            resource_type = "raw"
        
        # Ensure we are at the start of the file
        file.file.seek(0)
        
        # Use filename as public_id base but sanitize it to avoid signature issues with special chars
        base_filename = "".join([c if c.isalnum() or c in ['-', '_'] else '_' for c in os.path.splitext(file.filename)[0]])
        
        upload_result = cloudinary.uploader.upload(
            file.file,
            resource_type=resource_type,
            folder="bgv_documents",
            public_id=f"{base_filename}_{os.urandom(2).hex()}",
            type="upload" # Explicitly set to public upload
        )

        return {
            "url": upload_result.get("secure_url"),
            "public_id": upload_result.get("public_id"),
            "resource_type": upload_result.get("resource_type"),
            "storage_provider": "cloudinary",
            "original_filename": file.filename
        }
    except HTTPException as he:
        # Re-raise HTTPExceptions as-is so client gets correct status (e.g. 400)
        raise he
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
        # Normalize resource_type based on common use cases in this system
        effective_resource_type = resource_type
        if public_id.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png', '.webp', '.gif')):
             effective_resource_type = "image"
        elif public_id.lower().endswith(('.doc', '.docx')):
             effective_resource_type = "raw"

        logging.info(f"Generating URL for: {public_id}, resource_type: {effective_resource_type}")
        
        # We use signed URLs for delivery. If 401 occurs, it's usually 
        # a configuration mismatch or type mismatch.
        url, options = cloudinary.utils.cloudinary_url(
            public_id,
            resource_type=effective_resource_type,
            secure=True,
            sign_url=True
        )
        return {"url": url}
    except Exception as e:
        logging.error(f"Error generating signed URL: {str(e)}")
        # Fallback to a non-signed secure URL for public assets in bgv_documents
        url, _ = cloudinary.utils.cloudinary_url(
            public_id, 
            resource_type="image", 
            secure=True
        )
        return {"url": url}

# End of Media Routes
