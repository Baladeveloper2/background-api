import pymysql, os, json
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()
u = urlparse(os.getenv('DATABASE_URL'))
c = pymysql.connect(
    host=u.hostname, user=u.username, password=u.password, 
    database=u.path.lstrip('/'), port=u.port or 3306
)
cur = c.cursor()
query = """
SELECT 
    TABLE_NAME, 
    CONSTRAINT_NAME, 
    COLUMN_NAME, 
    REFERENCED_TABLE_NAME, 
    REFERENCED_COLUMN_NAME 
FROM 
    INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
WHERE 
    TABLE_SCHEMA = 'defaultdb' 
    AND REFERENCED_TABLE_NAME IS NOT NULL
"""
cur.execute(query)
for row in cur.fetchall():
    print(row)
c.close()
