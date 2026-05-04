import httpx
import asyncio

async def test_api():
    token = "d0c51f9115db443bba3b88ea970c6145"
    url = f"http://localhost:8000/api/v1/public/insufficiency/{token}"
    async with httpx.AsyncClient() as client:
        res = await client.get(url)
        print(f"Status: {res.status_code}")
        print(f"Body: {res.text}")

if __name__ == "__main__":
    asyncio.run(test_api())
