import os
import sys
import json
import datetime
from sqlalchemy import text
from app.database import engine, SessionLocal

def backup_database():
    print("Starting database backup...")
    backup_dir = os.path.join(os.path.dirname(__file__), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"db_backup_{timestamp}.json")

    # Reflect database schema
    from sqlalchemy import MetaData
    meta = MetaData()
    meta.reflect(bind=engine)
    
    backup_data = {}
    with engine.connect() as conn:
        for table in meta.sorted_tables:
            print(f"Backing up table: {table.name}")
            try:
                result = conn.execute(table.select())
                rows = [dict(row._mapping) for row in result]
                # Convert datetime, date etc to string for JSON serialization
                for row in rows:
                    for k, v in row.items():
                        if isinstance(v, (datetime.datetime, datetime.date)):
                            row[k] = v.isoformat()
                        elif isinstance(v, bytes):
                            row[k] = v.hex() # Convert bytes to hex
                backup_data[table.name] = rows
            except Exception as e:
                print(f"Error backing up table {table.name}: {e}")

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2, default=str)
    print(f"Backup completed: {backup_file}")

def cleanup_database():
    print("Starting database cleanup...")
    session = SessionLocal()
    
    try:
        # Disable foreign key checks
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))

        # Tables to completely empty (Operational / Test Data)
        tables_to_empty = [
            "candidates",
            "customers",
            "ocr_result_cache",
            "partners",
            "Enrollment",
            "batches",
            "dashboard_summaries",
            "invoices",
            "ocr_extractions",
            "ocr_processing_jobs",
            "audit_logs",
            "cases",
            "client_documents",
            "document_metadata",
            "ocr_analytics",
            "ocr_classifications",
            "ocr_processing_logs",
            "ocr_review_queue",
            "address_change_requests",
            "case_comments",
            "notifications",
            "revoke_logs",
            "verification_checks",
            "address_verifications",
            "insufficiencies",
            "insufficiency_logs",
            "qc_field_issues",
            "verification_documents",
            "verification_logs",
            "address_verification_photos",
            "Course"
        ]
        
        for table in tables_to_empty:
            print(f"Emptying table: {table}")
            session.execute(text(f"DELETE FROM `{table}`"))
            
            # Reset auto-increment counters if applicable
            try:
                session.execute(text(f"ALTER TABLE `{table}` AUTO_INCREMENT = 1"))
            except Exception:
                pass

        # For users table, keep only SUPER_ADMIN role
        print("Cleaning users table (preserving SUPER_ADMIN)...")
        session.execute(text("DELETE FROM `users` WHERE `role` != 'SUPER_ADMIN'"))
        try:
            session.execute(text("ALTER TABLE `users` AUTO_INCREMENT = 1"))
        except Exception:
            pass

        # For User table (capital U), keep only ADMIN or SUPER_ADMIN
        print("Cleaning User table (preserving ADMIN/SUPER_ADMIN)...")
        session.execute(text("DELETE FROM `User` WHERE `role` NOT IN ('SUPER_ADMIN', 'ADMIN')"))
        try:
            session.execute(text("ALTER TABLE `User` AUTO_INCREMENT = 1"))
        except Exception:
            pass

        # Re-enable foreign key checks
        session.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        session.commit()
        print("Cleanup transaction committed successfully.")
        
    except Exception as e:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        session.rollback()
        print(f"Error during cleanup. Transaction rolled back. Error: {e}")
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    try:
        backup_database()
        cleanup_database()
        print("Database cleanup completed successfully.")
    except Exception as e:
        print(f"Failed to execute process: {e}")
