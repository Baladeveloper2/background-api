import uvicorn
import os
import sys
from dotenv import load_dotenv

# Enforce virtual environment usage
if not getattr(sys, 'frozen', False):
    venv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "venv", "Scripts", "python.exe"))
    if os.path.exists(venv_path) and os.path.normcase(sys.executable) != os.path.normcase(venv_path):
        import subprocess
        print(f"Warning: Not running in venv. Respawning with {venv_path}...")
        sys.exit(subprocess.run([venv_path] + sys.argv).returncode)

# Load environment variables from .env
load_dotenv()

if __name__ == "__main__":
    from app.main import app
    print("Starting BGVMS API Server...")
    port = int(os.environ.get("PORT", 8000))
    # We must pass the imported app object, and CANNOT use reload=True when compiled
    uvicorn.run(app, host="0.0.0.0", port=port)
