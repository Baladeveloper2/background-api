
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
        print("Searching in candidates...")
        cursor.execute("SELECT * FROM candidates WHERE name LIKE %s OR db_candidate_name LIKE %s", ("%KABII%", "%KABII%"))
        print(json.dumps(cursor.fetchall(), indent=4))
        
        print("\nSearching in cases...")
        # Check for any column that might contain the name
        cursor.execute("DESCRIBE cases")
        columns = [c['Field'] for c in cursor.fetchall()]
        where_clause = " OR ".join([f"`{c}` LIKE %s" for c in columns if "name" in c or "ref" in c])
        if where_clause:
            cursor.execute(f"SELECT * FROM cases WHERE {where_clause}", ["%KABII%"] * where_clause.count("%s"))
            print(json.dumps(cursor.fetchall(), indent=4))
            
    conn.close()
except Exception as e:
    print(f"Error: {e}")
