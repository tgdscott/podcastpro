import logging
import os
from typing import Optional, Dict, Any, List, Callable
from google.cloud.sql.connector import Connector, IPTypes
from contextlib import contextmanager

# Import database modules directly to have access to the module objects
import db_api_settings
import db_episodes
import db_jobs
import db_podcasts

logger = logging.getLogger(__name__)

INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME") # e.g. 'project:region:instance'
DB_USER = os.environ.get("DB_USER") # e.g. 'postgres'
DB_PASS = os.environ.get("DB_PASS") # e.g. 'your-password'
DB_NAME = os.environ.get("DB_NAME") # e.g. 'postgres'

connector = None

def get_db_connection() -> Any:
    """
    Establishes a connection to the Cloud SQL PostgreSQL database.
    Uses the Cloud SQL Python Connector.
    """
    global connector
    if connector is None:
        connector = Connector()

    conn = connector.connect(
        INSTANCE_CONNECTION_NAME,
        "psycopg2",
        user=DB_USER,
        password=DB_PASS,
        db=DB_NAME,
    )
    return conn

@contextmanager
def managed_db_connection():
    """Provides a database connection within a context, ensuring it's closed."""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        if conn:
            conn.close()


# --- Assign the get_db_connection function to imported modules ---
# This must happen BEFORE init_db() is called, and before any functions from these modules are used.
db_api_settings.managed_db_connection = managed_db_connection
db_episodes.managed_db_connection = managed_db_connection
db_jobs.managed_db_connection = managed_db_connection
db_podcasts.managed_db_connection = managed_db_connection

