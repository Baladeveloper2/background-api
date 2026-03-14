from sqlalchemy.orm import Session
from app import models, database
import uuid

def seed():
    db = next(database.get_db())
    
    # 1. Seed Modules
    modules_data = [
        {"name": "Applicants", "code": "bms.applicants", "category": "BMS"},
        {"name": "Customer", "code": "bms.customer", "category": "BMS"},
        {"name": "Batch", "code": "bms.batch", "category": "BMS"},
        {"name": "Data Entry", "code": "bvs.data_entry", "category": "BVS"},
        {"name": "Verification", "code": "bvs.verification", "category": "BVS"},
        {"name": "QC", "code": "bvs.qc", "category": "BVS"},
        {"name": "MIS Master", "code": "customer.mis_master", "category": "Customer"},
        {"name": "Candidate Login", "code": "customer.candidate_login", "category": "Customer"},
    ]
    
    print("Seeding modules...")
    for m in modules_data:
        existing = db.query(models.Module).filter(models.Module.code == m["code"]).first()
        if not existing:
            db.add(models.Module(**m))
    db.commit()

    # 2. Seed Roles
    print("Seeding roles...")
    roles_data = [
        {
            "name": "Super Admin",
            "description": "Full system access",
            "permissions": {m["code"]: True for m in modules_data}
        },
        {
            "name": "Verifier",
            "description": "Access to verification and data entry",
            "permissions": {"bvs.verification": True, "bvs.data_entry": True}
        },
        {
            "name": "QC Specialist",
            "description": "Access to QC and verification",
            "permissions": {"bvs.qc": True, "bvs.verification": True}
        }
    ]

    for r in roles_data:
        existing = db.query(models.Role).filter(models.Role.name == r["name"]).first()
        if not existing:
            db.add(models.Role(**r))
    db.commit()

    # 3. Assign first admin user to Super Admin role
    admin_role = db.query(models.Role).filter(models.Role.name == "Super Admin").first()
    if admin_role:
        user = db.query(models.User).filter(models.User.email == "admin@bgvms.com").first()
        if user:
            user.role_id = admin_role.id
            db.commit()
            print(f"Assigned {user.email} to {admin_role.name} role.")

    print("Seeding completed successfully.")

if __name__ == "__main__":
    try:
        seed()
    except Exception as e:
        print(f"Error during seeding: {e}")
        import traceback
        traceback.print_exc()
