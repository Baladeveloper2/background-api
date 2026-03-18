from sqlalchemy.orm import Session
from app import models, database
import uuid

def seed():
    db = next(database.get_db())
    
    # 1. Seed Modules (Capabilities)
    modules_data = [
        # Customer / Administrative Interfaces
        {"name": "Customer Management", "code": "bms.customer", "category": "Administrative Interfaces", "description": "List and manage client profiles (Routes: /customers, /customers/add)"},
        {"name": "Partner Management", "code": "bms.partner", "category": "Administrative Interfaces", "description": "Manage external partner institutions (Route: /partners)"},
        {"name": "MIS Reports", "code": "mis.report", "category": "Insights & Reports", "description": "Access MIS & Daily system reports (Routes: /reports, /reports/daily)"},
        {"name": "Governance Settings", "code": "admin.panel", "category": "System Core", "description": "Manage RBAC roles, modules, and user accounts (Route: /admin)"},
        
        # BVS Core Lifecycle (Operations)
        {"name": "Customer Data Intake", "code": "bvs.customer_data", "category": "BVS Operations", "description": "Initial data intake processing (Route: /bvs/customer-data)"},
        {"name": "Customer File Management", "code": "bvs.customer_file_list", "category": "BVS Operations", "description": "Manage uploaded client requirement files (Route: /bvs/customer-file-list)"},
        {"name": "Batch Processing", "code": "bvs.batch", "category": "BVS Operations", "description": "Group candidates into operational batches (Routes: /bvs/batch, /bvs/batch/create)"},
        {"name": "Data Entry Execution", "code": "bvs.data_entry", "category": "BVS Operations", "description": "Input detailed candidate data (Routes: /bvs/data-entry, /bvs/data-entry/create-applicant)"},
        {"name": "Primary Verification", "code": "bvs.verification", "category": "BVS Operations", "description": "Conduct primary checks on cases (Routes: /verification, /verification/case/*)"},
        {"name": "Quality Control (QC)", "code": "bvs.qc", "category": "BVS Operations", "description": "Final review of verified cases (Route: /qc)"},
        
        # Recruitment & Candidates
        {"name": "Candidate Management", "code": "recruit.management", "category": "Recruitment", "description": "Manage candidate pipelines (Routes: /candidates, /candidates/add)"},
        
        # BMS Applicants List
        {"name": "Applicant Hub", "code": "bms.applicants", "category": "Applicant Tracking", "description": "Full access to applicant lists: QC Complete, Insuff, Interim, Stop Check (Routes: /applicants/*)"},
        
        # Finance
        {"name": "Budget Management", "code": "finance.budget", "category": "Finance", "description": "View and manage system budgets (Route: /budget)"},
        {"name": "Sales Orders", "code": "finance.sales_orders", "category": "Finance", "description": "Manage customer commercial orders (Routes: /sales-orders)"},
        {"name": "Invoices", "code": "finance.invoices", "category": "Finance", "description": "Generate and manage customer invoices (Routes: /invoices)"},
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
            "description": "Full system access including deletion privileges",
            "permissions": {m["code"]: {"read": True, "write": True, "delete": True} for m in modules_data}
        },
        {
            "name": "Verifier",
            "description": "Access to verification and data entry (No Deletion)",
            "permissions": {
                "bvs.verification": {"read": True, "write": True, "delete": False},
                "bvs.data_entry": {"read": True, "write": True, "delete": False},
                "bms.applicants": {"read": True, "write": False, "delete": False}
            }
        },
        {
            "name": "QC Specialist",
            "description": "Access to QC and verification (No Deletion)",
            "permissions": {
                "bvs.qc": {"read": True, "write": True, "delete": False},
                "bvs.verification": {"read": True, "write": False, "delete": False}
            }
        }
    ]

    for r in roles_data:
        existing = db.query(models.Role).filter(models.Role.name == r["name"]).first()
        if existing:
            # Update existing roles with new structure
            existing.permissions = r["permissions"]
            existing.description = r["description"]
        else:
            db.add(models.Role(**r))
    db.commit()

    # 3. Assign first admin user to Super Admin role
    admin_role = db.query(models.Role).filter(models.Role.name == "Super Admin").first()
    if admin_role:
        user = db.query(models.User).filter(models.User.email == "admin@bgvms.com").first()
        if user:
            user.role_id = admin_role.id
            user.role = models.UserRole.SUPER_ADMIN
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
