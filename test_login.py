import httpx
import asyncio

async def test_login():
    async with httpx.AsyncClient() as client:
        r = await client.post('http://127.0.0.1:8000/api/v1/auth/login', data={'username':'zoneadmin@test.com', 'password':'password123'})
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text}")

if __name__ == "__main__":
    asyncio.run(test_login())
