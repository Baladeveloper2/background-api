import os
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv
from app import models
from app.database import engine

load_dotenv()

def migrate():
    print("Starting migration...")
    inspector = inspect(engine)
    
    # Create tables if they don't exist (e.g. roles, modules)
    print("Creating missing tables...")
    models.Base.metadata.create_all(bind=engine)
    
    # Check if 'role_id' column exists in 'users'
    columns = [col['name'] for col in inspector.get_columns('users')]
    if 'role_id' not in columns:
        print("Adding 'role_id' column to 'users' table...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN role_id VARCHAR(36) REFERENCES roles(id)"))
            conn.commit()
            print("Successfully added 'role_id'.")
    else:
        print("'role_id' column already exists.")

if __name__ == "__main__":
    migrate()
    print("Migration finished successfully.")
