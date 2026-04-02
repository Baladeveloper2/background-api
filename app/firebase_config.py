import os
import firebase_admin
from firebase_admin import credentials, storage
from dotenv import load_dotenv

load_dotenv()

def initialize_firebase():
    """Initializes Firebase Admin SDK if not already initialized."""
    if not firebase_admin._apps:
        # Check for service account key path in .env
        cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
        bucket_url = os.getenv("FIREBASE_STORAGE_BUCKET")
        
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred, {
                'storageBucket': bucket_url
            })
            print("Firebase initialized with Service Account Key.")
        else:
            # Fallback for development/testing if allowed
            print("Warning: FIREBASE_SERVICE_ACCOUNT_KEY not found. PDF uploads may fail.")
            # Initialize with default credentials if available
            try:
                firebase_admin.initialize_app(options={
                    'storageBucket': bucket_url
                })
                print("Firebase initialized with default credentials.")
            except:
                pass

def get_firebase_bucket():
    initialize_firebase()
    return storage.bucket()
