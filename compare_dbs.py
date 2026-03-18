from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

def check_db(db_name):
    url = f"mysql+pymysql://avnadmin:AVNS_ce7C0cV_01nkFa1rYPq@dataentry-dataentry.j.aivencloud.com:14419/{db_name}"
    print(f"\nChecking database: {db_name}")
    try:
        engine = create_engine(url, connect_args={"ssl": {}})
        with engine.connect() as conn:
            res = conn.execute(text("SHOW TABLES"))
            tables = [r[0] for r in res]
            print(f"Tables: {tables}")
            if "customers" in tables:
                res = conn.execute(text("DESCRIBE customers"))
                cols = [r[0] for r in res]
                print(f"Columns in customers: {cols}")
                res = conn.execute(text("SELECT count(*) FROM customers"))
                print(f"Row count: {res.scalar()}")
    except Exception as e:
        print(f"Error checking {db_name}: {e}")

check_db("defaultdb")
check_db("bgvms")
