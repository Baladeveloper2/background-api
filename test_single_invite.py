import httpx
import asyncio

async def test_single_invite():
    async with httpx.AsyncClient() as client:
        # Login
        r = await client.post('http://127.0.0.1:8000/api/v1/auth/login', data={'username':'zoneadmin@test.com', 'password':'password123'})
        token = r.json().get('access_token')
        print(f"Token: {token}")
        
        # Send link
        headers = {'Authorization': f'Bearer {token}'}
        payload = {
            "candidates": [
                {
                    "name": "Single Invite Test",
                    "email": "testsingle@example.com",
                    "phone": "9999999999",
                    "emp_id": "EMPTEST123"
                }
            ],
            "checks": ["Identity", "Address"],
            "send_links": True,
            "send_email": True,
            "send_sms": False,
            "custom_email_subject": "Test Single Invite",
            "custom_email_body": "<p>Hello {{candidate_name}}, Welcome to {{customer_name}}</p>"
        }
        r2 = await client.post(f'http://127.0.0.1:8000/api/v1/bulk-invite/candidates', json=payload, headers=headers)
        print(f"Status: {r2.status_code}")
        print(f"Response: {r2.text}")

if __name__ == "__main__":
    asyncio.run(test_single_invite())
