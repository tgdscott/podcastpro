import sqlite3
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the database path, assuming this script is in the root project directory
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'podbot.db')

def get_existing_columns(cursor, table_name):
    """Returns a set of existing column names for a given table."""
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        return {row[1] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        logging.warning(f"Table '{table_name}' does not exist yet. It will be created by the application on next run.")
        return set()

def migrate_database():
    """
    Checks for and adds missing columns to tables.
    This is a simple migration script to keep the schema in sync with the code.
    """
    logging.info(f"Connecting to database at {DATABASE_PATH}...")
    if not os.path.exists(DATABASE_PATH):
        logging.error("Database file not found. Please run the main application first to create it (e.g., by starting Gunicorn once).")
        return

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # --- Define the full, correct schema for all tables ---
    all_tables_schema = {
        "podcasts": {
            "id": "INTEGER PRIMARY KEY AUTOINCREMENT", "title": "TEXT NOT NULL UNIQUE", "author": "TEXT",
            "description": "TEXT", "default_cover_art_path": "TEXT", "default_template_path": "TEXT",
            "default_spreaker_show_id": "TEXT", "default_publish_timezone": "TEXT DEFAULT 'America/Los_Angeles'",
            "uses_omdb": "BOOLEAN DEFAULT 0", # <-- ADD THIS
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        }
        # Add other tables here if more migrations are needed in the future
    }

    # --- Iterate through all tables and apply migrations ---
    for table_name, schema in all_tables_schema.items():
        logging.info(f"\nChecking '{table_name}' table schema...")
        existing_cols = get_existing_columns(cursor, table_name)
        
        if not existing_cols: # If table doesn't exist, skip it. App will create it.
            continue
            
        logging.info(f"Found existing columns: {sorted(list(existing_cols))}")

        for col_name, col_type in schema.items():
            if col_name not in existing_cols:
                logging.warning(f"-> Missing column '{col_name}' in '{table_name}'. Adding it...")
                try:
                    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
                    logging.info(f"   ...Successfully added '{col_name}'.")
                except sqlite3.OperationalError as e:
                    logging.error(f"   ...ERROR adding column '{col_name}' to '{table_name}': {e}")

    conn.commit()
    conn.close()
    logging.info("\nDatabase migration check complete.")

if __name__ == "__main__":
    migrate_database()