import requests

try:
    res = requests.get('http://localhost:8000/health')
    print("Health check status code:", res.status_code)
    print("Health check response:", res.json())
except Exception as e:
    print("Failed to connect:", e)
