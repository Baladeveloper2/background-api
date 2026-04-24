
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL").replace("mysql+aiomysql", "mysql+pymysql")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # Check column
    res = conn.execute(text("DESCRIBE cases"))
    cols = [r[0] for r in res.fetchall()]
    print(f"HAS COLUMN: {'insufficiency_count' in cols}")
    
    # Check table
    res = conn.execute(text("SHOW TABLES LIKE 'insufficiency_logs'"))
    tables = res.fetchall()
    print(f"HAS TABLE: {len(tables) > 0}")
