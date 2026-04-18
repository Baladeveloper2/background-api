from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from . import (
    models, auth_routes, customer_routes, partner_routes, 
    user_routes, candidate_routes, batch_routes, case_routes, 
    verification_routes, stats_routes, role_routes, media_routes
)
from .database import engine, Base, get_async_db, async_engine
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import _rate_limit_exceeded_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from .auth_routes import limiter
import logging
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic can go here
    yield
    # Shutdown logic: Dispose of the async engine to avoid event loop errors
    await async_engine.dispose()

# Database tables should be managed by alembic migrations in production, not auto-generated
# Base.metadata.create_all(bind=engine)

app = FastAPI(title="BGVMS API", lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print(f"DEBUG: Validation error on {request.url.path}")
    print(f"DEBUG: Error details: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://[::1]:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://background-verification-topaz.vercel.app",
        "https://background-verification-91d11.web.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"]
)

app.include_router(auth_routes.router)
app.include_router(customer_routes.router)
app.include_router(partner_routes.router)
app.include_router(user_routes.router)
app.include_router(candidate_routes.router)
app.include_router(batch_routes.router)
app.include_router(case_routes.router)
app.include_router(verification_routes.router)
app.include_router(stats_routes.router)
app.include_router(role_routes.router)
app.include_router(media_routes.router)

from .ws import manager, WebSocketDisconnect, WebSocket
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("")
async def root():
    return {"message": "Welcome to Background Verification Management System API"}

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_async_db)):
    try:
        # Try to execute a simple query
        await db.execute(text("SELECT 1"))
        
        # Test User Query
        res = await db.execute(select(models.User).limit(1))
        user = res.scalar_one_or_none()
        
        return {
            "status": "ok", 
            "database": "connected",
            "user_query": getattr(user, 'email', 'None')
        }
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}

