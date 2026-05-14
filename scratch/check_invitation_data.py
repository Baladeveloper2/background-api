
import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and "mysql" in DATABASE_URL and "+aiomysql" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+aiomysql://")

async def check():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        res = await session.execute(text("SELECT id, status, received_date FROM cases WHERE status = 'DOCUMENTS_SUBMITTED' LIMIT 5"))
        cases = res.fetchall()
        print("Cases with DOCUMENTS_SUBMITTED:")
        for c in cases:
            print(f"ID: {c[0]}, Status: {c[1]}, Received Date: {c[2]}")
            
        res = await session.execute(text("SELECT id, status, received_date FROM cases WHERE status = 'LINK_SHARED' LIMIT 5"))
        cases = res.fetchall()
        print("\nCases with LINK_SHARED:")
        for c in cases:
            print(f"ID: {c[0]}, Status: {c[1]}, Received Date: {c[2]}")

if __name__ == "__main__":
    asyncio.run(check())
