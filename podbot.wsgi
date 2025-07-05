import sys
import os

# Add the project directory to the Python path
# This ensures that 'app.py' can be imported correctly
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the Flask application instance from app.py
from app import app

# The 'app' object is now the WSGI application callable
# WSGI servers like Gunicorn will look for this 'app' object.