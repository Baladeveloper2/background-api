import app
import os
print(f"DEBUG: app module path is {os.path.abspath(app.__file__)}")
print(f"DEBUG: main module path is {os.path.abspath(app.main.__file__)}")
