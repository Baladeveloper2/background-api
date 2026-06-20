import pymysql
import json

conn = pymysql.connect(
    host='dataentry-dataentry.j.aivencloud.com',
    port=14419,
    user='avnadmin',
    password='AVNS_ce7C0cV_01nkFa1rYPq',
    database='defaultdb',
    cursorclass=pymysql.cursors.DictCursor
)

try:
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM candidates WHERE name LIKE '%BALAMURUGAN TEST%'")
        candidate = cursor.fetchone()
        if candidate:
            print("Candidate ID:", candidate['id'])
            cursor.execute("SELECT id FROM cases WHERE candidate_id = %s", (candidate['id'],))
            cases = cursor.fetchall()
            for case in cases:
                cursor.execute("SELECT id, check_type, data FROM verification_checks WHERE case_id = %s", (case['id'],))
                checks = cursor.fetchall()
                for check in checks:
                    if 'database' in check['check_type'].lower():
                        print("---")
                        print("Check ID:", check['id'])
                        print("Check Type:", check['check_type'])
                        print("Data:", check['data'])
finally:
    conn.close()
