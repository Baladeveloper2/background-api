import uvicorn
import os
import sys
from dotenv import load_dotenv

# Enforce virtual environment usage
venv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "venv", "Scripts", "python.exe"))
if os.path.exists(venv_path) and os.path.normcase(sys.executable) != os.path.normcase(venv_path):
    print(f"Warning: Not running in venv. Respawning with {venv_path}...")
    os.execv(venv_path, [venv_path] + sys.argv)

# Load environment variables from .env
load_dotenv()

if __name__ == "__main__":
    print("Starting BGVMS API Server...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
