
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

case_id = "1bdc6405-82df-43bc-a951-5ee6258f0e4d"

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
        cursor.execute("SELECT b.* FROM cases c JOIN batches b ON c.batch_id = b.id WHERE c.id = %s", (case_id,))
        row = cursor.fetchone()
        
        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                return super(DateTimeEncoder, self).default(obj)
        
        print(json.dumps(row, indent=4, cls=DateTimeEncoder))
    conn.close()
except Exception as e:
    print(f"Error: {e}")
