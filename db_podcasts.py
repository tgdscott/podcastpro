"""
Manages PostgreSQL database operations for podcast projects.
"""
import psycopg2
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# This context manager will be injected from db_manager.py to handle connections.
managed_db_connection = None

def add_podcast_project(title: str, author: Optional[str] = None, description: Optional[str] = None,
                        default_cover_art_path: Optional[str] = None,
                        default_template_path: Optional[str] = None,
                        default_spreaker_show_id: Optional[str] = None,
                        default_publish_timezone: Optional[str] = 'America/Los_Angeles',
                        uses_omdb: bool = False) -> Optional[int]:
    """Adds a new podcast project to the database."""
    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO podcasts (title, author, description, default_cover_art_path, default_template_path, default_spreaker_show_id, default_publish_timezone, uses_omdb, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING id;
            """, (title, author, description, default_cover_art_path, default_template_path, default_spreaker_show_id, default_publish_timezone, uses_omdb))
            podcast_id = cursor.fetchone()[0]
            conn.commit()
            logger.info(f"Added new podcast project '{title}' with ID: {podcast_id}")
            return podcast_id
    except psycopg2.errors.UniqueViolation:
        logger.error(f"Failed to add podcast project: Title '{title}' already exists.")
        return None
    except psycopg2.Error as e:
        logger.error(f"Database error adding podcast project '{title}': {e}")
        return None

def get_podcast_project(podcast_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a specific podcast project by its ID."""
    try:
        with managed_db_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT * FROM podcasts WHERE id = %s", (podcast_id,))
            data = cursor.fetchone()
            return dict(data) if data else None
    except psycopg2.Error as e:
        logger.error(f"Database error fetching podcast project ID {podcast_id}: {e}")
        return None

def get_all_podcast_projects() -> List[Dict[str, Any]]:
    """Fetches all podcast projects from the database."""
    projects = []
    try:
        with managed_db_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT id, title, author, default_template_path FROM podcasts ORDER BY title ASC")
            rows = cursor.fetchall()
            for row in rows:
                projects.append(dict(row))
    except psycopg2.Error as e:
        logger.error(f"Database error fetching all podcast projects: {e}")
    return projects

def update_podcast_project(podcast_id: int, title: Optional[str] = None, author: Optional[str] = None,
                           description: Optional[str] = None, default_cover_art_path: Optional[str] = None,
                           default_template_path: Optional[str] = None,
                           default_spreaker_show_id: Optional[str] = None, default_publish_timezone: Optional[str] = None,
                           uses_omdb: Optional[bool] = None) -> bool:
    """Updates an existing podcast project."""
    fields_to_update = []
    params = []

    if title is not None: fields_to_update.append("title = %s"); params.append(title)
    if author is not None: fields_to_update.append("author = %s"); params.append(author)
    if description is not None: fields_to_update.append("description = %s"); params.append(description)
    if default_cover_art_path is not None: fields_to_update.append("default_cover_art_path = %s"); params.append(default_cover_art_path)
    if default_template_path is not None: fields_to_update.append("default_template_path = %s"); params.append(default_template_path)
    if default_spreaker_show_id is not None: fields_to_update.append("default_spreaker_show_id = %s"); params.append(default_spreaker_show_id)
    if default_publish_timezone is not None: fields_to_update.append("default_publish_timezone = %s"); params.append(default_publish_timezone)
    if uses_omdb is not None: fields_to_update.append("uses_omdb = %s"); params.append(uses_omdb)

    if not fields_to_update: return False

    fields_to_update.append("updated_at = NOW()")
    params.append(podcast_id)

    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            # The last parameter is for the WHERE clause
            sql = f"UPDATE podcasts SET {', '.join(fields_to_update)} WHERE id = %s"
            cursor.execute(sql, tuple(params))
            conn.commit()
            logger.info(f"Updated podcast project ID {podcast_id}.")
            return True
    except psycopg2.Error as e:
        logger.error(f"Database error updating podcast project ID {podcast_id}: {e}")
        return False