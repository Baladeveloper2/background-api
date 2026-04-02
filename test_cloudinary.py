import os
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

# Cloudinary initialization
cloudinary.config(secure=True)

def test_upload():
    try:
        cloudinary.config(
            cloud_name="dfrfq0ch8",
            api_key="257176576991427",
            api_secret="L0Dsbb-q8rIUV-nAznSlVTpy5DY",
            secure=True
        )
        
        # Create a small dummy file
        with open("test_upload.txt", "w") as f:
            f.write("test upload content")
        
        print("Attempting upload...")
        result = cloudinary.uploader.upload(
            "test_upload.txt",
            folder="test_uploads",
            resource_type="auto"
        )
        print("Upload successful!")
        print(f"URL: {result.get('secure_url')}")
    except Exception as e:
        print(f"Upload failed: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if os.path.exists("test_upload.txt"):
            os.remove("test_upload.txt")

if __name__ == "__main__":
    test_upload()
