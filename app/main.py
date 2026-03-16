from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, get_db
from sqlalchemy import text
from . import models, auth_routes, customer_routes, user_routes, candidate_routes, batch_routes, case_routes, verification_routes, stats_routes, role_routes
import os

# Create tables
# In development, auto-create tables. Use Alembic for real migrations.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="BGVMS API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", # Local development
        "https://background-verification-topaz.vercel.app", # Production frontend
        "https://background-verification-91d11.web.app" # Production frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(customer_routes.router)
app.include_router(user_routes.router)
app.include_router(candidate_routes.router)
app.include_router(batch_routes.router)
app.include_router(case_routes.router)
app.include_router(verification_routes.router)
app.include_router(stats_routes.router)
app.include_router(role_routes.router)

@app.get("/")
async def root():
    return {"message": "Welcome to Background Verification Management System API"}

@app.get("/health")
async def health_check(db = Depends(get_db)):
    try:
        # Try to execute a simple query
        db.execute(text("SELECT 1"))
        
        # Test User Query
        user = db.query(models.User).first()
        user_email = user.email if user else "No users in DB"
        
        # Test Passlib / bcrypt (Common fail point on Linux/Python 3.12+)
        from .auth import verify_password
        test_hash = verify_password("admin123", "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIQGfP1cW")
        
        return {
            "status": "ok", 
            "database": "connected", 
            "user_query": getattr(user, 'email', 'None'),
            "passlib_test": test_hash
        }
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}

