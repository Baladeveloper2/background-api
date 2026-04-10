import requests

base_url = "http://localhost:8000"
case_id = "d2582b8d-6289-4c4a-9359-3560ff2705e2"
user_id = "c3a21505-b960-4590-be8b-57db8f1d8213"

payload = {
    "case_ids": [case_id],
    "user_id": user_id
}

response = requests.post(f"{base_url}/cases/bulk-allocate", json=payload)
print(response.status_code)
print(response.json())

# Verify in DB
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))
with engine.connect() as conn:
    res = conn.execute(text(f"SELECT assigned_to FROM cases WHERE id='{case_id}'")).fetchone()
    print(f"Verified Assigned To: {res[0]}")
