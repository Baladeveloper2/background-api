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
    print("PURGING EVERYTHING...")
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    
    # 1. Drop constraints on OTHER tables that might point to roles/modules
    # We find them dynamically
    cur.execute("""
        SELECT TABLE_NAME, CONSTRAINT_NAME 
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
        WHERE TABLE_SCHEMA = 'defaultdb' 
        AND REFERENCED_TABLE_NAME IN ('roles', 'modules')
    """)
    for table, constr in cur.fetchall():
        print(f"Dropping constraint {constr} on {table}")
        try: cur.execute(f"ALTER TABLE {table} DROP FOREIGN KEY {constr}")
        except: pass

    # 2. Drop the tables
    cur.execute("DROP TABLE IF EXISTS roles")
    cur.execute("DROP TABLE IF EXISTS modules")
    
    # 3. Create fresh
    print("Recreating...")
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
    
    # 4. Seed
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
    
    print("Assigning user...")
    cur.execute("UPDATE users SET role_id = %s WHERE email = 'admin@bgvms.com'", (super_admin_id,))
    
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    print("DONE! RBAC system should be live and visible.")

if __name__ == "__main__":
    run()
    conn.close()
