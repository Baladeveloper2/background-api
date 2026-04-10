import sys
import os
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app import models
from app.auth import create_access_token
import json
import requests

db = SessionLocal()
try:
    user = db.query(models.User).filter(models.User.email == 'admin@bgvms.com').first()
    if not user:
        print("User not found")
        sys.exit(1)
        
    permissions = user.bvs_permissions if not user.role_id else (user.role_rel.permissions or {})
    
    token = create_access_token(data={
        "sub": user.email, 
        "role": user.role, 
        "full_name": user.full_name,
        "permissions": permissions
    })
    
    headers = {'Authorization': f'Bearer {token}'}
    r = requests.get('http://127.0.0.1:8000/cases', headers=headers)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Total cases returned: {len(data)}")
        for x in data:
            print(f"ID: {x.get('id')}, Ref: {x.get('case_ref_no')}, Subject: {x.get('candidate_name')}")
    else:
        print(r.text)
finally:
    db.close()
