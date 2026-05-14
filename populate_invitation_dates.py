
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and "mysql" in DATABASE_URL and "+pymysql" not in DATABASE_URL:
    if "://" in DATABASE_URL:
        proto, rest = DATABASE_URL.split("://")
        DATABASE_URL = "mysql+pymysql://" + rest

engine = create_engine(DATABASE_URL)

def populate_dates():
    with engine.connect() as conn:
        print("Populating missing link_shared_at and submitted_at for existing cases...")
        
        # For LINK_SHARED, use received_date as a proxy
        conn.execute(text("UPDATE cases SET link_shared_at = received_date WHERE status = 'LINK_SHARED' AND link_shared_at IS NULL"))
        
        # For DOCUMENTS_SUBMITTED, use received_date as a proxy for link_shared_at, and received_date + 1 day for submitted_at if null
        # Actually, let's just use received_date for both for now to avoid the dash.
        conn.execute(text("UPDATE cases SET link_shared_at = received_date WHERE status = 'DOCUMENTS_SUBMITTED' AND link_shared_at IS NULL"))
        conn.execute(text("UPDATE cases SET submitted_at = received_date WHERE status = 'DOCUMENTS_SUBMITTED' AND submitted_at IS NULL"))
        
        print("Successfully populated missing dates.")
        conn.commit()

if __name__ == "__main__":
    populate_dates()
