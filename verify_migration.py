
import asyncio
import sys
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, '.')
from app.database import async_engine

async def verify():
    async with async_engine.connect() as conn:
        # Check column
        result = await conn.execute(text("DESCRIBE cases"))
        columns = [row[0] for row in result.fetchall()]
        print(f"Cases columns: {columns}")
        
        # Check table
        result = await conn.execute(text("SHOW TABLES"))
        tables = [row[0] for row in result.fetchall()]
        print(f"Tables: {tables}")
        
        if 'insufficiency_count' in columns:
            print("VERIFIED: insufficiency_count exists.")
        else:
            print("FAILED: insufficiency_count NOT found.")
            
        if 'insufficiency_logs' in tables:
            print("VERIFIED: insufficiency_logs table exists.")
        else:
            print("FAILED: insufficiency_logs table NOT found.")

if __name__ == "__main__":
    asyncio.run(verify())
