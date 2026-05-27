import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

load_dotenv()
db_url = os.getenv("DATABASE_URL")
if db_url.startswith("mysql:"):
    db_url = db_url.replace("mysql:", "mysql+pymysql:", 1)
elif "mysql+aiomysql" in db_url:
    db_url = db_url.replace("mysql+aiomysql", "mysql+pymysql")

engine = create_engine(db_url)

def get_stats(client_name=None, start_date=None, end_date=None):
    with engine.connect() as conn:
        # Determine client id
        cust_id = None
        if client_name:
            cust_res = conn.execute(text("SELECT id FROM customers WHERE name = :n"), {"n": client_name}).first()
            if cust_res:
                cust_id = cust_res[0]

        # Base case query
        where_clauses = []
        params = {}
        if cust_id:
            where_clauses.append("customer_id = :cid")
            params["cid"] = cust_id
        if start_date:
            where_clauses.append("received_date >= :s")
            params["s"] = start_date
        if end_date:
            where_clauses.append("received_date <= :e")
            params["e"] = end_date

        where_sql = " AND ".join(where_clauses)
        if where_sql:
            where_sql = "WHERE " + where_sql

        # 1. Total cases and statuses
        status_rows = conn.execute(text(f"SELECT status, count(*) FROM cases {where_sql} GROUP BY status"), params).all()
        status_counts = {row[0]: row[1] for row in status_rows}

        # 2. WIP
        wip_statuses = ['IN_PROGRESS', 'VERIFICATION', 'QC', 'QC_PENDING', 'QA_PENDING']
        wip_count = sum(v for k, v in status_counts.items() if k in wip_statuses)

        # 3. Insufficient cases
        if cust_id:
            insuff_sql = "SELECT count(distinct case_id) FROM insufficiencies i JOIN cases c ON i.case_id = c.id WHERE i.is_resolved = 0 AND c.customer_id = :cid"
        else:
            insuff_sql = "SELECT count(distinct case_id) FROM insufficiencies WHERE is_resolved = 0"
        
        insuff_params = {"cid": cust_id} if cust_id else {}
        if start_date:
            insuff_sql += " AND c.received_date >= :s"
            insuff_params["s"] = start_date
        if end_date:
            insuff_sql += " AND c.received_date <= :e"
            insuff_params["e"] = end_date

        actual_insuff_count = conn.execute(text(insuff_sql), insuff_params).scalar() or 0

        # 4. TAT
        tat_where = []
        tat_params = {}
        if cust_id:
            tat_where.append("customer_id = :cid")
            tat_params["cid"] = cust_id
        if start_date:
            tat_where.append("received_date >= :s")
            tat_params["s"] = start_date
        if end_date:
            tat_where.append("received_date <= :e")
            tat_params["e"] = end_date

        tat_where_sql = " AND ".join(tat_where)
        if tat_where_sql:
            tat_where_sql = "AND " + tat_where_sql

        in_tat_count = conn.execute(text(f"SELECT count(*) FROM cases WHERE is_in_tat = 1 {tat_where_sql}"), tat_params).scalar() or 0
        out_tat_count = conn.execute(text(f"SELECT count(*) FROM cases WHERE is_in_tat = 0 {tat_where_sql}"), tat_params).scalar() or 0

        now_time = datetime.utcnow()
        risk_threshold = now_time - timedelta(days=7)
        at_risk_params = {"rt": risk_threshold}
        at_risk_params.update(tat_params)
        at_risk_count = conn.execute(text(f"SELECT count(*) FROM cases WHERE status NOT IN ('FINALIZED', 'COMPLETED', 'POSITIVE', 'NEGATIVE', 'DISCREPANCY', 'UNABLE TO VERIFY', 'HOLD', 'INSUFFICIENT', 'QC_VERIFIED', 'CLOSED') AND received_date < :rt {tat_where_sql}"), at_risk_params).scalar() or 0

        # 5. Check result counts
        check_where = []
        check_params = {}
        if cust_id:
            check_where.append("c.customer_id = :cid")
            check_params["cid"] = cust_id
        if start_date:
            check_where.append("c.received_date >= :s")
            check_params["s"] = start_date
        if end_date:
            check_where.append("c.received_date <= :e")
            check_params["e"] = end_date

        check_where_sql = " AND ".join(check_where)
        if check_where_sql:
            check_where_sql = "WHERE " + check_where_sql

        check_rows = conn.execute(text(f"SELECT vc.case_id, vc.status FROM verification_checks vc JOIN cases c ON vc.case_id = c.id {check_where_sql}"), check_params).all()
        
        from collections import defaultdict
        cases_checks_map = defaultdict(list)
        for r_case_id, r_status in check_rows:
            cases_checks_map[r_case_id].append(str(r_status).upper())

        positive_count = 0
        negative_count = 0
        amber_count = 0
        for cid, statuses in cases_checks_map.items():
            if "STOP" in statuses:
                pass
            elif "RED" in statuses or "NEGATIVE" in statuses:
                negative_count += 1
            elif "AMBER" in statuses or "DISCREPANCY" in statuses:
                amber_count += 1
            elif any(s in ["GREEN", "POSITIVE", "QC_VERIFIED", "CLEAR", "VERIFIED"] for s in statuses):
                positive_count += 1

        if not cases_checks_map:
            positive_count = sum(v for k, v in status_counts.items() if k in ['FINALIZED', 'COMPLETED', 'QC_VERIFIED', 'POSITIVE'])
            negative_count = sum(v for k, v in status_counts.items() if k in ['NEGATIVE', 'DISCREPANCY', 'UNABLE TO VERIFY'])
            amber_count = sum(v for k, v in status_counts.items() if k == 'HOLD')

        return {
            "positive": positive_count,
            "negative": negative_count,
            "wip": wip_count,
            "insufficient": actual_insuff_count,
            "in_tat": in_tat_count,
            "out_tat": out_tat_count,
            "at_risk": at_risk_count,
            "status_counts": status_counts
        }

print("=== STATS WITH NO FILTERS ===")
print(get_stats())

print("\n=== STATS WITH FILTERS ===")
print(get_stats(
    client_name="Apex Covantage India Private Limited",
    start_date=datetime(2026, 5, 1),
    end_date=datetime(2026, 5, 15, 23, 59, 59)
))
