
import requests

def test():
    # We don't have a token easily, so we hit a known public endpoint to see if logs appear
    # Or we just assume the user will reload.
    print("Testing health endpoint to see if server is up...")
    try:
        res = requests.get("http://localhost:8000/health")
        print(f"Health check: {res.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
