import os
from sqlalchemy import create_engine
from sqlalchemy.sql import text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/bgvms")

print(f"Testing connection to: {DATABASE_URL}")

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        result = connection.execute(text("SELECT * FROM users"))
        print(f"Query successful! Found {result.rowcount} rows.")
        for row in result:
            print(row)

except Exception as e:
    print(f"Connection failed: {e}")
