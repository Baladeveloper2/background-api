import sys
import os
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app import models
from app.auth import create_access_token
import json
import requests
from collections import Counter

db = SessionLocal()
try:
    user = db.query(models.User).filter(models.User.email == 'admin@bgvms.com').first()
    token = create_access_token(data={
        "sub": user.email, 
        "role": user.role, 
        "full_name": user.full_name,
        "permissions": user.bvs_permissions
    })
    
    headers = {'Authorization': f'Bearer {token}'}
    r = requests.get('http://127.0.0.1:8000/cases', headers=headers)
    if r.status_code == 200:
        data = r.json()
        refs = [x['case_ref_no'] for x in data]
        print(f"Total items in list: {len(data)}")
        item_counts = Counter(refs)
        for ref, count in item_counts.items():
            print(f"Ref {ref} appears {count} times")
    else:
        print(r.text)
finally:
    db.close()
