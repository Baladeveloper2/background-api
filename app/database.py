import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Get the base URL from environment (we'll swap drivers as needed)
RAW_URL = os.getenv("DATABASE_URL", "mysql://root:password@localhost/bgv_db")

# Ensure the Raw URL doesn't have a protocol prefix that includes a driver yet
# or handle it if it does
def get_url_with_driver(url, driver):
    if "://" in url:
        base = url.split("://")[1]
        return f"mysql+{driver}://{base}"
    return url

ASYNC_URL = get_url_with_driver(RAW_URL, "aiomysql")
SYNC_URL = get_url_with_driver(RAW_URL, "pymysql")

# Async Engine and Session
async_engine = create_async_engine(
    ASYNC_URL,
    pool_size=20,
    max_overflow=30,
    pool_recycle=3600,
    pool_pre_ping=True
)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# Sync Engine and Session (Legacy)
sync_engine = create_engine(
    SYNC_URL,
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

Base = declarative_base()

# Async Dependency
async def get_async_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

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
