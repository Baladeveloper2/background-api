from pydantic import ValidationError
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.schemas import UserCreate

payload = {
    "full_name": "BALAMURUGAN S",
    "email": "verifiers@bgvms.com",
    "password": "password123",
    "role": "USER",
    "role_id": "some-uuid",
    "territory": "",
    "business_unit": "",
    "status": "ACTIVE"
}

try:
    user = UserCreate(**payload)
    print("Validation Successful")
    print(user.model_dump())
except ValidationError as e:
    print("Validation Failed")
    print(e.json())
