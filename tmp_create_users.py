
import sys
import os

# Add the project directory to sys.path
sys.path.append(r'd:\project\backend')

from app.database import SYNC_URL
from app.models import Role, User
from app.enums import UserRole
from app.auth import get_password_hash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(SYNC_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    print("Checking existing roles...")
    roles = db.query(Role).all()
    for r in roles:
        print(f"Role: {r.name} (ID: {r.id})")

    # Ensure Verifier Role exists in DB
    verifier_role = db.query(Role).filter(Role.name == "VERIFIER").first()
    if not verifier_role:
        print("Creating VERIFIER role...")
        verifier_role = Role(name="VERIFIER", description="Field Auditor / Verifier")
        db.add(verifier_role)
        db.flush()

    # Ensure QA Role exists in DB
    qa_role = db.query(Role).filter(Role.name == "QA").first()
    if not qa_role:
        print("Creating QA role...")
        qa_role = Role(name="QA", description="Final Verification Auditor")
        db.add(qa_role)
        db.flush()

    # Create User Bala (Verifier)
    bala = db.query(User).filter(User.email == "bala@example.com").first()
    if not bala:
        print("Creating user Bala...")
        bala = User(
            email="bala@example.com",
            full_name="Bala",
            hashed_password=get_password_hash("Password@123"),
            role=UserRole.VERIFIER,
            role_id=verifier_role.id,
            status="ACTIVE"
        )
        db.add(bala)
    else:
        print("User Bala already exists.")
        bala.role = UserRole.VERIFIER
        bala.role_id = verifier_role.id

    # Create User Manish (QA)
    manish = db.query(User).filter(User.email == "manish@example.com").first()
    if not manish:
        print("Creating user Manish...")
        manish = User(
            email="manish@example.com",
            full_name="Manish",
            hashed_password=get_password_hash("Password@123"),
            role=UserRole.QA,
            role_id=qa_role.id,
            status="ACTIVE"
        )
        db.add(manish)
    else:
        print("User Manish already exists.")
        manish.role = UserRole.QA
        manish.role_id = qa_role.id

    db.commit()
    print("Successfully created/updated users and roles.")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
finally:
    db.close()
