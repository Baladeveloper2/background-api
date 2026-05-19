import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

def run():
    with engine.connect() as conn:
        print("Starting legacy status migration in database...")
        
        # 1. Update cases
        res = conn.execute(text("""
            UPDATE cases 
            SET status = CASE 
                WHEN status IN ('COMPLETED', 'QC_PENDING', 'QC_REVIEW', 'QC', 'QA_PENDING', 'QC_VERIFIED', 'CLOSED', 'CANCELLED') THEN 'FINALIZED'
                WHEN status IN ('DOCUMENTS_SUBMITTED', 'IN_VERIFICATION', 'REOPENED', 'VERIFICATION') THEN 'IN_PROGRESS'
                WHEN status = 'INSUFFICIENT' THEN 'INSUFFICIENCY'
                WHEN status IN ('LINK_SHARED', 'PENDING', 'NEW') THEN 'ASSIGNED'
                ELSE status
            END
            WHERE status IN (
                'COMPLETED', 'QC_PENDING', 'QC_REVIEW', 'QC', 'QA_PENDING', 'QC_VERIFIED', 'CLOSED', 'CANCELLED',
                'DOCUMENTS_SUBMITTED', 'IN_VERIFICATION', 'REOPENED', 'VERIFICATION',
                'INSUFFICIENT',
                'LINK_SHARED', 'PENDING', 'NEW'
            )
        """))
        print(f"Updated {res.rowcount} cases to canonical statuses.")
        
        # 2. Update checks: GREEN -> POSITIVE, RED -> NEGATIVE, AMBER -> DISCREPANCY
        res2 = conn.execute(text("""
            UPDATE verification_checks
            SET status = CASE 
                WHEN status = 'GREEN' THEN 'POSITIVE'
                WHEN status = 'RED' THEN 'NEGATIVE'
                WHEN status = 'AMBER' THEN 'DISCREPANCY'
                ELSE status
            END
            WHERE status IN ('GREEN', 'RED', 'AMBER')
        """))
        print(f"Updated {res2.rowcount} checks from GREEN/RED/AMBER to POSITIVE/NEGATIVE/DISCREPANCY.")
        
        # 3. Update checks: QC_PENDING/QC_VERIFIED -> final_result if not null, else POSITIVE
        res3 = conn.execute(text("""
            UPDATE verification_checks
            SET status = CASE
                WHEN final_result IS NOT NULL AND final_result != '' THEN final_result
                ELSE 'POSITIVE'
            END
            WHERE status IN ('QC_PENDING', 'QC_VERIFIED')
        """))
        print(f"Updated {res3.rowcount} checks from QC_PENDING/QC_VERIFIED to final results.")
        
        conn.commit()
        print("Legacy status migration completed successfully.")

if __name__ == "__main__":
    run()
