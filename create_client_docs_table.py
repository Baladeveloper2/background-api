
import os
import traceback
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("DATABASE_URL").replace("mysql+aiomysql", "mysql+pymysql")
engine = create_engine(url)

try:
    with engine.connect() as conn:
        print("Checking if client_documents table exists...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS client_documents (
                id VARCHAR(36) NOT NULL,
                customer_id VARCHAR(36) NOT NULL,
                name VARCHAR(255) NOT NULL,
                is_folder TINYINT(1) DEFAULT 0,
                parent_id VARCHAR(36),
                file_path VARCHAR(500),
                file_type VARCHAR(100),
                uploaded_by VARCHAR(36) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                FOREIGN KEY (customer_id) REFERENCES customers(id),
                FOREIGN KEY (parent_id) REFERENCES client_documents(id),
                FOREIGN KEY (uploaded_by) REFERENCES users(id)
            )
        """))
        conn.commit()
        print("client_documents table handled successfully.")
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
