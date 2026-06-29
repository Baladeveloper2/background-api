import httpx
import asyncio

async def test_health():
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get('http://127.0.0.1:8000/health')
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text}")

if __name__ == "__main__":
    asyncio.run(test_health())
