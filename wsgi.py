from app import create_app
import db_manager
import logging

app = create_app()

# Initialize the database when the application starts.
# The 'CREATE TABLE IF NOT EXISTS' statements in db_manager.py make this safe
# to run every time the container starts.
with app.app_context():
    logging.info("Initializing database schema...")
    db_manager.init_db()
    logging.info("Database initialization complete.")