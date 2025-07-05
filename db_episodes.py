"""
Manages PostgreSQL database operations for scheduled episodes and schedule configuration.
"""
import psycopg2
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# This context manager will be injected from db_manager.py to handle connections.
managed_db_connection = None

def get_schedule_config() -> Optional[Dict[str, Any]]:
    """Fetches the current schedule configuration."""
    try:
        with managed_db_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT schedule_type, times_per_period, days_of_week, publish_time_local, podcast_timezone FROM schedule_config WHERE id = 1")
            config_data = cursor.fetchone()
            if config_data: return dict(config_data)
            logger.warning("No schedule configuration found in the database.")
            return None
    except psycopg2.Error as e:
        logger.error(f"Database error fetching schedule config: {e}")
        return None

def update_schedule_config(schedule_data: Dict[str, Any]) -> bool:
    """Updates the schedule configuration."""
    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute("""
                UPDATE schedule_config SET
                    schedule_type = %s,
                    times_per_period = %s,
                    days_of_week = %s,
                    publish_time_local = %s,
                    podcast_timezone = %s
                WHERE id = 1
            """, (
                schedule_data.get('schedule_type'),
                schedule_data.get('times_per_period'),
                schedule_data.get('days_of_week'),
                schedule_data.get('publish_time_local'),
                schedule_data.get('podcast_timezone')
            ))
            conn.commit()
            logger.info(f"Schedule configuration updated: {schedule_data}")
            return True
    except psycopg2.Error as e: logger.error(f"Database error updating schedule config: {e}")

def get_latest_scheduled_publish_time() -> Optional[str]:
    """Queries the internal DB for the latest known scheduled publish time."""
    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT MAX(publish_at_utc_iso) FROM episodes WHERE publish_at_utc_iso IS NOT NULL")
            result = cursor.fetchone()
            if result and result[0]:
                logger.info(f"Latest known publish time from DB: {result[0]}")
                return result[0]
            logger.info("No previous publish times found in DB.")
            return None
    except psycopg2.Error as e:
        logger.error(f"Database error getting latest publish time: {e}")
        return None

def record_scheduled_episode(ep_num: Optional[str], episode_topic: Optional[str], spreaker_id: Optional[str], publish_time_utc: str,
                            processed_mp3_path: str, poster_path: str = None, show_notes_path: str = None, 
                            tags_list: Optional[List[str]] = None):
    """Records a successfully scheduled episode into the internal database."""
    tags_str = ",".join(tags_list) if tags_list else None
    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO episodes (episode_number, episode_topic, spreaker_episode_id, processed_mp3_path, poster_path, show_notes_path, publish_at_utc_iso, tags)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (ep_num, episode_topic, spreaker_id, processed_mp3_path, poster_path, show_notes_path, publish_time_utc, tags_str))
            conn.commit()
            logger.info(f"Recorded episode {ep_num} ('{episode_topic}') to DB for {publish_time_utc} with tags: {tags_str if tags_str else 'None'}.")
    except psycopg2.Error as e:
        logger.error(f"Database error recording scheduled episode (ep: {ep_num}, topic: {episode_topic}, time: {publish_time_utc}): {e}")

def delete_scheduled_episode(episode_id: int) -> bool:
    """Deletes a scheduled episode record from the database."""
    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute("DELETE FROM episodes WHERE id = %s", (episode_id,))
            conn.commit()
            logger.info(f"Scheduled episode ID {episode_id} deleted successfully.")
            return True
    except psycopg2.Error as e:
        logger.error(f"Database error deleting scheduled episode ID {episode_id}: {e}")
        return False

def update_episode_metadata_in_db(spreaker_episode_id: str,
                                  new_publish_at_utc_iso: Optional[str] = None,
                                  new_tags_list: Optional[List[str]] = None,
                                  new_processed_mp3_path: Optional[str] = None,
                                  new_poster_path: Optional[str] = None, new_show_notes_path: Optional[str] = None) -> bool:
    """Updates publish time and/or tags for an episode in the local 'episodes' table based on Spreaker ID."""
    if not new_publish_at_utc_iso and new_tags_list is None and not new_processed_mp3_path and not new_poster_path and not new_show_notes_path:
        logger.info(f"No metadata provided to update for Spreaker ID {spreaker_episode_id} in local DB.")
        return False
    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            updates = []
            params = []
            if new_publish_at_utc_iso: updates.append("publish_at_utc_iso = %s"); params.append(new_publish_at_utc_iso)
            if new_processed_mp3_path: updates.append("processed_mp3_path = %s"); params.append(new_processed_mp3_path)
            if new_poster_path: updates.append("poster_path = %s"); params.append(new_poster_path)
            if new_show_notes_path: updates.append("show_notes_path = %s"); params.append(new_show_notes_path)
            if new_tags_list is not None: updates.append("tags = %s"); params.append(",".join(new_tags_list))
            params.append(spreaker_episode_id)

            sql = f"UPDATE episodes SET {', '.join(updates)}, created_at = NOW() WHERE spreaker_episode_id = %s"
            cursor.execute(sql, tuple(params))
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"Updated local DB metadata for Spreaker ID {spreaker_episode_id}.")
                return True
            logger.warning(f"No rows updated in local DB for Spreaker ID {spreaker_episode_id}. It might not exist.")
            return False
    except psycopg2.Error as e:
        logger.error(f"Database error updating metadata for Spreaker ID {spreaker_episode_id}: {e}")
        return False

def get_episode_details_for_reupload(episode_number_to_upload: str) -> Optional[Dict[str, Any]]:
    """Fetches all necessary details for an episode from the local DB for re-upload."""
    try:
        with managed_db_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("""
                SELECT episode_number, episode_topic, processed_mp3_path, poster_path, show_notes_path, tags
                FROM episodes
                WHERE episode_number = %s
                ORDER BY created_at DESC LIMIT 1
            """, (episode_number_to_upload,))
            data = cursor.fetchone()
            if data: return dict(data)
            logger.warning(f"No details found for episode {episode_number_to_upload} in local DB for re-upload.")
            return None
    except psycopg2.Error as e:
        logger.error(f"Database error fetching details for episode {episode_number_to_upload} for re-upload: {e}")
        return None

def get_all_scheduled_episodes() -> List[Dict[str, Any]]:
    """Fetches all episodes from the 'episodes' table, ordered by publish time."""
    episodes_list = []
    try:
        with managed_db_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("""
                SELECT id, episode_number, episode_topic, spreaker_episode_id, publish_at_utc_iso,
                       processed_mp3_path, poster_path, show_notes_path, tags, created_at
                FROM episodes
                ORDER BY publish_at_utc_iso DESC
            """)
            rows = cursor.fetchall()
            for row in rows: episodes_list.append(dict(row))
            return episodes_list
    except psycopg2.Error as e:
        logger.error(f"Database error fetching all scheduled episodes: {e}")
        return []

def get_episode_by_id(episode_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a specific episode by its primary key ID."""
    try:
        with managed_db_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT * FROM episodes WHERE id = %s", (episode_id,))
            data = cursor.fetchone()
            return dict(data) if data else None
    except psycopg2.Error as e:
        logger.error(f"Database error fetching episode ID {episode_id}: {e}")
        return None