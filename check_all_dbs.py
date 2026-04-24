
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
raw_url = os.getenv("DATABASE_URL").replace("mysql+aiomysql", "mysql+pymysql")

target_dbs = ["defaultdb", "bgvms"]

for db_name in target_dbs:
    url = raw_url.rsplit('/', 1)[0] + '/' + db_name
    print(f"--- Checking {db_name} ---")
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            res = conn.execute(text("DESCRIBE cases"))
            cols = [r[0] for r in res.fetchall()]
            print(f"Cases has insufficiency_count: {'insufficiency_count' in cols}")
            
            res = conn.execute(text("SHOW TABLES LIKE 'insufficiency_logs'"))
            print(f"Has insufficiency_logs table: {len(res.fetchall()) > 0}")
    except Exception as e:
        print(f"Error checking {db_name}: {e}")
