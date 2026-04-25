
import asyncio
from sqlalchemy import text
from app.database import async_engine

async def migrate():
    async with async_engine.begin() as conn:
        print("Migrating Candidate table...")
        try:
            await conn.execute(text("ALTER TABLE candidates ADD COLUMN pan_no VARCHAR(50)"))
            print("Added pan_no")
        except Exception as e: print(f"pan_no error: {e}")
        
        try:
            await conn.execute(text("ALTER TABLE candidates ADD COLUMN passport_no VARCHAR(50)"))
            print("Added passport_no")
        except Exception as e: print(f"passport_no error: {e}")
        
        try:
            await conn.execute(text("ALTER TABLE candidates ADD COLUMN nationality VARCHAR(100)"))
            print("Added nationality")
        except Exception as e: print(f"nationality error: {e}")
        
        try:
            await conn.execute(text("ALTER TABLE candidates ADD COLUMN identity_type VARCHAR(100)"))
            print("Added identity_type")
        except Exception as e: print(f"identity_type error: {e}")
        
        try:
            await conn.execute(text("ALTER TABLE candidates ADD COLUMN db_candidate_name VARCHAR(255)"))
            print("Added db_candidate_name")
        except Exception as e: print(f"db_candidate_name error: {e}")
        
        try:
            await conn.execute(text("ALTER TABLE candidates ADD COLUMN db_dob DATE"))
            print("Added db_dob")
        except Exception as e: print(f"db_dob error: {e}")
        
        try:
            await conn.execute(text("ALTER TABLE candidates ADD COLUMN database_scope VARCHAR(255)"))
            print("Added database_scope")
        except Exception as e: print(f"database_scope error: {e}")
        
        print("Migration complete.")

if __name__ == "__main__":
    asyncio.run(migrate())
