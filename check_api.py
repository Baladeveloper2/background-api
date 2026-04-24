import requests
import json

try:
    r = requests.get('http://localhost:8000/api/v1/cases/')
    print(f"Status: {r.status_code}")
    data = r.json()
    if isinstance(data, list):
        for c in data:
            if c.get('case_ref_no') == 'IBM002':
                print(f"Found IBM002: in_tat={c.get('in_tat')} out_tat={c.get('out_tat')}")
    else:
        print(f"Response: {data}")
except Exception as e:
    print(f"Error: {e}")
