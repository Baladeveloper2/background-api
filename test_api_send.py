import httpx
import asyncio

async def test_send_link():
    async with httpx.AsyncClient() as client:
        # Login
        r = await client.post('http://127.0.0.1:8000/api/v1/auth/login', data={'username':'zoneadmin@test.com', 'password':'password123'})
        token = r.json().get('access_token')
        
        # Send link
        headers = {'Authorization': f'Bearer {token}'}
        payload = {"checks": ["Identity", "Address"]}
        case_id = "59576274-3784-47e6-8b7a-3262f75aea12"
        r2 = await client.post(f'http://127.0.0.1:8000/api/v1/cases/{case_id}/send-bgv-link', json=payload, headers=headers)
        print(f"Status: {r2.status_code}")
        print(f"Response: {r2.text}")

if __name__ == "__main__":
    asyncio.run(test_send_link())
