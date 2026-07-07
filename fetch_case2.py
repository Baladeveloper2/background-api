import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

engine = create_engine('sqlite:///d:/project/backend/app.db')  # or wherever it is
# Let's try to find the db.
