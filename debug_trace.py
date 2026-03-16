import traceback
import sys
import os

# Ensure the backend directory is in the path
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.stats_routes import get_dashboard_stats

db = SessionLocal()
class DummyUser:
    email = "debug@debug.com"
    full_name = "Debug User"

try:
    print("Executing get_dashboard_stats...")
    result = get_dashboard_stats(db, current_user=DummyUser())
    print("Execution Success! Attempting JSON serialization...")
    import json
    from datetime import datetime
    
    def json_serial(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError (f"Type {type(obj)} not serializable")

    print(json.dumps(result, indent=2, default=str))
    print("Serialization Success!")
except Exception:
    print("Caught Exception:")
    traceback.print_exc()
finally:
    db.close()
