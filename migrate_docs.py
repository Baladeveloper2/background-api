import asyncio
from sqlalchemy import text
from app.database import async_engine

async def update_schema():
    print("Initiating schema migration for client_documents...")
    async with async_engine.connect() as conn:
        try:
            # Add is_read column
            await conn.execute(text("ALTER TABLE client_documents ADD COLUMN is_read BOOLEAN DEFAULT FALSE"))
            print("Added is_read column.")
        except Exception as e:
            print(f"is_read might already exist or error: {str(e)[:100]}...")

        try:
            # Add read_at column
            await conn.execute(text("ALTER TABLE client_documents ADD COLUMN read_at DATETIME NULL"))
            print("Added read_at column.")
        except Exception as e:
            print(f"read_at might already exist or error: {str(e)[:100]}...")

        try:
            # Add read_by column
            await conn.execute(text("ALTER TABLE client_documents ADD COLUMN read_by VARCHAR(36) NULL"))
            print("Added read_by column.")
        except Exception as e:
            print(f"read_by might already exist or error: {str(e)[:100]}...")
            
        await conn.commit()

    print("Schema migration complete.")

if __name__ == "__main__":
    asyncio.run(update_schema())
