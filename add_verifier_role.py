import os
import uuid
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

def add_verifier_role():
    with engine.connect() as connection:
        # Check if Verifier role exists
        res = connection.execute(text("SELECT id FROM roles WHERE name = 'Verifier'")).fetchone()
        if not res:
            print("Creating Verifier Role...")
            role_id = str(uuid.uuid4())
            perms = '{"bvs.verification": {"read": true, "write": true, "delete": false}, "bvs.qc": {"read": false, "write": false, "delete": false}, "bms.applicants": {"read": true, "write": false, "delete": false}, "mis.report": {"read": true, "write": false, "delete": false}}'
            connection.execute(text(f"INSERT INTO roles (id, name, description, permissions) VALUES ('{role_id}', 'Verifier', 'Standard Verification and Audit Execution Role', '{perms}')"))
            connection.commit()
            print("Verifier role created.")
        else:
            print("Verifier role already exists.")

if __name__ == "__main__":
    add_verifier_role()
