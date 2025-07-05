"""
Manages PostgreSQL database operations for processing jobs and their logs.
"""
import psycopg2
import psycopg2.extras # For dictionary cursors
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import re

logger = logging.getLogger(__name__)

# This context manager will be injected from db_manager.py to handle connections.
managed_db_connection = None

def add_processing_job(template_path: str, recording_filename: str,
                       uploaded_recording_path: str, output_base_filename: str,
                       episode_number: Optional[str] = None,
                       episode_topic: Optional[str] = None,
                       ai_intro_text: Optional[str] = None,
                       remove_fillers: bool = True,
                       stop_word_detection_enabled: bool = True,
                       intern_command_enabled: bool = False,
                       intern_command_keyword: str = 'intern',
                       season_number: Optional[str] = None,
                       remove_pauses: bool = True,
                       generate_transcript: bool = True,
                       generate_show_notes: bool = True,
                       use_gemini_for_summary: bool = False,
                       download_poster: bool = True,
                       min_pause_duration_sec: float = 1.5,
                       custom_filler_words_csv: Optional[str] = None,
                       job_base_output_dir: Optional[str] = None,
                       podcast_id: Optional[int] = None,
                       # NEW: Commercial Break Settings
                       commercial_breaks_enabled: bool = False,
                       commercial_breaks_count: int = 1,
                       commercial_breaks_min_duration_between_sec: float = 300.0,
                       commercial_breaks_max_duration_between_sec: float = 600.0,
                       commercial_breaks_min_silence_ms: int = 1000,
                       commercial_breaks_cue_phrases: Optional[str] = None, # Comma-separated
                       commercial_breaks_audio_keys: Optional[str] = None # Comma-separated
                       ) -> Optional[int]:
    """Adds a new podcast processing job to the database."""
    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO processing_jobs (
                    template_path, recording_filename, uploaded_recording_path,
                    output_base_filename, status, episode_number, episode_topic,
                    ai_intro_text, remove_fillers, stop_word_detection_enabled,
                    intern_command_enabled, intern_command_keyword, season_number,
                    remove_pauses, generate_transcript, generate_show_notes, use_gemini_for_summary,
                    download_poster, min_pause_duration_sec, custom_filler_words_csv,
                    job_base_output_dir, podcast_id,
                    commercial_breaks_enabled, commercial_breaks_count,
                    commercial_breaks_min_duration_between_sec, commercial_breaks_max_duration_between_sec,
                    commercial_breaks_min_silence_ms, commercial_breaks_cue_phrases, commercial_breaks_audio_keys
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (template_path, recording_filename, uploaded_recording_path,
                  output_base_filename, 'pending', episode_number, episode_topic, ai_intro_text,
                  remove_fillers, stop_word_detection_enabled, intern_command_enabled, intern_command_keyword,
                  season_number, remove_pauses, generate_transcript, generate_show_notes,
                  use_gemini_for_summary, download_poster, min_pause_duration_sec, custom_filler_words_csv,
                  job_base_output_dir, podcast_id,
                  commercial_breaks_enabled, commercial_breaks_count,
                  commercial_breaks_min_duration_between_sec, commercial_breaks_max_duration_between_sec,
                  commercial_breaks_min_silence_ms, commercial_breaks_cue_phrases, commercial_breaks_audio_keys))
            job_id = cursor.fetchone()[0]
            conn.commit()
            logger.info(f"Added new processing job with ID: {job_id}")
            return job_id
    except psycopg2.Error as e:
        logger.error(f"Database error adding processing job: {e}")
        return None

def get_job_details(job_id: int) -> Optional[Dict[str, Any]]:
    """Fetches details for a specific processing job."""
    try:
        with managed_db_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT * FROM processing_jobs WHERE id = %s", (job_id,))
            job_data = cursor.fetchone()
            if job_data: return dict(job_data)
            return None
    except psycopg2.Error as e:
        logger.error(f"Database error fetching job {job_id}: {e}")
        return None

def update_job_status(job_id: int, status: str, error_message: Optional[str] = None) -> bool:
    """Updates the status and optionally an error message for a job."""
    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            status_to_set = f"{status}: {error_message[:200]}" if error_message else status
            cursor.execute("UPDATE processing_jobs SET status = %s, updated_at = NOW() WHERE id = %s", (status_to_set, job_id))
        conn.commit()
        logger.info(f"Updated job {job_id} status to '{status_to_set}'")
        return True
    except psycopg2.Error as e:
        logger.error(f"Database error updating job {job_id} status: {e}")
        return False

def get_job_status(job_id: int) -> Optional[str]:
    """Fetches just the status for a specific processing job."""
    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT status FROM processing_jobs WHERE id = %s", (job_id,))
            row = cursor.fetchone()
            if row: return row[0]
            logger.warning(f"Attempted to get status for non-existent job ID {job_id}")
            return None
    except psycopg2.Error as e:
        logger.error(f"Database error fetching status for job {job_id}: {e}")
        return None

