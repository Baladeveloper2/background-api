from app.database import SessionLocal, SQLALCHEMY_DATABASE_URL
from app.stats_routes import get_dashboard_stats
from app.models import User, UserRole

print(f"DEBUG: Using DATABASE_URL = {SQLALCHEMY_DATABASE_URL}")

db = SessionLocal()
# Mock a super admin user for bypass
user = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
if not user:
    user = User(email="debug@example.com", role=UserRole.SUPER_ADMIN)

try:
    stats = get_dashboard_stats(db=db, current_user=user)
    print("Stats fetched successfully")
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
