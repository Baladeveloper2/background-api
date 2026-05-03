
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

updates = {
    'CAPGEMINI': 'CAP',
    'IBM': 'IBM',
    'TATA': 'TATA',
    'MAHINDRA': 'MHD'
}

try:
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db_name,
        autocommit=True,
        ssl={'ssl': {}}
    )
    with conn.cursor() as cursor:
        for name, code in updates.items():
            print(f"Updating {name} with short_code {code}...")
            cursor.execute("UPDATE customers SET short_code = %s WHERE name = %s", (code, name))
            print(f"Affected rows: {cursor.rowcount}")
    conn.close()
    print("Updates complete.")
except Exception as e:
    print(f"Error: {e}")
