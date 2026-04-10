import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    roles = conn.execute(text("SELECT id, name FROM roles")).fetchall()
    print("ALL ROLES:")
    for r in roles:
        print(f"ID: {r[0]} | NAME: {r[1]}")
    
    users = conn.execute(text("SELECT email, full_name, role_id FROM users")).fetchall()
    print("\nALL USERS:")
    for u in users:
        role_name = next((r[1] for r in roles if r[0] == u[2]), "No Role Assigned")
        print(f"EMAIL: {u[0]} | NAME: {u[1]} | ROLE_ID: {u[2]} | ROLE_NAME: {role_name}")
