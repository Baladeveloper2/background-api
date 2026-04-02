import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/bgvms")
engine = create_engine(DATABASE_URL)

def run_migrations():
    commands = [
        # Fix Enum columns to be VARCHAR(50)
        "ALTER TABLE users MODIFY status VARCHAR(50);",
        "ALTER TABLE partners MODIFY status VARCHAR(50);",
        "ALTER TABLE cases MODIFY status VARCHAR(50);",
        "ALTER TABLE verification_checks MODIFY status VARCHAR(50);",
        
        # Upgrade TEXT columns to MEDIUMTEXT for large JSON/Base64 data
        "ALTER TABLE verification_checks MODIFY data MEDIUMTEXT;",
        "ALTER TABLE candidates MODIFY address_details MEDIUMTEXT;",
        "ALTER TABLE candidates MODIFY documents MEDIUMTEXT;"
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
