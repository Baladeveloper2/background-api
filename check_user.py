from app import models, database

def check():
    db = database.SessionLocal()
    u = db.query(models.User).filter(models.User.email == 'customer@bgvms.com').first()
    if u:
        print(f"ID: {u.id}")
        print(f"ROLE: {u.role}")
        print(f"CUSTOMER_ID: {u.customer_id}")
    else:
        print("User not found.")
    db.close()

if __name__ == "__main__":
    check()
