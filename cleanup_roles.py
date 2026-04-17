import sys
import os

sys.path.append(os.getcwd())

from app.database import SessionLocal
from app import models

def cleanup():
    db = SessionLocal()
    try:
        # 1. Rename 'QA' to 'QC Verifier'
        qa_role = db.query(models.Role).filter(models.Role.name == "QA").first()
        if qa_role:
            qa_role.name = "QC Verifier"
            print("Renamed 'QA' to 'QC Verifier'")
        
        # 2. Rename 'SUPER_ADMIN' to 'Super Admin'
        sa_role = db.query(models.Role).filter(models.Role.name == "SUPER_ADMIN").first()
        if sa_role:
            sa_role.name = "Super Admin"
            print("Renamed 'SUPER_ADMIN' to 'Super Admin'")
            
        db.commit()

        # 3. Ensure standard roles exist
        approved_names = ["Super Admin", "QC Verifier", "Verifier", "Data Entry"]
        for name in approved_names:
            role = db.query(models.Role).filter(models.Role.name == name).first()
            if not role:
                role = models.Role(name=name, description=f"Standard {name} Role")
                db.add(role)
                print(f"Created missing role: {name}")
        db.commit()

        # Get Verifier role for fallback
        verifier_role = db.query(models.Role).filter(models.Role.name == "Verifier").first()
        
        # 4. Handle users in unwanted roles
        unwanted_roles = db.query(models.Role).filter(~models.Role.name.in_(approved_names)).all()
        for role in unwanted_roles:
            # Reassign users
            users = db.query(models.User).filter(models.User.role_id == role.id).all()
            if users:
                for user in users:
                    user.role_id = verifier_role.id
                print(f"Reassigned {len(users)} users from '{role.name}' to 'Verifier'")
            
            # Delete role
            db.delete(role)
            print(f"Deleted role: {role.name}")
        
        db.commit()
        print("Cleanup complete.")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    cleanup()
