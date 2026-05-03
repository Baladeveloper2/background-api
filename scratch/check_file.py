import requests
import json

def check():
    try:
        # We need an auth token
        # This is a bit hard without a user, but we can check if the code changed.
        # Actually, let's just check the file content on disk to be 100% sure.
        with open("app/batch_routes.py", "r") as f:
            content = f.read()
            if "Entry Pending" in content:
                print("STALE CODE: 'Entry Pending' still found in file!")
            else:
                print("NEW CODE: 'Entry Pending' not found in file.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check()
