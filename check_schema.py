import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/bgvms")
engine = create_engine(DATABASE_URL)

def check_schema():
    tables = ["users", "partners", "cases", "verification_checks", "candidates"]
    with engine.connect() as connection:
        for table in tables:
            print(f"\n--- Schema for {table} ---")
            result = connection.execute(text(f"DESCRIBE {table}"))
            for row in result:
                print(row)

if __name__ == "__main__":
    check_schema()
