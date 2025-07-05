#!/bin/bash
# Stop any existing Gunicorn processes
pkill gunicorn || true

# Exit immediately if a command exits with a non-zero status.
set -e
# Print commands and their arguments as they are executed.
set -x

# Activate the virtual environment
# No longer need to source the virtual environment if using absolute path to gunicorn

# Start Gunicorn
# -w 4: Use 4 worker processes (adjust based on your server's CPU cores)
# -b 0.0.0.0:5002: Bind to all interfaces on port 5002
# app:app: Specifies the Flask application instance (from app.py, where 'app' is the Flask app object)
# --timeout 120: Set a timeout for workers (e.g., 120 seconds for long file uploads/processing)
# --access-logfile -: Log access to stdout
# --error-logfile -: Log errors to stdout
# --log-level debug: Provides much more verbose output for debugging startup issues
/home/opc/general_podbot/venv/bin/gunicorn --workers 1 --bind 0.0.0.0:5002 --timeout 900 --log-level debug --access-logfile - --error-logfile - wsgi:app
