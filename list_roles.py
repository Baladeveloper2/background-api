import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as connection:
    result = connection.execute(text("SELECT id, name FROM roles"))
    for row in result:
        print(row)
