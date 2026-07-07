import sys
import json
from sqlalchemy import create_engine
from sqlalchemy.sql import text

engine = create_engine('mysql+pymysql://avnadmin:AVNS_ce7C0cV_01nkFa1rYPq@dataentry-dataentry.j.aivencloud.com:14419/defaultdb')
with engine.connect() as conn:
    res = conn.execute(text("SELECT id, candidate_id FROM cases WHERE id='73f97e01-c98e-4f34-9519-22bc2a67194a'"))
    case = res.fetchone()
    if not case:
        print("Case not found")
        sys.exit()
    print("Found case", case)
    
    cand_res = conn.execute(text("SELECT address_details FROM candidates WHERE id=:cid"), {"cid": case.candidate_id})
    cand = cand_res.fetchone()
    if cand:
        print("Cand address_details:")
        print(cand.address_details)
    else:
        print("Cand not found")
