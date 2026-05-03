
import pymysql
import os
from dotenv import load_dotenv

load_dotenv('backend/.env')

user = os.getenv("DB_USER", "avnadmin")
password = os.getenv("DB_PASSWORD", "AVNS_ce7C0cV_01nkFa1rYPq")
host = os.getenv("DB_HOST", "dataentry-dataentry.j.aivencloud.com")
port = int(os.getenv("DB_PORT", 14419))
db_name = "defaultdb"

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
        cursor.execute("SELECT id, case_ref_no FROM cases WHERE case_ref_no NOT LIKE 'CL-%'")
        rows = cursor.fetchall()
        print(f"Found {len(rows)} cases with old format.")
        for r in rows[:10]:
            print(f"ID: {r[0]}, Ref: {r[1]}")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
