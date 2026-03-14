import pymysql, os, json, uuid
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()
u = urlparse(os.getenv('DATABASE_URL'))
conn = pymysql.connect(
    host=u.hostname, user=u.username, password=u.password, 
    database=u.path.lstrip('/'), port=u.port or 3306,
    autocommit=True
)
cur = conn.cursor()

def run():
    print("Disabling FK checks and cleaning up...")
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    
    # Drop known constraints on users
    try: cur.execute("ALTER TABLE users DROP FOREIGN KEY users_ibfk_1")
    except: pass
    
    # Drop known constraints on admin_role_permissions
    try: cur.execute("ALTER TABLE admin_role_permissions DROP FOREIGN KEY fk_admin_role_permissions_role_id")
    except: pass
    
    # Drop tables
    cur.execute("DROP TABLE IF EXISTS roles")
    cur.execute("DROP TABLE IF EXISTS modules")
    
    print("Creating tables...")
    cur.execute("""
        CREATE TABLE modules (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            code VARCHAR(100) UNIQUE NOT NULL,
            category VARCHAR(100) NOT NULL,
            description VARCHAR(500),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE roles (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            description VARCHAR(500),
            permissions TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    print("Seeding...")
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
        cur.execute("INSERT INTO modules (id, name, code, category) VALUES (%s, %s, %s, %s)", m)
        
    all_perms = {m[2]: True for m in modules_data}
    super_admin_id = str(uuid.uuid4())
    cur.execute("INSERT INTO roles (id, name, description, permissions) VALUES (%s, %s, %s, %s)", 
                (super_admin_id, "Super Admin", "Full system access", json.dumps(all_perms)))
    
    cur.execute("INSERT INTO roles (id, name, description, permissions) VALUES (%s, %s, %s, %s)", 
                (str(uuid.uuid4()), "Verifier", "Access to verification and data entry", json.dumps({"bvs.verification": True, "bvs.data_entry": True})))

    print("Re-assigning admin user...")
    cur.execute("UPDATE users SET role_id = %s WHERE email = 'admin@bgvms.com'", (super_admin_id,))
    
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    print("RBAC system is now LIVE with data.")

if __name__ == "__main__":
    run()
    conn.close()
