from app.database import sync_engine as engine, Base
from app import models

def create_tables():
    # This will create any missing tables, including the new 'insufficiencies' table
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully")

if __name__ == "__main__":
    create_tables()
