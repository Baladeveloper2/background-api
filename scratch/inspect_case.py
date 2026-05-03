
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

name_search = "KABILAN D"

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
        cursor.execute("SELECT c.id, c.case_ref_no, cand.name as candidate_name, cust.name as customer_name, cust.short_code as customer_short_code FROM cases c JOIN candidates cand ON c.candidate_id = cand.id JOIN customers cust ON c.customer_id = cust.id WHERE cand.name LIKE %s", (f"%{name_search}%",))
        rows = cursor.fetchall()
        
        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                return super(DateTimeEncoder, self).default(obj)
        
        print(json.dumps(rows, indent=4, cls=DateTimeEncoder))
    conn.close()
except Exception as e:
    print(f"Error: {e}")
