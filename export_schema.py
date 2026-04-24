
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("DATABASE_URL").replace("aiomysql", "pymysql")
engine = create_engine(url)
with engine.connect() as conn:
    schema = conn.execute(text("SHOW CREATE TABLE cases")).fetchone()[1]
    with open("cases_schema.txt", "w", encoding="utf-8") as f:
        f.write(schema)
    
    schema_users = conn.execute(text("SHOW CREATE TABLE users")).fetchone()[1]
    with open("users_schema.txt", "w", encoding="utf-8") as f:
        f.write(schema_users)
