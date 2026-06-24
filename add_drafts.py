from app.database import engine
from app.models import Base
from sqlalchemy import text

def upgrade_db():
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE batches ADD COLUMN status VARCHAR(50) DEFAULT 'DRAFT'"))
            print("Added status column to batches")
        except Exception as e:
            print("Status column might already exist:", e)

    Base.metadata.create_all(engine)
    print("Created CandidateDraft table if not exists")

if __name__ == "__main__":
    upgrade_db()
