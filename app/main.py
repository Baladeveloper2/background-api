from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, get_db
from sqlalchemy import text
from . import models, auth_routes, customer_routes, partner_routes, user_routes, candidate_routes, batch_routes, case_routes, verification_routes, stats_routes, role_routes, media_routes, database
import os

# Create tables
# In development, auto-create tables. Use Alembic for real migrations.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="BGVMS API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://background-verification-topaz.vercel.app",
        "https://background-verification-91d11.web.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        
        return {
            "status": "ok", 
            "database": "connected",
            "user_query": getattr(user, 'email', 'None')
        }
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}

