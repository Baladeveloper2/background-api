
import json
with open('api_out.json', 'r', encoding='utf-16') as f:
    data = json.load(f)
    print(f"LEN: {len(data)}")
    for d in data:
        print(f"ID: {d.get('id')} | Name: {d.get('candidate_name')}")
