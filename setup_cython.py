"""
Cython compilation setup for FastAPI backend.
Run this on the Linux VPS to compile all .py files to .so binaries.

Usage:
    python setup_cython.py build_ext --inplace
"""

from setuptools import setup, Extension
from Cython.Build import cythonize
import os
import glob

# Files to EXCLUDE from compilation (these need to stay as .py)
EXCLUDE_FILES = {
    "__init__.py",  # Package markers - must stay as .py
    "database.py",  # SQLAlchemy engine setup - safer as .py
}

# Sub-packages to also include
SUB_PACKAGES = ["idp"]

def get_extensions():
    extensions = []

    # Collect all .py files in app/
    py_files = glob.glob("app/*.py")

    # Add sub-package files
    for sub in SUB_PACKAGES:
        py_files += glob.glob(f"app/{sub}/*.py")

    for filepath in py_files:
        filename = os.path.basename(filepath)

        # Skip excluded files
        if filename in EXCLUDE_FILES:
            print(f"  [SKIP] {filepath}")
            continue

        # Convert path to module name: app/main.py -> app.main
        module_name = filepath.replace(os.sep, ".").replace("/", ".")[:-3]

        print(f"  [COMPILE] {filepath} -> {module_name}")
        extensions.append(
            Extension(
                name=module_name,
                sources=[filepath],
            )
        )

    return extensions


if __name__ == "__main__":
    print("=" * 60)
    print("Cython Compilation — FastAPI Backend")
    print("=" * 60)

    exts = get_extensions()
    print(f"\nCompiling {len(exts)} files...\n")

    setup(
        name="backend",
        ext_modules=cythonize(
            exts,
            compiler_directives={
                "language_level": "3",      # Python 3
                "always_allow_keywords": True,
            },
            nthreads=4,                     # Parallel compilation
            quiet=False,
        ),
    )

    print("\n[DONE] Compilation complete!")
