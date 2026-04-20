import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL not found in .env")
    exit(1)

# Ensure matching driver
if DATABASE_URL.startswith("mysql:"):
    DATABASE_URL = DATABASE_URL.replace("mysql:", "mysql+pymysql:", 1)

engine = create_engine(DATABASE_URL)

def run_migrations():
    commands = [
        "ALTER TABLE cases ADD COLUMN verifier_revoke_count INT DEFAULT 0;",
        "ALTER TABLE cases ADD COLUMN qc_revoke_count INT DEFAULT 0;",
        "ALTER TABLE cases ADD COLUMN is_in_tat INT DEFAULT 1;"
    ]
    
    with engine.connect() as connection:
        for command in commands:
            print(f"Executing: {command}")
            try:
                connection.execute(text(command))
                connection.commit()
                print("Success.")
            except Exception as e:
                print(f"Error executing {command}: {e}")

if __name__ == "__main__":
    run_migrations()
