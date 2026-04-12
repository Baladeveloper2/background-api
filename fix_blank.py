import os
import sqlalchemy
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

engine = sqlalchemy.create_engine(os.getenv('DATABASE_URL'))
with engine.connect() as conn:
    conn.execute(text("UPDATE users SET role = 'SUPER_ADMIN' WHERE email = 'bala@bgvms.com'"))
    # Also unallocate some cases so the buffer is not empty
    conn.execute(text("UPDATE cases SET assigned_to = NULL"))
    conn.commit()
    print("Upgraded Bala to SUPER_ADMIN and unallocated all cases.")
