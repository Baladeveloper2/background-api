from app.database import SessionLocal, engine, SQLALCHEMY_DATABASE_URL
from app import models
from sqlalchemy import inspect
import os

import traceback

def check_db():
    print(f"DATABASE_URL from app.database: {SQLALCHEMY_DATABASE_URL}")
    try:

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"Tables in database: {tables}")
        
        if "users" in tables:
            db = SessionLocal()
            try:
                # Query email and role to see if Enums are fine
                results = db.query(models.User.email, models.User.role).all()
                print(f"Number of users: {len(results)}")
                for email, role in results:
                    print(f"User email: {email}, Role: {role}")


            except Exception as inner_e:
                print(f"Error querying users: {inner_e}")
                traceback.print_exc()
            finally:
                db.close()
        else:
            print("Error: 'users' table not found!")
    except Exception as e:
        print(f"Error checking database: {e}")
        with open('error.log', 'w') as f:
            f.write(str(e))
            f.write("\n")
            f.write(traceback.format_exc())



if __name__ == "__main__":
    check_db()
