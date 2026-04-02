import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv('CLOUDINARY_URL')
if url:
    print(f"URL Length: {len(url)}")
    print(f"URL Hex: {url.encode('utf-8').hex()}")
    print(f"URL Repr: {repr(url)}")
else:
    print("CLOUDINARY_URL not found in environment.")
