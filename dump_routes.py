from app.main import app
import json

routes_info = []
for route in app.routes:
    if hasattr(route, "path"):
        routes_info.append({
            "path": route.path,
            "methods": list(route.methods) if hasattr(route, "methods") else []
        })

with open("full_routes_debug.json", "w") as f:
    json.dump(routes_info, f, indent=2)

print("Routes info saved to full_routes_debug.json")
