import pymysql
import json
import uuid
import os
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

def setup():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not found in .env")
        return

    # Parse DATABASE_URL
    # mysql+pymysql://user:pass@host:port/dbname
    parsed = urlparse(db_url)
    user = parsed.username
    password = parsed.password
    host = parsed.hostname
    port = parsed.port or 3306
    db_name = parsed.path.lstrip('/')

    conn = None
    try:
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=db_name,
            port=port,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.Cursor
        )
        cursor = conn.cursor()
        
        print(f"Connected to {host}:{port}/{db_name}. Dropping and recreating tables...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        try:
            cursor.execute("ALTER TABLE roles DROP FOREIGN KEY roles_ibfk_1")
        except:
            pass
        cursor.execute("DROP TABLE IF EXISTS roles")
        cursor.execute("DROP TABLE IF EXISTS modules")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0") # Disable again for creation just in case
        cursor.execute("""
            CREATE TABLE modules (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                code VARCHAR(100) UNIQUE NOT NULL,
                category VARCHAR(100) NOT NULL,
                description VARCHAR(500),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE roles (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                description VARCHAR(500),
                permissions TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
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
        # Note: We use 'admin@bgvms.com' as the default admin email in our scripts
        cursor.execute("UPDATE users SET role_id = %s WHERE email = 'admin@bgvms.com'", (super_admin_id,))
        
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        print("Cloud DB Raw SQL Setup completed successfully.")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    setup()
