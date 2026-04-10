import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as connection:
    result = connection.execute(text("SELECT id, case_ref_no, status, assigned_to FROM cases WHERE status = 'QC'"))
    for row in result:
        print(row)
