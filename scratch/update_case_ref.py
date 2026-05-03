
import pymysql
import os
from dotenv import load_dotenv

load_dotenv('backend/.env')

user = os.getenv("DB_USER", "avnadmin")
password = os.getenv("DB_PASSWORD", "AVNS_ce7C0cV_01nkFa1rYPq")
host = os.getenv("DB_HOST", "dataentry-dataentry.j.aivencloud.com")
port = int(os.getenv("DB_PORT", 14419))
db_name = "defaultdb"

case_id = "1bdc6405-82df-43bc-a951-5ee6258f0e4d"
new_ref = "CL-CAP-001"

try:
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db_name,
        ssl={'ssl': {}}
    )
    with conn.cursor() as cursor:
        print(f"Updating case {case_id} to {new_ref}...")
        cursor.execute("UPDATE cases SET case_ref_no = %s WHERE id = %s", (new_ref, case_id))
        print(f"Affected rows: {cursor.rowcount}")
        conn.commit()
    conn.close()
    print("Update complete.")
except Exception as e:
    print(f"Error: {e}")