def init_db():
    """Initializes the PostgreSQL database and creates tables if they don't exist."""
    try:
        with managed_db_connection() as conn, conn.cursor() as cursor:
            logger.info("Initializing database tables...")
            # Create api_keys table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    service_name TEXT PRIMARY KEY,
                    api_key_value TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # Create application_settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS application_settings (
                    setting_name TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            db_api_settings._initialize_default_app_settings(cursor) # Insert default settings
            # Create podcasts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS podcasts (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL UNIQUE,
                    author TEXT,
                    description TEXT,
                    default_cover_art_path TEXT,
                    default_template_path TEXT,
                    default_spreaker_show_id TEXT,
                    default_publish_timezone TEXT DEFAULT 'America/Los_Angeles',
                    uses_omdb BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # Create processing_jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_jobs (
                    id SERIAL PRIMARY KEY,
                    podcast_id INTEGER REFERENCES podcasts(id) ON DELETE SET NULL,
                    template_path TEXT,
                    recording_filename TEXT,
                    uploaded_recording_path TEXT,
                    output_base_filename TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    episode_number TEXT,
                    episode_topic TEXT,
                    ai_intro_text TEXT,
                    remove_fillers BOOLEAN,
                    stop_word_detection_enabled BOOLEAN,
                    intern_command_enabled BOOLEAN,
                    intern_command_keyword TEXT,
                    season_number TEXT,
                    remove_pauses BOOLEAN,
                    generate_transcript BOOLEAN,
                    generate_show_notes BOOLEAN,
                    use_gemini_for_summary BOOLEAN,
                    download_poster BOOLEAN,
                    min_pause_duration_sec REAL,
                    custom_filler_words_csv TEXT,
                    job_base_output_dir TEXT,
                    commercial_breaks_enabled BOOLEAN,
                    commercial_breaks_count INTEGER,
                    commercial_breaks_min_duration_between_sec REAL,
                    commercial_breaks_max_duration_between_sec REAL,
                    commercial_breaks_min_silence_ms INTEGER,
                    commercial_breaks_cue_phrases TEXT,
                    commercial_breaks_audio_keys TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # Create job_logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_logs (
                    id SERIAL PRIMARY KEY,
                    job_id INTEGER NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
                    timestamp TIMESTAMPTZ DEFAULT NOW(),
                    log_level TEXT NOT NULL,
                    message TEXT NOT NULL
                )
            """)
            # Create episodes table (for scheduled/published episodes)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id SERIAL PRIMARY KEY,
                    episode_number TEXT,
                    episode_topic TEXT,
                    spreaker_episode_id TEXT UNIQUE,
                    processed_mp3_path TEXT,
                    poster_path TEXT,
                    show_notes_path TEXT,
                    publish_at_utc_iso TEXT UNIQUE,
                    tags TEXT,
                    transcript_url TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # Create schedule_config table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedule_config (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    schedule_type TEXT NOT NULL DEFAULT 'weekly',
                    times_per_period INTEGER NOT NULL DEFAULT 3,
                    days_of_week TEXT NOT NULL DEFAULT '0,2,4',
                    publish_time_local TEXT NOT NULL DEFAULT '05:00',
                    podcast_timezone TEXT NOT NULL DEFAULT 'America/Los_Angeles',
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cursor.execute("INSERT INTO schedule_config (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
            cursor.execute("""
                INSERT INTO podcasts (id, title, author, description)
                VALUES (1, 'Default Podcast', 'Your Name', 'Your Podcast Description')
                ON CONFLICT (id) DO NOTHING
            """)
            logger.info("Database tables checked/created successfully.")
        conn.commit()
    except Exception as e:
        logger.error(f"Error during database initialization: {e}", exc_info=True) # conn.rollback() is implicit

# --- Expose functions from other db modules ---
# API Settings
db_manager_save_api_key = db_api_settings.save_api_key
db_manager_get_api_key = db_api_settings.get_api_key
db_manager_set_application_setting = db_api_settings.set_application_setting
db_manager_get_application_setting = db_api_settings.get_application_setting

# Episodes (Scheduled)
db_manager_get_schedule_config = db_episodes.get_schedule_config
db_manager_update_schedule_config = db_episodes.update_schedule_config
db_manager_get_latest_scheduled_publish_time = db_episodes.get_latest_scheduled_publish_time
db_manager_record_scheduled_episode = db_episodes.record_scheduled_episode
db_manager_delete_scheduled_episode = db_episodes.delete_scheduled_episode
db_manager_get_episode_by_id = db_episodes.get_episode_by_id
db_manager_update_episode_metadata_in_db = db_episodes.update_episode_metadata_in_db
db_manager_get_episode_details_for_reupload = db_episodes.get_episode_details_for_reupload
db_manager_get_all_scheduled_episodes = db_episodes.get_all_scheduled_episodes

# Jobs (Processing)
db_manager_add_job = db_jobs.add_processing_job # Renamed for submit.py
db_manager_get_job_details = db_jobs.get_job_details
db_manager_update_job_status = db_jobs.update_job_status
db_manager_get_job_status = db_jobs.get_job_status
db_manager_get_all_active_jobs = db_jobs.get_all_active_jobs
db_manager_delete_job = db_jobs.delete_job
db_manager_get_job_history = db_jobs.get_job_history
db_manager_recreate_job_from_existing = db_jobs.recreate_job_from_existing
db_manager_add_job_log = db_jobs.add_job_log
db_manager_get_job_logs = db_jobs.get_job_logs

# Podcasts (Projects)
db_manager_add_podcast_project = db_podcasts.add_podcast_project
db_manager_get_podcast_project = db_podcasts.get_podcast_project
db_manager_get_all_podcast_projects = db_podcasts.get_all_podcast_projects
db_manager_update_podcast_project = db_podcasts.update_podcast_project

# --- Re-export all functions under their simpler names for easy access ---
# This makes it so other modules can call `db_manager.save_api_key()` instead of a longer name.

# API Settings
save_api_key = db_manager_save_api_key
get_api_key = db_manager_get_api_key
set_application_setting = db_manager_set_application_setting
get_application_setting = db_manager_get_application_setting

# Episodes (Scheduled)
get_schedule_config = db_manager_get_schedule_config
update_schedule_config = db_manager_update_schedule_config
get_latest_scheduled_publish_time = db_manager_get_latest_scheduled_publish_time
record_scheduled_episode = db_manager_record_scheduled_episode
delete_scheduled_episode = db_manager_delete_scheduled_episode
get_episode_by_id = db_manager_get_episode_by_id
update_episode_metadata_in_db = db_manager_update_episode_metadata_in_db
get_episode_details_for_reupload = db_manager_get_episode_details_for_reupload
get_all_scheduled_episodes = db_manager_get_all_scheduled_episodes

# Jobs (Processing)
add_job = db_manager_add_job
get_job_details = db_manager_get_job_details
update_job_status = db_manager_update_job_status
get_job_status = db_manager_get_job_status
get_all_active_jobs = db_manager_get_all_active_jobs
delete_job = db_manager_delete_job
get_job_history = db_manager_get_job_history
recreate_job_from_existing = db_manager_recreate_job_from_existing
add_job_log = db_manager_add_job_log
get_job_logs = db_manager_get_job_logs

# Podcasts (Projects)
add_podcast_project = db_manager_add_podcast_project
get_podcast_project = db_manager_get_podcast_project
get_all_podcast_projects = db_manager_get_all_podcast_projects
update_podcast_project = db_manager_update_podcast_project
