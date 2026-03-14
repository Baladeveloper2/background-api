import requests

response = requests.post("http://localhost:8000/auth/login", data={"username": "admin@bgvms.com", "password": "admin123"})
if response.status_code == 200:
    print("Login successful!")
    print(response.json())
else:
    print("Login failed with status code:", response.status_code)
    print(response.text)
