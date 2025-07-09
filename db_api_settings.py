"""
Database operations for API keys and application settings - works with both SQLite and PostgreSQL
"""
import logging
from typing import Optional
logger = logging.getLogger(__name__)
# This will be set by db_manager.py
managed_db_connection = None
def save_api_key(service_name: str, api_key_value: str) -> bool:
    """Saves or updates an API key for a given service."""
    try:
        with managed_db_connection() as conn:
            if hasattr(conn, 'cursor'):  # PostgreSQL
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO api_keys (service_name, api_key_value, updated_at)
                        VALUES (%s, %s, NOW())
                        ON CONFLICT(service_name) DO UPDATE SET
                            api_key_value = EXCLUDED.api_key_value,
                            updated_at = NOW()
                    """, (service_name, api_key_value))
                    conn.commit()
            else:  # SQLite
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO api_keys (service_name, api_key_value, updated_at)
                    VALUES (?, ?, datetime('now'))
                """, (service_name, api_key_value))
                conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving API key for '{service_name}': {e}")
        return False
def get_api_key(service_name: str) -> Optional[str]:
    """Fetches an API key for a given service."""
    try:
        with managed_db_connection() as conn:
            if hasattr(conn, 'cursor'):  # PostgreSQL
                with conn.cursor() as cursor:
                    cursor.execute("SELECT api_key_value FROM api_keys WHERE service_name = %s", (service_name,))
                    row = cursor.fetchone()
                    return row[0] if row else None
            else:  # SQLite
                cursor = conn.cursor()
                cursor.execute("SELECT api_key_value FROM api_keys WHERE service_name = ?", (service_name,))
                row = cursor.fetchone()
                return row[0] if row else None
    except Exception as e:
        logger.error(f"Error fetching API key for '{service_name}': {e}")
        return None
def set_application_setting(setting_name: str, setting_value: str) -> bool:
    """Saves or updates a global application setting."""
    try:
        with managed_db_connection() as conn:
            if hasattr(conn, 'cursor'):  # PostgreSQL
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO application_settings (setting_name, setting_value, updated_at)
                        VALUES (%s, %s, NOW())
                        ON CONFLICT(setting_name) DO UPDATE SET
                            setting_value = EXCLUDED.setting_value,
                            updated_at = NOW()
                    """, (setting_name, setting_value))
                    conn.commit()
            else:  # SQLite
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO application_settings (setting_name, setting_value, updated_at)
                    VALUES (?, ?, datetime('now'))
                """, (setting_name, setting_value))
                conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving application setting '{setting_name}': {e}")
        return False
def get_application_setting(setting_name: str, default_value: Optional[str] = None) -> Optional[str]:
    """Fetches a global application setting."""
    try:
        with managed_db_connection() as conn:
            if hasattr(conn, 'cursor'):  # PostgreSQL
                with conn.cursor() as cursor:
                    cursor.execute("SELECT setting_value FROM application_settings WHERE setting_name = %s", (setting_name,))
                    row = cursor.fetchone()
                    return row[0] if row else default_value
            else:  # SQLite
                cursor = conn.cursor()
                cursor.execute("SELECT setting_value FROM application_settings WHERE setting_name = ?", (setting_name,))
                row = cursor.fetchone()
                return row[0] if row else default_value
    except Exception as e:
        logger.error(f"Error fetching application setting '{setting_name}': {e}")
        return default_value
