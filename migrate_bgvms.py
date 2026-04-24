
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
raw_url = os.getenv("DATABASE_URL").replace("mysql+aiomysql", "mysql+pymysql")
# Replace defaultdb with bgvms
if "/defaultdb" in raw_url:
    bgvms_url = raw_url.replace("/defaultdb", "/bgvms")
else:
    bgvms_url = raw_url

print(f"Applying to: {bgvms_url}")
engine = create_engine(bgvms_url)

try:
    with engine.connect() as conn:
        print("Checking 'cases' table in bgvms...")
        try:
            conn.execute(text("ALTER TABLE cases ADD COLUMN insufficiency_count INT DEFAULT 0;"))
            conn.commit()
            print("Successfully added to bgvms.")
        except Exception as e:
            print(f"Note for bgvms cases: {e}")

        print("Creating 'insufficiency_logs' table in bgvms...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS insufficiency_logs (
                id VARCHAR(36) NOT NULL,
                case_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(36) NOT NULL,
                from_status VARCHAR(50) NOT NULL,
                notes TEXT,
                marked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved_at DATETIME,
                PRIMARY KEY (id),
                INDEX ix_marked_at (marked_at),
                FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """))
        conn.commit()
        print("Table confirmed in bgvms.")
except Exception as e:
    print(f"Error connecting to bgvms: {e}")
