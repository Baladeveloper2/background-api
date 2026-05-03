
import pymysql
import os
from dotenv import load_dotenv

# Load env from backend/.env
load_dotenv('backend/.env')

user = os.getenv("DB_USER", "avnadmin")
password = os.getenv("DB_PASSWORD", "AVNS_ce7C0cV_01nkFa1rYPq")
host = os.getenv("DB_HOST", "dataentry-dataentry.j.aivencloud.com")
port = int(os.getenv("DB_PORT", 14419))
db_name = "defaultdb"

print(f"Connecting to {host}:{port}/{db_name} as {user}...")

try:
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db_name,
        autocommit=True,
        ssl={'ssl': {}} # Aiven usually requires SSL
    )
    with conn.cursor() as cursor:
        print("Migrating 'customers' table...")
        try:
            cursor.execute("SHOW COLUMNS FROM customers LIKE 'short_code'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE customers ADD COLUMN short_code VARCHAR(50) AFTER name")
                cursor.execute("CREATE UNIQUE INDEX ix_customers_short_code ON customers (short_code)")
                print("Successfully added 'short_code' to 'customers'.")
            else:
                print("'short_code' already exists in 'customers'.")
        except Exception as e:
            print(f"Error migrating 'customers': {e}")

        print("Migrating 'batches' table...")
        try:
            cursor.execute("SHOW COLUMNS FROM batches LIKE 'cl_ref_no'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE batches ADD COLUMN cl_ref_no VARCHAR(50) AFTER batch_no")
                cursor.execute("CREATE INDEX ix_batches_cl_ref_no ON batches (cl_ref_no)")
                print("Successfully added 'cl_ref_no' to 'batches'.")
            else:
                print("'cl_ref_no' already exists in 'batches'.")
        except Exception as e:
            print(f"Error migrating 'batches': {e}")
    conn.close()
    print("Migration complete.")
except Exception as e:
    print(f"Connection error: {e}")
