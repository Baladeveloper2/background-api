
import asyncio
import os
from sqlalchemy import text
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

async def check_all_schemas():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url: return
    
    # Try to connect without a specific database to see all
    base_url = db_url.rsplit("/", 1)[0] + "/information_schema"
    # Actually, just connect to the host
    
    engine = create_async_engine(db_url.replace("pymysql", "aiomysql"))
    
    async with engine.connect() as conn:
        print(f"Connected to: {engine.url.database}")
        
        # Check bgvms if it exists
        print("Checking if 'bgvms' database exists...")
        res = await conn.execute(text("SHOW DATABASES LIKE 'bgvms'"))
        if res.fetchone():
            print("DATABASE 'bgvms' EXISTS!")
            # Switch to bgvms and check notifications
            await conn.execute(text("USE bgvms"))
            res2 = await conn.execute(text("SHOW TABLES LIKE 'notifications'"))
            if res2.fetchone():
                print("Table 'notifications' exists in 'bgvms'. Describing...")
                res3 = await conn.execute(text("DESCRIBE notifications"))
                for row in res3.fetchall():
                    print(row)
            else:
                print("Table 'notifications' NOT found in 'bgvms'.")
        else:
            print("DATABASE 'bgvms' NOT FOUND.")

if __name__ == "__main__":
    asyncio.run(check_all_schemas())
