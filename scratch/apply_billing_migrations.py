import sqlite3
import os

db_path = "bgvms.db"

if not os.path.exists(db_path):
    print("Database bgvms.db not found!")
    exit(1)

print(f"Applying billing database migrations directly on {db_path}...")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Update customers table to add gst_number and billing_config
try:
    cursor.execute("ALTER TABLE customers ADD COLUMN gst_number VARCHAR(100) NULL;")
    print("Added COLUMN gst_number to customers.")
except sqlite3.OperationalError as e:
    print("Column gst_number might already exist:", e)

try:
    cursor.execute("ALTER TABLE customers ADD COLUMN billing_config TEXT NULL;")
    print("Added COLUMN billing_config to customers.")
except sqlite3.OperationalError as e:
    print("Column billing_config might already exist:", e)


# 2. Update cases table to add billing attributes
try:
    cursor.execute("ALTER TABLE cases ADD COLUMN is_billable BOOLEAN DEFAULT 1;")
    print("Added COLUMN is_billable to cases.")
except sqlite3.OperationalError as e:
    print("Column is_billable might already exist:", e)

try:
    cursor.execute("ALTER TABLE cases ADD COLUMN is_invoiced BOOLEAN DEFAULT 0;")
    print("Added COLUMN is_invoiced to cases.")
except sqlite3.OperationalError as e:
    print("Column is_invoiced might already exist:", e)

try:
    cursor.execute("ALTER TABLE cases ADD COLUMN invoice_id VARCHAR(36) NULL;")
    print("Added COLUMN invoice_id to cases.")
except sqlite3.OperationalError as e:
    print("Column invoice_id might already exist:", e)

try:
    cursor.execute("ALTER TABLE cases ADD COLUMN billed_at DATETIME NULL;")
    print("Added COLUMN billed_at to cases.")
except sqlite3.OperationalError as e:
    print("Column billed_at might already exist:", e)

try:
    cursor.execute("ALTER TABLE cases ADD COLUMN billing_amount FLOAT DEFAULT 0.0;")
    print("Added COLUMN billing_amount to cases.")
except sqlite3.OperationalError as e:
    print("Column billing_amount might already exist:", e)


# 3. Create invoices table if not exists
try:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id VARCHAR(36) PRIMARY KEY,
        invoice_number VARCHAR(100) UNIQUE NOT NULL,
        client_id VARCHAR(36) NOT NULL,
        billing_cycle VARCHAR(50) DEFAULT 'MONTHLY',
        billing_period_from DATETIME NOT NULL,
        billing_period_to DATETIME NOT NULL,
        subtotal FLOAT DEFAULT 0.0,
        gst_amount FLOAT DEFAULT 0.0,
        total_amount FLOAT DEFAULT 0.0,
        generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        due_date DATETIME NULL,
        status VARCHAR(50) DEFAULT 'DRAFT',
        generated_by VARCHAR(36) NULL,
        modified_by VARCHAR(36) NULL,
        paid_at DATETIME NULL,
        FOREIGN KEY(client_id) REFERENCES customers(id) ON DELETE CASCADE,
        FOREIGN KEY(generated_by) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY(modified_by) REFERENCES users(id) ON DELETE SET NULL
    );
    """)
    print("Created Table invoices successfully.")
except sqlite3.OperationalError as e:
    print("Error creating invoices table:", e)

# 4. Set indexes
try:
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_invoices_invoice_number ON invoices (invoice_number);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_invoices_client_id ON invoices (client_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_cases_invoice_id ON cases (invoice_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_cases_is_invoiced ON cases (is_invoiced);")
    print("Created indexes successfully.")
except sqlite3.OperationalError as e:
    print("Error creating indexes:", e)

conn.commit()
conn.close()
print("Direct SQLite migrations applied successfully!")
