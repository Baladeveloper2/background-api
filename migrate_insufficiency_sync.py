
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL not found in .env")
    exit(1)

# Use synchronous driver for DDL if needed
if "mysql+aiomysql" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("mysql+aiomysql", "mysql+pymysql")
elif DATABASE_URL.startswith("mysql:"):
    DATABASE_URL = DATABASE_URL.replace("mysql:", "mysql+pymysql:", 1)

engine = create_engine(DATABASE_URL)

def run_migrations():
    with engine.connect() as connection:
        # 1. Add insufficiency_count column
        print("Checking/Adding insufficiency_count...")
        try:
            connection.execute(text("ALTER TABLE cases ADD COLUMN insufficiency_count INT DEFAULT 0;"))
            connection.commit()
            print("Success.")
        except Exception as e:
            print(f"Column check/add note: {e}")

        # 2. Create insufficiency_logs table
        print("Creating insufficiency_logs table...")
        try:
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS insufficiency_logs (
                    id VARCHAR(36) NOT NULL,
                    case_id VARCHAR(36) NOT NULL,
                    user_id VARCHAR(36) NOT NULL,
                    from_status VARCHAR(50) NOT NULL,
                    notes TEXT,
                    marked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    resolved_at DATETIME,
                    PRIMARY KEY (id),
                    INDEX ix_insufficiency_logs_case_id (case_id),
                    INDEX ix_insufficiency_logs_user_id (user_id),
                    INDEX ix_insufficiency_logs_marked_at (marked_at),
                    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """))
            connection.commit()
            print("Success.")
        except Exception as e:
            print(f"Table creation error: {e}")

if __name__ == "__main__":
    run_migrations()