def get_all_active_jobs() -> List[Dict[str, Any]]:
    """Fetches all jobs that are 'pending' or 'processing'."""
    jobs_list = []
    try:
        with managed_db_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT * FROM processing_jobs WHERE status = 'pending' OR status = 'processing' ORDER BY created_at ASC")
            rows = cursor.fetchall()
            for row in rows: jobs_list.append(dict(row))
            return jobs_list
    except psycopg2.Error as e:
        logger.error(f"Database error fetching active jobs: {e}")
        return []

def delete_job(job_id: int) -> bool:
    """Deletes a job from the processing_jobs table by its ID."""
    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute("DELETE FROM processing_jobs WHERE id = %s", (job_id,))
            conn.commit()
            logger.info(f"Deleted job with ID: {job_id}")
            return True
    except psycopg2.Error as e:
        logger.error(f"Database error deleting job {job_id}: {e}")
        return False

def get_job_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetches completed or failed jobs, ordered by most recent first."""
    jobs_list = []
    try:
        with managed_db_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM processing_jobs
                WHERE status NOT IN ('pending', 'processing')
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()
            for row in rows: jobs_list.append(dict(row))
            return jobs_list
    except psycopg2.Error as e:
        logger.error(f"Database error fetching job history: {e}")
        return []

def recreate_job_from_existing(original_job_id: int) -> Optional[int]:
    """
    Creates a new job by copying the settings from an existing job.
    Returns the new job's ID if successful, otherwise None.
    """
    original_job_details = get_job_details(original_job_id)
    if not original_job_details:
        logger.error(f"Cannot recreate job. Original job ID {original_job_id} not found.")
        return None

    try:
        original_base_filename = original_job_details.get('output_base_filename', f'job_{original_job_id}')
        base_name_match = re.match(r'^(.*)_\d{14}(_rerun)?$', original_base_filename)
        base_name = base_name_match.group(1) if base_name_match else original_base_filename
        new_output_base_filename = f"{base_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}_rerun"

        new_job_id = add_processing_job(
            podcast_id=original_job_details.get('podcast_id'),
            template_path=original_job_details.get('template_path'),
            recording_filename=original_job_details.get('recording_filename'),
            uploaded_recording_path=original_job_details.get('uploaded_recording_path'),
            output_base_filename=new_output_base_filename,
            episode_number=original_job_details.get('episode_number'),
            episode_topic=original_job_details.get('episode_topic'),
            season_number=original_job_details.get('season_number'),
            ai_intro_text=original_job_details.get('ai_intro_text'),
            remove_fillers=bool(original_job_details.get('remove_fillers')),
            remove_pauses=bool(original_job_details.get('remove_pauses')),
            generate_transcript=bool(original_job_details.get('generate_transcript')),
            generate_show_notes=bool(original_job_details.get('generate_show_notes')),
            use_gemini_for_summary=bool(original_job_details.get('use_gemini_for_summary')),
            download_poster=bool(original_job_details.get('download_poster')),
            min_pause_duration_sec=original_job_details.get('min_pause_duration_sec'),
            custom_filler_words_csv=original_job_details.get('custom_filler_words_csv'),
            stop_word_detection_enabled=bool(original_job_details.get('stop_word_detection_enabled')),
            intern_command_enabled=bool(original_job_details.get('intern_command_enabled')),
            intern_command_keyword=original_job_details.get('intern_command_keyword'),
            job_base_output_dir=original_job_details.get('job_base_output_dir'),
            commercial_breaks_enabled=bool(original_job_details.get('commercial_breaks_enabled')),
            commercial_breaks_count=original_job_details.get('commercial_breaks_count'),
            commercial_breaks_min_duration_between_sec=original_job_details.get('commercial_breaks_min_duration_between_sec'),
            commercial_breaks_max_duration_between_sec=original_job_details.get('commercial_breaks_max_duration_between_sec'),
            commercial_breaks_min_silence_ms=original_job_details.get('commercial_breaks_min_silence_ms'),
            commercial_breaks_cue_phrases=original_job_details.get('commercial_breaks_cue_phrases'),
            commercial_breaks_audio_keys=original_job_details.get('commercial_breaks_audio_keys')
        )

        if new_job_id: logger.info(f"Successfully recreated job {original_job_id} as new job {new_job_id}.")
        else: logger.error(f"Failed to recreate job {original_job_id} using add_processing_job.")
        return new_job_id
    except Exception as e:
        logger.error(f"Exception while recreating job {original_job_id}: {e}", exc_info=True)
        return None

def add_job_log(job_id: int, log_level: str, message: str):
    """Adds a log entry for a specific job."""
    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO job_logs (job_id, level, message) VALUES (%s, %s, %s)",
                (job_id, log_level, message)
            )
            conn.commit()
    except psycopg2.Error as e:
        # Use standard print for this critical error as logging might also fail
        print(f"FATAL: Could not write log to database for job {job_id}. Error: {e}")

def get_job_logs(job_id: int) -> list:
    """Retrieves all log entries for a specific job, ordered by timestamp."""
    try:
        with managed_db_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute("SELECT timestamp, level, message FROM job_logs WHERE job_id = %s ORDER BY timestamp ASC", (job_id,))
            logs = cursor.fetchall()
            # Convert rows to plain dicts
            return [dict(log) for log in logs]
    except psycopg2.Error as e:
        logger.error(f"Database error fetching logs for job {job_id}: {e}")
        return []
