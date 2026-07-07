import sys
import json
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
import app.models as models

async def update_cand():
    engine = create_async_engine('mysql+aiomysql://avnadmin:AVNS_ce7C0cV_01nkFa1rYPq@dataentry-dataentry.j.aivencloud.com:14419/defaultdb')
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        cand_id = "3886e75c-6944-4c7c-9741-867b77033b6d"
        cand = await session.get(models.Candidate, cand_id)
        print("Before:", cand.address_details)
        cand.address_details = {"employments": [{"company": "Python Test"}]}
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(cand, "address_details")
        await session.commit()
        
        cand2 = await session.get(models.Candidate, cand_id)
        print("After:", cand2.address_details)

if __name__ == "__main__":
    asyncio.run(update_cand())
