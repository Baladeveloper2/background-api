
import os
import asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app import models, enums

async def test_sql():
    # Setup dummy engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    # Simulate conditions
    status = "LINK_SHARED"
    allowed_statuses = [enums.CaseStatus.PENDING, enums.CaseStatus.LINK_SHARED, enums.CaseStatus.DOCUMENTS_SUBMITTED]
    base_conditions = []
    
    if status and status != 'ALL':
        base_conditions.append(models.Case.status == status)
    else:
        base_conditions.append(models.Case.status.in_(allowed_statuses))
        
    stmt = select(models.Case).filter(*base_conditions)
    
    # Check generated SQL
    print(f"Generated SQL: {stmt}")

if __name__ == "__main__":
    asyncio.run(test_sql())
