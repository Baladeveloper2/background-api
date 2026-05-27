import pymysql, os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

raw = os.getenv('DATABASE_URL', 'mysql://root:password@localhost/bgv_db')
raw = raw.replace('mysql://', '')
parts = raw.split('@')
userpass = parts[0].split(':')
hostdb = parts[1].split('/')
user = userpass[0]
password = ':'.join(userpass[1:])  # handle passwords with colons
host = hostdb[0]
db = hostdb[1]

conn = pymysql.connect(host=host, user=user, password=password, database=db)
cur = conn.cursor()

print('=== DISTINCT case statuses ===')
cur.execute('SELECT status, COUNT(*) as cnt FROM cases GROUP BY status ORDER BY cnt DESC LIMIT 20')
for row in cur.fetchall():
    print(row)

print('\n=== is_billable values ===')
try:
    cur.execute('SELECT is_billable, COUNT(*) as cnt FROM cases GROUP BY is_billable')
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print('ERROR:', e)

print('\n=== is_invoiced values ===')
try:
    cur.execute('SELECT is_invoiced, COUNT(*) as cnt FROM cases GROUP BY is_invoiced')
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print('ERROR:', e)

print('\n=== Sample completed cases (first 5) ===')
final_statuses = ('FINALIZED','POSITIVE','NEGATIVE','QC_VERIFIED','DISCREPANCY','COMPLETED')
placeholders = ','.join(['%s'] * len(final_statuses))
cur.execute(
    f'SELECT id, status, is_billable, is_invoiced, customer_id FROM cases WHERE status IN ({placeholders}) LIMIT 5',
    final_statuses
)
for row in cur.fetchall():
    print(row)

print('\n=== Total billable (final status, not invoiced, is_billable=1) ===')
cur.execute(
    f'SELECT COUNT(*) FROM cases WHERE status IN ({placeholders}) AND is_invoiced=0 AND is_billable=1',
    final_statuses
)
print(cur.fetchone())

print('\n=== Total with final status, not invoiced (ignore is_billable) ===')
cur.execute(
    f'SELECT COUNT(*) FROM cases WHERE status IN ({placeholders}) AND is_invoiced=0',
    final_statuses
)
print(cur.fetchone())

conn.close()
