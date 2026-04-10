import os
import uuid
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

def add_qc_role():
    with engine.connect() as connection:
        # Check if QC Analyst role exists
        res = connection.execute(text("SELECT id FROM roles WHERE name = 'QC Analyst'")).fetchone()
        if not res:
            print("Creating QC Analyst Role...")
            role_id = str(uuid.uuid4())
            perms = '{"bvs.verification": {"read": true, "write": true, "delete": false}, "bvs.qc": {"read": true, "write": true, "delete": false}, "bms.applicants": {"read": true, "write": false, "delete": false}, "mis.report": {"read": true, "write": false, "delete": false}}'
            connection.execute(text(f"INSERT INTO roles (id, name, description, permissions) VALUES ('{role_id}', 'QC Analyst', 'Quality Control and Authorization Role', '{perms}')"))
            connection.commit()
            print("QC Analyst role created.")
        else:
            print("QC Analyst role already exists.")

if __name__ == "__main__":
    add_qc_role()
