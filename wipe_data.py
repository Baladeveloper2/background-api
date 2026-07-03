import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

engine = create_async_engine(os.getenv('DATABASE_URL'))

async def run():
    async with engine.begin() as conn:
        print("Wiping data...")
        await conn.execute(text("DELETE FROM client_documents"))
        await conn.execute(text("DELETE FROM audit_logs"))
        await conn.execute(text("DELETE FROM notifications"))
        
        await conn.execute(text("DELETE FROM insufficiencies"))
        await conn.execute(text("DELETE FROM verifier_assignments"))
        await conn.execute(text("DELETE FROM verification_checks"))
        await conn.execute(text("DELETE FROM case_activity"))
        await conn.execute(text("DELETE FROM cases"))
        await conn.execute(text("DELETE FROM candidates"))
        
        # Keep super admins
        await conn.execute(text("DELETE FROM users WHERE role != 'SUPER_ADMIN'"))
        
        await conn.execute(text("DELETE FROM branches"))
        await conn.execute(text("DELETE FROM customers"))
        await conn.execute(text("DELETE FROM zones"))
        print("Done wiping!")

if __name__ == "__main__":
    asyncio.run(run())
