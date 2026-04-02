import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

# Database credentials
db_user = os.getenv("DB_USER", "avnadmin")
db_password = os.getenv("DB_PASSWORD", "AVNS_ce7C0cV_01nkFa1rYPq")
db_host = os.getenv("DB_HOST", "dataentry-dataentry.j.aivencloud.com")
db_port = int(os.getenv("DB_PORT", 14419))
db_name = "defaultdb"

def revert_cloudinary_links():
    try:
        conn = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            port=db_port
        )
        cursor = conn.cursor()

        # Tables and columns to update
        updates = [
            ("customers", "customer_agreement"),
            ("batches", "file_url"),
            ("candidates", "customer_agreement")
        ]

        total_updated = 0
        for table, col in updates:
            # Check if table exists
            cursor.execute(f"SHOW TABLES LIKE '{table}'")
            if not cursor.fetchone():
                print(f"Table {table} does not exist, skipping.")
                continue

            # Check if column exists
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE '{col}'")
            if not cursor.fetchone():
                print(f"Column {col} in {table} does not exist, skipping.")
                continue

            # Update 'dfrtq0ch8' back to 'dfrfq0ch8'
            sql = f"UPDATE {table} SET {col} = REPLACE({col}, 'dfrtq0ch8', 'dfrfq0ch8') WHERE {col} LIKE '%dfrtq0ch8%'"
            cursor.execute(sql)
            rows = cursor.rowcount
            total_updated += rows
            print(f"Updated {rows} records in {table}.{col}")

        conn.commit()
        print(f"Revert complete. Total records updated: {total_updated}")
        conn.close()
    except Exception as e:
        print(f"Revert failed: {str(e)}")

if __name__ == "__main__":
    revert_cloudinary_links()
