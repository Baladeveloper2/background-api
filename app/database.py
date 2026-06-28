import os
import socket
import urllib.parse
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("app.database")

def resolve_db_url(url: str) -> str:
    """
    Parses the database URL, resolves the hostname to an IP address,
    and returns the URL with the resolved IP address to bypass flaky DNS
    resolution. Falls back to a known IP if resolution completely fails
    for the primary Aiven host.
    """
    if not url:
        return url
    try:
        parsed = urllib.parse.urlsplit(url)
        hostname = parsed.hostname
        if not hostname:
            return url
            
        resolved_ip = None
        try:
            # Force IPv4 first, as IPv6 can be the source of getaddrinfo issues on Windows/asyncio
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_INET)
            if addr_info:
                resolved_ip = addr_info[0][4][0]
        except Exception as e:
            logger.warning(f"Failed to resolve {hostname} via IPv4: {e}")
            try:
                # Fallback to default resolution
                addr_info = socket.getaddrinfo(hostname, None)
                if addr_info:
                    resolved_ip = addr_info[0][4][0]
            except Exception as ex:
                logger.warning(f"Failed to resolve {hostname} via default DNS: {ex}")
                
        if not resolved_ip:
            if hostname == "dataentry-dataentry.j.aivencloud.com":
                resolved_ip = "139.59.122.93"
                logger.info(f"Using fallback hardcoded IP for {hostname}: {resolved_ip}")
            else:
                return url
        else:
            logger.info(f"Resolved database host {hostname} -> {resolved_ip}")

        # Reconstruct the URL with the resolved IP
        netloc_host = f"[{resolved_ip}]" if ":" in resolved_ip else resolved_ip
        if parsed.port:
            netloc_host = f"{netloc_host}:{parsed.port}"
        
        userinfo = ""
        if parsed.username:
            userinfo = parsed.username
            if parsed.password is not None:
                userinfo = f"{userinfo}:{parsed.password}"
            userinfo = f"{userinfo}@"
            
        new_netloc = f"{userinfo}{netloc_host}"
        new_parsed = parsed._replace(netloc=new_netloc)
        return urllib.parse.urlunsplit(new_parsed)
    except Exception as e:
        logger.error(f"Error while resolving database URL {url}: {e}")
        return url

# Primary URLs
RAW_URL = resolve_db_url(os.getenv("DATABASE_URL", "mysql://root:password@localhost/bgv_db"))
# Potential Read-Replica URL (falls back to primary)
READ_RAW_URL = resolve_db_url(os.getenv("DATABASE_READ_URL", RAW_URL))

# Driver formatting
def get_url_with_driver(url, driver):
    if "://" in url:
        base = url.split("://")[1]
        return f"mysql+{driver}://{base}"
    return url

ASYNC_URL = get_url_with_driver(RAW_URL, "aiomysql")
SYNC_URL = get_url_with_driver(RAW_URL, "pymysql")
READ_ASYNC_URL = get_url_with_driver(READ_RAW_URL, "aiomysql")

# ─────────────────────────────────────────────────────────────────────────────
# IMPORTANT: Aiven MySQL plan max_connections = 76.
# Budget per process (uvicorn reload spawns 2):
#   async_engine  : pool_size=5  max_overflow=5  → up to 10 connections
#   sync_engine   : pool_size=3  max_overflow=2  → up to  5 connections (legacy)
#   Total per process ≈ 15 · 2 processes = 30 + 5 headroom for admin = 35 << 76
# ─────────────────────────────────────────────────────────────────────────────

# Primary Async Engine
async_engine = create_async_engine(
    ASYNC_URL,
    poolclass=NullPool,
    connect_args={"connect_timeout": 10},
)
# Read-Only Async Engine
read_engine = create_async_engine(
    READ_ASYNC_URL,
    poolclass=NullPool,
    connect_args={"connect_timeout": 10},
) if READ_ASYNC_URL != ASYNC_URL else async_engine

AsyncSessionLocal = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
ReadSessionLocal = async_sessionmaker(bind=read_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

# Sync Engine and Session (Legacy — used only by Celery workers and admin scripts)
# Keep pool very small; async engine handles all web requests
sync_engine = create_engine(
    SYNC_URL,
    pool_size=3,
    max_overflow=2,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"connect_timeout": 10},
)
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
