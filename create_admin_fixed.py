from app.database import SessionLocal
from app import models
import bcrypt
import uuid

def create_admin():
    db = SessionLocal()
    admin_email = "admin@bgvms.com"
    db_user = db.query(models.User).filter(models.User.email == admin_email).first()
    
    if db_user:
        print(f"User {admin_email} already exists")
        return

    password = "admin123".encode('utf-8')
    hashed_password = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')
    
    new_user = models.User(
        id=str(uuid.uuid4()),
        email=admin_email,
        hashed_password=hashed_password,
        full_name="System Admin",
        role=models.UserRole.SUPER_ADMIN,
        status=models.Status.ACTIVE,
        bvs_permissions={
            "bms": {"applicants": True, "customer": True, "batch": True},
            "bvs": {"verification": True, "qc": True, "data_entry": True},
            "candidate": {"management": True},
            "mis": {"report": True},
            "admin": {"panel": True}
        }
    )

    db.add(new_user)
    db.commit()
    print(f"Admin user created: {admin_email} / admin123")

if __name__ == "__main__":
    create_admin()
