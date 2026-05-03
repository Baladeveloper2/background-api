
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

search_str = "KABII.AN D"

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
        print(f"Searching for '{search_str}' in all tables...")
        cursor.execute("SHOW TABLES")
        tables = [t['Tables_in_defaultdb'] for t in cursor.fetchall()]
        
        for table in tables:
            cursor.execute(f"DESCRIBE `{table}`")
            columns = [c['Field'] for c in cursor.fetchall() if "char" in c['Type'] or "text" in c['Type']]
            for col in columns:
                cursor.execute(f"SELECT * FROM `{table}` WHERE `{col}` = %s", (search_str,))
                res = cursor.fetchall()
                if res:
                    print(f"Found in table '{table}', column '{col}':")
                    print(json.dumps(res, indent=4, default=str))
                    
    conn.close()
    print("Search complete.")
except Exception as e:
    print(f"Error: {e}")
