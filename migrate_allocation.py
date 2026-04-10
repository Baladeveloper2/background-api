import os
import uuid
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from passlib.context import CryptContext

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def migrate():
    commands = [
        # Change role to VARCHAR to avoid ENUM issues
        "ALTER TABLE users MODIFY role VARCHAR(50);",
        # Add assigned_to column to cases
        "ALTER TABLE cases ADD COLUMN assigned_to VARCHAR(36) NULL REFERENCES users(id);",
    ]
    
    with engine.connect() as connection:
        for command in commands:
            print(f"Executing: {command}")
            try:
                connection.execute(text(command))
                connection.commit()
                print("Success.")
            except Exception as e:
                print(f"Note: {e}") # Might already exist
        
        # Now create user and role
        print("Creating QA Audit Role and User...")
        
        # 1. QA Audit Role
        qa_role_id = str(uuid.uuid4())
        check_role = connection.execute(text("SELECT id FROM roles WHERE name = 'QA Audit'")).fetchone()
        if not check_role:
            perms = '{"bvs.verification": {"read": true, "write": true, "delete": false}, "bvs.qc": {"read": true, "write": true, "delete": false}, "bms.applicants": {"read": true, "write": true, "delete": false}, "mis.report": {"read": true, "write": false, "delete": false}}'
            connection.execute(text(f"INSERT INTO roles (id, name, description, permissions) VALUES ('{qa_role_id}', 'QA Audit', 'Quality Assurance and Audit Governance', '{perms}')"))
            print(f"Created QA Audit Role: {qa_role_id}")
        else:
            qa_role_id = check_role[0]
            print(f"QA Audit Role exists: {qa_role_id}")
            
        # 2. QA Audit User
        email = "qa.audit@cl-edge.com"
        check_user = connection.execute(text(f"SELECT id FROM users WHERE email = '{email}'")).fetchone()
        if not check_user:
            user_id = str(uuid.uuid4())
            hp = pwd_context.hash("Admin@123")
            connection.execute(text(f"INSERT INTO users (id, email, full_name, hashed_password, role, role_id, status) VALUES ('{user_id}', '{email}', 'QA Audit Lead', '{hp}', 'QA', '{qa_role_id}', 'ACTIVE')"))
            print(f"Created QA Audit User: {email}")
        else:
            print(f"QA Audit User exists: {email}")
            connection.execute(text(f"UPDATE users SET role = 'QA', role_id = '{qa_role_id}' WHERE email = '{email}'"))

        connection.commit()

if __name__ == "__main__":
    migrate()
