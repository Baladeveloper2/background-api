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
        with open('api_full_dump.json', 'w', encoding='utf-8') as f:
            json.dump(data, f)
finally:
    db.close()
