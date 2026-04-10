import sys
import os
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app import models
from app.auth_routes import create_access_token
import json
import requests

db = SessionLocal()
try:
    user = db.query(models.User).filter(models.User.email == 'admin@bgvms.com').first()
    # In auth_routes.py, create_access_token takes (data, expires_delta=None)
    token = create_access_token({
        'sub': user.email, 
        'role': user.role.value if hasattr(user.role, 'value') else user.role, 
        'full_name': user.full_name, 
        'permissions': user.bvs_permissions
    })
    
    headers = {'Authorization': f'Bearer {token}'}
    # Use 127.0.0.1 instead of localhost to be safer
    r = requests.get('http://127.0.0.1:8000/cases', headers=headers)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Total cases returned: {len(data)}")
        for x in data:
            print(f"ID: {x.get('id')}, Ref: {x.get('case_ref_no')}, Checks: {len(x.get('checks', []))}")
    else:
        print(r.text)
finally:
    db.close()
