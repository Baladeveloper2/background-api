import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "mysql+aiomysql://avnadmin:AVNS_ce7C0cV_01nkFa1rYPq@dataentry-dataentry.j.aivencloud.com:14419/defaultdb"

async def alter_table():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE insufficiencies ADD COLUMN priority VARCHAR(50) DEFAULT 'Medium';"))
            print("Successfully added priority column to insufficiencies.")
        except Exception as e:
            print(f"Error: {e}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(alter_table())
