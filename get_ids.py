import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as connection:
    user = connection.execute(text("SELECT id FROM users WHERE email='qa.audit@cl-edge.com'")).fetchone()
    case = connection.execute(text("SELECT id FROM cases WHERE status='QC'")).fetchone()
    if user and case:
        print(f"USER_ID: {user[0]}")
        print(f"CASE_ID: {case[0]}")
    else:
        print("Missing user or case")
