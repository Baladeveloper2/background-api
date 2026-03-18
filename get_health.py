import requests
import json
try:
    r = requests.get('http://localhost:8000/health')
    with open("health_resp.txt", "w") as f:
        json.dump(r.json(), f, indent=2)
    print("Health response saved to health_resp.txt")
except Exception as e:
    print(f"Error fetching health: {e}")
