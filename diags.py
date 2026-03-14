import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import traceback

load_dotenv()
try:
    engine = create_engine(os.environ.get("DATABASE_URL"))
    with engine.connect() as conn:
        res = conn.execute(text("SELECT * FROM users LIMIT 1"))
        row = res.fetchone()
        print("Row:", row)
except Exception as e:
    print("Error occurred:")
    traceback.print_exc()
