
import pymysql
import os
from dotenv import load_dotenv
import json

load_dotenv('backend/.env')

user = os.getenv("DB_USER", "avnadmin")
password = os.getenv("DB_PASSWORD", "AVNS_ce7C0cV_01nkFa1rYPq")
host = os.getenv("DB_HOST", "dataentry-dataentry.j.aivencloud.com")
port = int(os.getenv("DB_PORT", 14419))
db_name = "defaultdb"

batch_id = "2e636dc6-19f6-41b1-a388-83c69b3b0886"

try:
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db_name,
        ssl={'ssl': {}}
    )
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT id, case_ref_no FROM cases WHERE batch_id = %s", (batch_id,))
        print(json.dumps(cursor.fetchall(), indent=4))
    conn.close()
except Exception as e:
    print(f"Error: {e}")
