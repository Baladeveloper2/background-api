import sys
import os

sys.path.append(r'd:\project\backend')

from app.database import sync_engine
from sqlalchemy import text

def update_schema():
    with sync_engine.connect() as conn:
        print("Checking users table structure...")
        
        # Check if columns exist
        res = conn.execute(text("DESCRIBE users"))
        columns = [row[0] for row in res.fetchall()]
        print(f"Current columns: {columns}")
        
        # Add phone column if not exists
        if "phone" not in columns:
            print("Adding 'phone' column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(20) NULL"))
            print("'phone' column added.")
        
        # Add is_2fa_enabled column if not exists
        if "is_2fa_enabled" not in columns:
            print("Adding 'is_2fa_enabled' column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN is_2fa_enabled TINYINT(1) DEFAULT 0 NOT NULL"))
            print("'is_2fa_enabled' column added.")
            
        # Add otp_code column if not exists
        if "otp_code" not in columns:
            print("Adding 'otp_code' column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN otp_code VARCHAR(6) NULL"))
            print("'otp_code' column added.")
            
        # Add otp_expires_at column if not exists
        if "otp_expires_at" not in columns:
            print("Adding 'otp_expires_at' column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN otp_expires_at DATETIME NULL"))
            print("'otp_expires_at' column added.")
            
        conn.commit()
        print("Database schema update finished successfully.")

if __name__ == "__main__":
    update_schema()
