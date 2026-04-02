import os
import sys

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app import models

def delete_user(email):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if user:
            db.delete(user)
            db.commit()
            print(f"User {email} deleted successfully.")
        else:
            print(f"User {email} not found.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    delete_user("admin@example.com")
