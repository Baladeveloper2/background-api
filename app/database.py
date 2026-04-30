import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Primary URLs
RAW_URL = os.getenv("DATABASE_URL", "mysql://root:password@localhost/bgv_db")
# Potential Read-Replica URL (falls back to primary)
READ_RAW_URL = os.getenv("DATABASE_READ_URL", RAW_URL)

# Driver formatting
def get_url_with_driver(url, driver):
    if "://" in url:
        base = url.split("://")[1]
        return f"mysql+{driver}://{base}"
    return url

ASYNC_URL = get_url_with_driver(RAW_URL, "aiomysql")
SYNC_URL = get_url_with_driver(RAW_URL, "pymysql")
READ_ASYNC_URL = get_url_with_driver(READ_RAW_URL, "aiomysql")

# Primary Async Engine
async_engine = create_async_engine(
    ASYNC_URL,
    pool_size=20, max_overflow=30, pool_recycle=1800, pool_pre_ping=True, pool_timeout=30
)
# Read-Only Async Engine (Clustered Support)
read_engine = create_async_engine(
    READ_ASYNC_URL,
    pool_size=40, max_overflow=60, pool_recycle=1800, pool_pre_ping=True, pool_timeout=30
) if READ_ASYNC_URL != ASYNC_URL else async_engine

AsyncSessionLocal = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
ReadSessionLocal = async_sessionmaker(bind=read_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

# Sync Engine and Session (Legacy)
sync_engine = create_engine(SYNC_URL, pool_pre_ping=True, pool_recycle=1800)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

Base = declarative_base()

from contextlib import asynccontextmanager

# Async Dependency (Primary/Write)
@asynccontextmanager
async def get_async_db_context():
    async with AsyncSessionLocal() as session:
        yield session

async def get_async_db():
    async with AsyncSessionLocal() as session:
        yield session

# Async Dependency (Read-Only/Reporting)
@asynccontextmanager
async def get_read_db_context():
    async with ReadSessionLocal() as session:
        yield session

async def get_read_db():
    async with ReadSessionLocal() as session:
        yield session

# Sync Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Alias for backward compatibility with patched routes
get_db_sync = get_db

# For backward compatibility
engine = sync_engine
SQLALCHEMY_DATABASE_URL = SYNC_URL
