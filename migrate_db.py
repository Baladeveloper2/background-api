from app.database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        print("Starting migration...")
        
        # 1. Rename package_enabled to active_status if it exists and active_status doesn't
        try:
            conn.execute(text("ALTER TABLE customers CHANGE package_enabled active_status INT DEFAULT 1"))
            conn.commit()
            print("Renamed package_enabled to active_status")
        except Exception as e:
            print(f"Could not rename package_enabled (might already be renamed or missing): {e}")

        # 2. Check if short_code exists and city is empty, then migrate short_code to city
        try:
             # We already saw 'city' and 'short_code' both exist in DESCRIBE result.
             # Let's copy values if city is null
             conn.execute(text("UPDATE customers SET city = short_code WHERE city IS NULL AND short_code IS NOT NULL"))
             conn.commit()
             print("Migrated short_code data to city")
        except Exception as e:
             print(f"Could not migrate short_code: {e}")

        print("Migration complete.")

if __name__ == "__main__":
    migrate()
