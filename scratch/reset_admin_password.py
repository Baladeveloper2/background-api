import sys
sys.path.append(r'd:\project\backend')

from app.database import SYNC_URL
from app.models import User
from app.auth import get_password_hash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(SYNC_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    user = db.query(User).filter(User.email == "admin@bgvms.com").first()
    if user:
        user.hashed_password = get_password_hash("Password@123")
        db.commit()
        print("Successfully updated admin password to Password@123")
    else:
        print("Admin user not found")
except Exception as e:
    db.rollback()
    print(f"Error: {e}")
finally:
    db.close()
