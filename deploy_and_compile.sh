#!/bin/bash
# ============================================================
# deploy_and_compile.sh
# Run this script ON YOUR HOSTINGER VPS after uploading files
# ============================================================

set -e  # Exit on any error

DEPLOY_DIR="/var/www/backend"
VENV_DIR="$DEPLOY_DIR/venv"

echo "========================================"
echo " FastAPI Backend — Cython Deployment"
echo "========================================"

# Step 1: Install system build dependencies
echo ""
echo "[1/6] Installing system build tools..."
sudo apt-get update -qq
sudo apt-get install -y python3-dev gcc build-essential

# Step 2: Create venv if not exists
echo ""
echo "[2/6] Setting up Python virtual environment..."
cd $DEPLOY_DIR
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv venv
    echo "  Created new venv"
else
    echo "  venv already exists"
fi

source $VENV_DIR/bin/activate

# Step 3: Install Python requirements + Cython
echo ""
echo "[3/6] Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install cython setuptools -q
echo "  Dependencies installed"

# Step 4: Compile with Cython
echo ""
echo "[4/6] Compiling Python files with Cython..."
python setup_cython.py build_ext --inplace
echo "  Compilation done!"

# Step 5: Remove source .py files (keep only .so binaries)
echo ""
echo "[5/6] Removing source .py files..."

# Remove .py files but KEEP __init__.py and database.py (excluded from compilation)
find app/ -name "*.py" \
    ! -name "__init__.py" \
    ! -name "database.py" \
    -delete

# Remove Cython build artifacts (not needed at runtime)
rm -rf build/
find app/ -name "*.c" -delete
find app/ -name "*.pyx" -delete 2>/dev/null || true

echo "  Source files removed"

# Step 6: Verify .so files exist
echo ""
echo "[6/6] Verifying compiled binaries..."
SO_COUNT=$(find app/ -name "*.so" | wc -l)
echo "  Found $SO_COUNT .so binary files"

if [ "$SO_COUNT" -eq 0 ]; then
    echo "  ERROR: No .so files found! Compilation may have failed."
    exit 1
fi

find app/ -name "*.so" | head -20

echo ""
echo "========================================"
echo " Deployment Complete!"
echo " Source code is now hidden."
echo "========================================"
echo ""
echo "Start server with:"
echo "  source $VENV_DIR/bin/activate"
echo "  gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000"
echo ""
