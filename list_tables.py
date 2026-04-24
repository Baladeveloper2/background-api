
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("DATABASE_URL").replace("aiomysql", "pymysql")
engine = create_engine(url)
with engine.connect() as conn:
    tables = [r[0] for r in conn.execute(text("SHOW TABLES")).fetchall()]
    print("Tables found:")
    for t in sorted(tables):
        print(f" - {t}")
