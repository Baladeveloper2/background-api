import asyncio
import httpx
from app.auth import create_access_token

async def check():
    token = create_access_token(data={"sub": "admin@bgvms.com", "role": "SUPER_ADMIN"})
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get("http://localhost:8000/api/v1/users", headers={"Authorization": f"Bearer {token}"}, timeout=10.0)
            print("Status code:", res.status_code)
            if res.status_code == 200:
                data = res.json()
                print("Returned users:", len(data))
                for u in data:
                    print(u.get("email"), "role:", u.get("role"), "id:", u.get("id"), "full_name:", u.get("full_name"))
            else:
                print("Error:", res.text)
        except Exception as e:
            print("Failed:", e)

asyncio.run(check())



