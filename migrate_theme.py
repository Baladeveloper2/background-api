import sys
import os

# Add backend directory to sys.path to resolve imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import engine
from sqlalchemy import text

def add_column():
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN theme_preference VARCHAR(50) DEFAULT 'professional-violet'"))
            print("Successfully added theme_preference column to users table.")
        except Exception as e:
            if "Duplicate column name" in str(e):
                print("Column theme_preference already exists. Skipping.")
            else:
                print(f"Error adding column: {e}")

if __name__ == "__main__":
    add_column()
