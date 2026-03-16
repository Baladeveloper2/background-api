from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text(
        "ALTER TABLE users MODIFY COLUMN role "
        "ENUM('SUPER_ADMIN','ADMIN','MANAGER','VERIFIER','QC','CUSTOMER','CANDIDATE','USER') "
        "NOT NULL DEFAULT 'USER'"
    ))
    conn.commit()
    print('Done: USER enum value added to users.role column')
