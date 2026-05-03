
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

case_id = "1bdc6405-82df-43bc-a951-5ce6258f0c4d"

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
        cursor.execute("SELECT cand.name as candidate_name, c.case_ref_no FROM cases c JOIN candidates cand ON c.candidate_id = cand.id WHERE c.id = %s", (case_id,))
        row = cursor.fetchone()
        print(json.dumps(row, indent=4))
    conn.close()
except Exception as e:
    print(f"Error: {e}")
