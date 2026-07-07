import sqlite3
conn=sqlite3.connect('d:/project/backend/db.sqlite3')
cur=conn.cursor()
cur.execute("SELECT candidate_details FROM cases WHERE id='73f97e01-c98e-4f34-9519-22bc2a67194a'")
row = cur.fetchone()
if row:
    print(row[0])
else:
    print("Not found")
