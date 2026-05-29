from sqlalchemy import create_engine, text
from passlib.context import CryptContext

def test():
    pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
    engine = create_engine('mysql+pymysql://avnadmin:AVNS_ce7C0cV_01nkFa1rYPq@dataentry-dataentry.j.aivencloud.com:14419/defaultdb')
    with engine.connect() as conn:
        row = conn.execute(text("SELECT hashed_password FROM users WHERE email='customer@bgvms.com'")).fetchone()
        if row:
            hashed = row[0]
            print('Matches Password@123:', pwd_context.verify('Password@123', hashed))
            print('Matches password123:', pwd_context.verify('password123', hashed))
            print('Matches Admin@123:', pwd_context.verify('Admin@123', hashed))
            print('Matches pass123:', pwd_context.verify('pass123', hashed))
        else:
            print('User not found')

if __name__ == '__main__':
    test()
