
import asyncio
from sqlalchemy import select
from app.database import SessionLocal, async_engine
from app import models

async def dump_batches():
    async with async_engine.connect() as conn:
        res = await conn.execute(select(models.Batch.batch_no, models.Batch.cl_ref_no).limit(10))
        batches = res.all()
        for b in batches:
            print(f"Batch No: {b.batch_no}, CL Ref: {b.cl_ref_no}")

if __name__ == "__main__":
    asyncio.run(dump_batches())
