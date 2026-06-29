import os
from dotenv import load_dotenv

load_dotenv()
logo = os.getenv("LOGO_URL", "fallback")
print(f"LOGO: '{logo}'")
