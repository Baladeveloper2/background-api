from app.database import SessionLocal
from app import models, auth
import sys

def create_admin():
    db = SessionLocal()
    admin_email = "admin@bgvms.com"
    db_user = db.query(models.User).filter(models.User.email == admin_email).first()
    
    if db_user:
        print(f"User {admin_email} already exists")
        return

    hashed_password = auth.get_password_hash("admin123")
    new_user = models.User(
        email=admin_email,
        hashed_password=hashed_password,
        full_name="System Admin",
        role=models.UserRole.SUPER_ADMIN,
        status=models.Status.ACTIVE
    )
    db.add(new_user)
    db.commit()
    print(f"Admin user created: {admin_email} / admin123")

if __name__ == "__main__":
    create_admin()
