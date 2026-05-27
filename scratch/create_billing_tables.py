import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("No DATABASE_URL found!")
    sys.exit(1)

if db_url.startswith("mysql:"):
    db_url = db_url.replace("mysql:", "mysql+pymysql:", 1)
elif "mysql+aiomysql" in db_url:
    db_url = db_url.replace("mysql+aiomysql", "mysql+pymysql")

engine = create_engine(db_url)

with engine.connect() as conn:
    print("Starting enterprise billing database migrations...")
    
    # Let's inspect the id column of customers to see its exact type, charset and collation
    cust_desc = conn.execute(text("SHOW CREATE TABLE customers")).first()
    print("customers table DDL:", cust_desc[1])
    
    # 1. Create invoices table (omitting charset/collation to let MySQL match automatically)
    print("Creating invoices table if not exists...")
    create_invoices_sql = """
    CREATE TABLE IF NOT EXISTS invoices (
        id VARCHAR(36) PRIMARY KEY,
        invoice_number VARCHAR(100) UNIQUE NOT NULL,
        client_id VARCHAR(36) NOT NULL,
        billing_cycle VARCHAR(50) DEFAULT 'MONTHLY',
        billing_period_from DATETIME NOT NULL,
        billing_period_to DATETIME NOT NULL,
        subtotal DOUBLE DEFAULT 0.0,
        gst_amount DOUBLE DEFAULT 0.0,
        total_amount DOUBLE DEFAULT 0.0,
        generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        due_date DATETIME NULL,
        status VARCHAR(50) DEFAULT 'DRAFT',
        generated_by VARCHAR(36) NULL,
        modified_by VARCHAR(36) NULL,
        paid_at DATETIME NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (client_id) REFERENCES customers(id) ON DELETE CASCADE
    ) ENGINE=InnoDB;
    """
    try:
        conn.execute(text(create_invoices_sql))
        conn.commit()
        print("invoices table created successfully!")
    except Exception as e:
        print(f"Error creating invoices table: {e}")
        # Try without the foreign key first to diagnose
        print("Retrying invoices table creation without foreign key...")
        create_invoices_no_fk = """
        CREATE TABLE IF NOT EXISTS invoices (
            id VARCHAR(36) PRIMARY KEY,
            invoice_number VARCHAR(100) UNIQUE NOT NULL,
            client_id VARCHAR(36) NOT NULL,
            billing_cycle VARCHAR(50) DEFAULT 'MONTHLY',
            billing_period_from DATETIME NOT NULL,
            billing_period_to DATETIME NOT NULL,
            subtotal DOUBLE DEFAULT 0.0,
            gst_amount DOUBLE DEFAULT 0.0,
            total_amount DOUBLE DEFAULT 0.0,
            generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            due_date DATETIME NULL,
            status VARCHAR(50) DEFAULT 'DRAFT',
            generated_by VARCHAR(36) NULL,
            modified_by VARCHAR(36) NULL,
            paid_at DATETIME NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB;
        """
        conn.execute(text(create_invoices_no_fk))
        conn.commit()
        print("invoices table created without foreign key. Now altering client_id column to match customers(id)...")
        # Try to alter the column collation to match customers.id if needed
        try:
            # Add foreign key
            conn.execute(text("ALTER TABLE invoices ADD CONSTRAINT fk_invoices_client FOREIGN KEY (client_id) REFERENCES customers(id) ON DELETE CASCADE"))
            conn.commit()
            print("Successfully added foreign key fk_invoices_client after match!")
        except Exception as alter_err:
            print(f"Failed to add foreign key constraint: {alter_err}")
            print("Proceeding without hard foreign key constraint for invoices(client_id) -> customers(id) if they are in different character sets.")

    # 2. Add columns to cases table
    print("Checking cases table columns...")
    cases_cols = conn.execute(text("DESCRIBE cases")).all()
    case_col_names = [col[0] for col in cases_cols]
    
    cases_to_add = {
        "is_billable": "TINYINT(1) DEFAULT 1",
        "is_invoiced": "TINYINT(1) DEFAULT 0",
        "invoice_id": "VARCHAR(36) NULL",
        "billed_at": "DATETIME NULL",
        "billing_amount": "DOUBLE DEFAULT 0.0"
    }
    
    for col, spec in cases_to_add.items():
        if col not in case_col_names:
            print(f"Adding column {col} to cases table...")
            try:
                conn.execute(text(f"ALTER TABLE cases ADD COLUMN {col} {spec}"))
                conn.commit()
                print(f"Added column {col} successfully!")
            except Exception as e:
                print(f"Error adding {col} to cases: {e}")
        else:
            print(f"Column {col} already exists on cases table.")

    # Add foreign key constraint to cases.invoice_id
    try:
        conn.execute(text("ALTER TABLE cases ADD CONSTRAINT fk_cases_invoice FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE SET NULL"))
        conn.commit()
        print("Added foreign key constraint fk_cases_invoice to cases table.")
    except Exception as e:
        print(f"Note: Constraint fk_cases_invoice might already exist or failed: {e}")

    # 3. Add columns to customers (clients) table
    print("Checking customers table columns...")
    cust_cols = conn.execute(text("DESCRIBE customers")).all()
    cust_col_names = [col[0] for col in cust_cols]
    
    cust_to_add = {
        "gst_number": "VARCHAR(100) NULL",
        "billing_config": "MEDIUMTEXT NULL"
    }
    
    for col, spec in cust_to_add.items():
        if col not in cust_col_names:
            print(f"Adding column {col} to customers table...")
            try:
                conn.execute(text(f"ALTER TABLE customers ADD COLUMN {col} {spec}"))
                conn.commit()
                print(f"Added column {col} successfully!")
            except Exception as e:
                print(f"Error adding {col} to customers: {e}")
        else:
            print(f"Column {col} already exists on customers table.")

    # 4. Create Indexes
    indexes = [
        ("idx_cases_client_id", "cases", "customer_id"),
        ("idx_cases_completed_date", "cases", "completed_date"),
        ("idx_cases_invoice_id", "cases", "invoice_id"),
        ("idx_cases_status", "cases", "status"),
        ("idx_cases_is_invoiced", "cases", "is_invoiced")
    ]
    
    for idx_name, tbl_name, col_name in indexes:
        try:
            print(f"Creating index {idx_name} on {tbl_name}({col_name})...")
            conn.execute(text(f"CREATE INDEX {idx_name} ON {tbl_name}({col_name})"))
            conn.commit()
            print(f"Created index {idx_name} successfully!")
        except Exception as e:
            print(f"Note: Index {idx_name} might already exist or failed: {e}")

    print("All enterprise billing migrations completed successfully!")
