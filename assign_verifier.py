import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    # 1. Find Verifier Role ID
    verifier_role = conn.execute(text("SELECT id FROM roles WHERE name = 'Verifier'")).fetchone()
    if not verifier_role:
        print("Verifier role not found. Creating it...")
        import uuid
        role_id = str(uuid.uuid4())
        perms = '{"bvs.verification": {"read": true, "write": true, "delete": false}, "bvs.qc": {"read": false, "write": false, "delete": false}, "bms.applicants": {"read": true, "write": false, "delete": false}, "mis.report": {"read": true, "write": false, "delete": false}}'
        conn.execute(text(f"INSERT INTO roles (id, name, description, permissions) VALUES ('{role_id}', 'Verifier', 'Verification execution role', '{perms}')"))
        v_role_id = role_id
    else:
        v_role_id = verifier_role[0]
    
    # 2. Update BALAMURUGAN S
    print(f"Updating BALAMURUGAN S (verifier@bgvms.com) to Verifier role ({v_role_id})")
    conn.execute(text(f"UPDATE users SET role_id = '{v_role_id}', role = 'VERIFIER' WHERE email = 'verifier@bgvms.com'"))
    conn.commit()
    print("Update successful.")
