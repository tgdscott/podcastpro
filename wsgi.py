from app import create_app
import db_manager
import logging
import os

app = create_app()

# Initialize the database when the application starts.
# Make this optional and fast-failing to prevent startup delays
with app.app_context():
    # Only try database initialization if explicitly enabled
    if os.environ.get('INIT_DATABASE', 'false').lower() == 'true':
        try:
            logging.info("Database initialization requested - attempting connection...")
            db_manager.init_db()
            logging.info("Database initialization complete.")
        except Exception as e:
            logging.warning(f"Database initialization failed (continuing anyway): {e}")
    else:
        logging.info("Database initialization skipped (set INIT_DATABASE=true to enable)")
        logging.info("Application starting without database - API endpoints will handle DB errors gracefully")