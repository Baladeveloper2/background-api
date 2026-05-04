from fastapi import FastAPI, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from . import (
    models, auth_routes, customer_routes, partner_routes, 
    user_routes, candidate_routes, batch_routes, case_routes, 
    verification_routes, stats_routes, role_routes, media_routes,
    notification_routes, ai_routes, billing_routes, client_doc_routes,
    public_routes
)


from .database import engine, Base, get_async_db, async_engine
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from .auth_routes import limiter
from .logging_config import setup_logging, logger, instrument_sqlalchemy
from .cache import get_redis_client
from contextlib import asynccontextmanager
from fastapi.middleware.gzip import GZipMiddleware
import os
import asyncio

# Initialize structured logging
setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Instrument SQLAlchemy for Performance Profiling (Slow Query Detection)
    # instrument_sqlalchemy(async_engine.sync_engine)
    
    yield
    # Shutdown: Dispose of the async engine to avoid event loop errors
    await async_engine.dispose()

# Database tables should be managed by alembic migrations in production, not auto-generated
# Base.metadata.create_all(bind=engine)

app = FastAPI(title="BGVMS API", lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error("Validation failed", extra={"path": request.url.path, "errors": exc.errors()})
    
    # Sanitize body for JSON serialization (specifically handle starlette FormData)
    body_serialized = None
    try:
        from starlette.datastructures import FormData
        if isinstance(exc.body, FormData):
            # Convert FormData to a flat dict, excluding file objects which are non-serializable
            body_serialized = {k: v for k, v in exc.body.items() if not hasattr(v, 'file')}
        else:
            body_serialized = exc.body
    except Exception:
        body_serialized = "Unserializable Body Content"

    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": body_serialized},
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

# Custom Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: http://localhost:8000 https://res.cloudinary.com https://*.amazonaws.com; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; frame-ancestors 'self' http://localhost:5173;"
    return response

# Versioned API Router
api_v1 = APIRouter(prefix="/api/v1")

api_v1.include_router(auth_routes.router)
api_v1.include_router(customer_routes.router)
api_v1.include_router(partner_routes.router)
api_v1.include_router(user_routes.router)
api_v1.include_router(candidate_routes.router)
api_v1.include_router(batch_routes.router)
api_v1.include_router(case_routes.router)
api_v1.include_router(verification_routes.router)
api_v1.include_router(stats_routes.router)
api_v1.include_router(role_routes.router)
api_v1.include_router(media_routes.router)
api_v1.include_router(notification_routes.router)
api_v1.include_router(ai_routes.router)
api_v1.include_router(billing_routes.router)
api_v1.include_router(client_doc_routes.router)
api_v1.include_router(public_routes.router)



app.include_router(api_v1)

import json
from .ws import manager, WebSocketDisconnect, WebSocket
@app.websocket("/ws")
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str = "anonymous"):
    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "JOIN_ROOM":
                    await manager.join_room(user_id, msg.get("case_id"))
                elif msg.get("type") == "LEAVE_ROOM":
                    await manager.leave_room(user_id, msg.get("case_id"))
            except Exception:
                pass # Ignore malformed json
    except WebSocketDisconnect:
        await manager.disconnect(websocket, user_id)

@app.websocket("/ws/presence/{case_id}")
async def presence_handler(websocket: WebSocket, case_id: str):
    # Extract user_id from token if possible, or use anonymous
    token = websocket.query_params.get("token")
    user_id = "anonymous"
    if token:
        try:
            from jose import jwt
            from . import auth
            payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
            user_id = payload.get("id", payload.get("sub", "anonymous"))
        except Exception as e:
            logger.error(f"WebSocket JWT validation failed: {str(e)}")
            pass
            
    await manager.connect(websocket, user_id)
    await manager.join_room(user_id, case_id)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.leave_room(user_id, case_id)
        await manager.disconnect(websocket, user_id)

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
            "cache": "local-memory",
            "user_query": getattr(user, 'email', 'None')
        }
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}

 
