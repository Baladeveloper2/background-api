import pymysql
import json
import uuid
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

def setup():
    db_url = os.getenv("DATABASE_URL")
    parsed = urlparse(db_url)
    conn = pymysql.connect(
        host=parsed.hostname,
        user=parsed.username,
        password=parsed.password,
        database=parsed.path.lstrip('/'),
        port=parsed.port or 3306,
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    
    try:
        print("Creating tables if not exist...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS modules (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                code VARCHAR(100) UNIQUE NOT NULL,
                category VARCHAR(100) NOT NULL,
                description VARCHAR(500),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                description VARCHAR(500),
                permissions TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("Checking if seed is needed...")
        cursor.execute("SELECT count(*) FROM modules")
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("Seeding modules...")
            modules_data = [
                (str(uuid.uuid4()), "Applicants", "bms.applicants", "BMS"),
                (str(uuid.uuid4()), "Customer", "bms.customer", "BMS"),
                (str(uuid.uuid4()), "Batch", "bms.batch", "BMS"),
                (str(uuid.uuid4()), "Data Entry", "bvs.data_entry", "BVS"),
                (str(uuid.uuid4()), "Verification", "bvs.verification", "BVS"),
                (str(uuid.uuid4()), "QC", "bvs.qc", "BVS"),
                (str(uuid.uuid4()), "MIS Master", "customer.mis_master", "Customer"),
                (str(uuid.uuid4()), "Candidate Login", "customer.candidate_login", "Customer"),
            ]
            for m in modules_data:
                cursor.execute("INSERT INTO modules (id, name, code, category) VALUES (%s, %s, %s, %s)", m)
            
            print("Seeding roles...")
            all_perms = {m[2]: True for m in modules_data}
            super_admin_id = str(uuid.uuid4())
            cursor.execute("INSERT INTO roles (id, name, description, permissions) VALUES (%s, %s, %s, %s)", 
                           (super_admin_id, "Super Admin", "Full system access", json.dumps(all_perms)))
            
            cursor.execute("INSERT INTO roles (id, name, description, permissions) VALUES (%s, %s, %s, %s)", 
                           (str(uuid.uuid4()), "Verifier", "Access to verification and data entry", json.dumps({"bvs.verification": True, "bvs.data_entry": True})))

            print("Updating admin user...")
            cursor.execute("UPDATE users SET role_id = %s WHERE email = 'admin@bgvms.com'", (super_admin_id,))
            
        print("Commiting changes...")
        conn.commit()
        print("RBAC Setup/Seed completed successfully.")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    setup()
