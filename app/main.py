from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from . import auth_routes, customer_routes, user_routes, candidate_routes, batch_routes, case_routes, verification_routes, stats_routes, role_routes
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
        "https://background-verification-topaz.vercel.app" # Production frontend
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
