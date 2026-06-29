import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))
from app.email_utils import send_bgv_invitation_email

async def main():
    try:
        await send_bgv_invitation_email('test@test.com', 'Test Candidate', 'http://link.com')
        print("Template rendered successfully!")
    except Exception as e:
        print(f"Error: {repr(e)}")

if __name__ == '__main__':
    asyncio.run(main())
