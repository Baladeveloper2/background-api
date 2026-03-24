import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

if __name__ == "__main__":
    print("Starting BGVMS API Server...")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
