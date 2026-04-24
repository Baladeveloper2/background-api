
import os
import traceback
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("DATABASE_URL").replace("mysql+aiomysql", "mysql+pymysql")
engine = create_engine(url)

try:
    with engine.connect() as conn:
        print("Dropping table if exists (cleanup)...")
        conn.execute(text("DROP TABLE IF EXISTS insufficiency_logs"))
        conn.commit()

        print("Executing CREATE TABLE (minimal)...")
        # Removing explicit collation to avoid compatibility issues
        conn.execute(text("""
            CREATE TABLE insufficiency_logs (
                id VARCHAR(36) NOT NULL,
                case_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(36) NOT NULL,
                from_status VARCHAR(50) NOT NULL,
                notes TEXT,
                marked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved_at DATETIME,
                PRIMARY KEY (id),
                INDEX ix_marked_at (marked_at),
                CONSTRAINT fk_insuff_case FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
                CONSTRAINT fk_insuff_user FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """))
        conn.commit()
        print("Table created successfully.")
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
