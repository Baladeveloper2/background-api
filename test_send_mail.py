import asyncio
import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))
load_dotenv()
from app.email_utils import send_bgv_invitation_email

async def main():
    print("Testing email send...")
    success = await send_bgv_invitation_email('viktarmaksimchyk@gmail.com', 'Test Candidate', 'http://link.com')
    print(f"Result: {success}")

if __name__ == '__main__':
    asyncio.run(main())
