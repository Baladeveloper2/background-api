import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# We can import get_dashboard_stats from app.stats_routes directly!
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.stats_routes import get_dashboard_stats
from app.models import User

load_dotenv()
db_url = os.getenv("DATABASE_URL")
if "mysql+aiomysql" not in db_url:
    db_url = db_url.replace("mysql+pymysql", "mysql+aiomysql").replace("mysql:", "mysql+aiomysql:", 1)

async def main():
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Get an active admin user to simulate
        from sqlalchemy import select
        user_res = await db.execute(select(User).filter(User.role == "SUPER_ADMIN").limit(1))
        user = user_res.scalar()
        if not user:
            print("No admin user found!")
            return
            
        print(f"Simulating as user: {user.email}")
        
        # 1. Query with NO filters
        stats_no_filters = await get_dashboard_stats(db=db, current_user=user)
        print("\n=== STATS WITH NO FILTERS ===")
        for k in ["positive_count", "negative_count", "pending_verification", "insufficient_cases", "in_tat_count", "at_risk_count", "out_tat_count"]:
            print(f"{k}: {stats_no_filters.get(k)}")
            
        # 2. Query with Apex Covantage filter
        stats_filtered = await get_dashboard_stats(client="Apex Covantage India Private Limited", from_date="2026-05-01", to_date="2026-05-15", db=db, current_user=user)
        print("\n=== STATS WITH APEX COVANTAGE & DATE FILTER ===")
        for k in ["positive_count", "negative_count", "pending_verification", "insufficient_cases", "in_tat_count", "at_risk_count", "out_tat_count"]:
            print(f"{k}: {stats_filtered.get(k)}")

if __name__ == "__main__":
    asyncio.run(main())
