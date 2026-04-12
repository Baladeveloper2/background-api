from sqlalchemy import create_engine, text
try:
    engine = create_engine('mysql+pymysql://avnadmin:AVNS_ce7C0cV_01nkFa1rYPq@dataentry-dataentry.j.aivencloud.com:14419/defaultdb')
    with engine.connect() as conn:
        res = conn.execute(text('SELECT id, status, batch_id FROM cases')).all()
        print(f'Length: {len(res)}')
        print(f'Cases: {res}')
except Exception as e:
    print(f'Error: {e}')
