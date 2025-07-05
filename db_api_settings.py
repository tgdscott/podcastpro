"""
Manages PostgreSQL database operations for API keys and application settings.
"""
import psycopg2
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# This context manager will be injected from db_manager.py to handle connections.
managed_db_connection = None

def _initialize_default_app_settings(cursor: psycopg2.extensions.cursor):
    """Helper to insert default application settings if they don't exist."""
    default_settings = {
        'enable_elevenlabs': 'true',
        'enable_gemini': 'true',
        'enable_omdb': 'true',
        'enable_spreaker': 'true',
        'show_notes_template': '' # Default empty template
    }
    for name, value in default_settings.items():
        cursor.execute("INSERT INTO application_settings (setting_name, setting_value) VALUES (%s, %s) ON CONFLICT (setting_name) DO NOTHING", (name, value))

def save_api_key(service_name: str, api_key_value: str) -> bool:
    """Saves or updates an API key for a given service."""
    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO api_keys (service_name, api_key_value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT(service_name) DO UPDATE SET
                    api_key_value = EXCLUDED.api_key_value,
                    updated_at = NOW()
            """, (service_name, api_key_value))
            conn.commit()
            logger.info(f"API key for service '{service_name}' saved/updated.")
            return True
    except psycopg2.Error as e:
        logger.error(f"Database error saving API key for '{service_name}': {e}")
        return False

def get_api_key(service_name: str) -> Optional[str]:
    """Fetches an API key for a given service."""
    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT api_key_value FROM api_keys WHERE service_name = %s", (service_name,))
            row = cursor.fetchone()
            if row: return row[0]
            return None
    except psycopg2.Error as e:
        logger.error(f"Database error fetching API key for '{service_name}': {e}")
        return None

def set_application_setting(setting_name: str, setting_value: str) -> bool:
    """Saves or updates a global application setting."""
    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO application_settings (setting_name, setting_value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT(setting_name) DO UPDATE SET
                    setting_value = EXCLUDED.setting_value,
                    updated_at = NOW()
            """, (setting_name, setting_value))
            conn.commit()
            logger.info(f"Application setting '{setting_name}' saved/updated to '{setting_value}'.")
            return True
    except psycopg2.Error as e:
        logger.error(f"Database error saving application setting '{setting_name}': {e}")
        return False

def get_application_setting(setting_name: str, default_value: Optional[str] = None) -> Optional[str]:
    """Fetches a global application setting. Returns default_value if not found."""
    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT setting_value FROM application_settings WHERE setting_name = %s", (setting_name,))
            row = cursor.fetchone()
            if row: return row[0]
            return default_value
    except psycopg2.Error as e:
        logger.error(f"Database error fetching application setting '{setting_name}': {e}")
        return default_value