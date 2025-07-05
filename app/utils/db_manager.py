"""
Manages SQLite database operations for scheduled episodes.
"""
import os
import sqlite3
import logging
import sys
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import re

# Import the new modules
import db_api_settings
import db_podcasts
import db_jobs
import db_episodes

logger = logging.getLogger(__name__)

# Construct an absolute path to the database file, assuming it's in the same directory as db_manager.py
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(_SCRIPT_DIR, "podcast_automation.db")

def get_db_connection() -> sqlite3.Connection:
    """Establishes and returns a new database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON") # Enable foreign key support
    return conn

# Pass the connection getter to the new modules
db_api_settings.get_db_connection = get_db_connection
db_podcasts.get_db_connection = get_db_connection
db_jobs.get_db_connection = get_db_connection
db_episodes.get_db_connection = get_db_connection

def init_db():
    """Initializes the SQLite database and creates tables if they don't exist."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_number TEXT,
                episode_topic TEXT, -- Renamed from movie_title for generality
                spreaker_episode_id TEXT,
                processed_mp3_path TEXT,
                poster_path TEXT,               -- New: Path to the poster image
                show_notes_path TEXT,           -- New: Path to the show notes file
                publish_at_utc_iso TEXT UNIQUE, -- Ensures only one episode per exact publish slot
                tags TEXT, -- Comma-separated list of tags
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Updated processing_jobs table schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, -- Job ID
                template_path TEXT NOT NULL,
                recording_filename TEXT NOT NULL,
                uploaded_recording_path TEXT NOT NULL,
                output_base_filename TEXT NOT NULL,
                status TEXT DEFAULT 'pending', -- e.g., pending, processing, completed, failed
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ai_intro_text TEXT, -- AI intro text for the episode
                remove_fillers BOOLEAN,
                intern_command_enabled BOOLEAN,
                intern_command_keyword TEXT, -- Default 'intern'
                stop_word_detection_enabled BOOLEAN,
                episode_number TEXT, -- User-provided episode identifier for the job
                episode_topic TEXT, -- User-provided episode topic/title for the job
                season_number TEXT, -- New: User-provided season number
                remove_pauses BOOLEAN, -- New: Override template setting
                generate_transcript BOOLEAN, -- New: Override template setting
                generate_show_notes BOOLEAN, -- New: Override template setting
                use_gemini_for_summary BOOLEAN, -- New: Override template setting
                download_poster BOOLEAN, -- New: Override template setting
                min_pause_duration_sec REAL, -- New: Override template setting
                custom_filler_words_csv TEXT, -- New: Override template setting
                job_base_output_dir TEXT, -- New: Base directory for this job's output files
                podcast_id INTEGER, -- New: Foreign key to the podcasts table
                
                -- NEW: Commercial Break Settings
                commercial_breaks_enabled BOOLEAN DEFAULT 0,
                commercial_breaks_count INTEGER DEFAULT 1,
                commercial_breaks_min_duration_between_sec REAL DEFAULT 300.0,
                commercial_breaks_max_duration_between_sec REAL DEFAULT 600.0,
                commercial_breaks_min_silence_ms INTEGER DEFAULT 1000,
                commercial_breaks_cue_phrases TEXT, -- Comma-separated
                commercial_breaks_audio_keys TEXT, -- Comma-separated keys from audio_files
                FOREIGN KEY (podcast_id) REFERENCES podcasts(id) ON DELETE SET NULL -- If podcast is deleted, set job's podcast_id to NULL
            )
        """)
        # New table for job-specific logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                log_level TEXT NOT NULL,
                message TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES processing_jobs (id) ON DELETE CASCADE
            )
        ''')
        # New table for scheduling configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedule_config (
                id INTEGER PRIMARY KEY DEFAULT 1, -- Only one row for now
                schedule_type TEXT, -- 'weekly' or 'monthly', to be set by user/app
                times_per_period INTEGER, -- e.g., 3 times per week, to be set by user/app
                days_of_week TEXT, -- Comma-separated: 0=Mon, 1=Tue, ..., 6=Sun, to be set by user/app
                -- For monthly: days_of_month TEXT (e.g., '1,15') - Not implemented in this iteration
                publish_time_local TEXT, -- HH:MM in user's local podcast timezone, to be set by user/app
                podcast_timezone TEXT DEFAULT 'America/Los_Angeles' -- New: Timezone for scheduling
            )
        """)
        # Ensure a default schedule config row exists
        cursor.execute("""
            INSERT OR IGNORE INTO schedule_config (id) VALUES (1)
        """)
        # New table for API Keys
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                service_name TEXT PRIMARY KEY,
                api_key_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # New table for global application settings (e.g., enabling/disabling integrations)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS application_settings (
                setting_name TEXT PRIMARY KEY,
                setting_value TEXT,           -- 'true'/'false' or other string values
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Initialize default settings if they don't exist
        db_api_settings._initialize_default_app_settings(cursor)

        # New table for Podcasts/Projects
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS podcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE,
                author TEXT,
                description TEXT,
                default_cover_art_path TEXT, -- Path to a default cover art for this podcast
                default_template_path TEXT,  -- Path to a default template for this podcast
                default_spreaker_show_id TEXT, -- Podcast-specific Spreaker Show ID (e.g., for Spreaker integration)
                default_publish_timezone TEXT DEFAULT 'America/Los_Angeles', -- For publish_time_local
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        logger.info(f"Database initialized/checked at {DATABASE_PATH}")
    except sqlite3.Error as e:
        logger.error(f"Database error during initialization: {e}")
    finally:
        if conn:
            conn.close()

# Expose functions from the new modules via db_manager
# API Keys & Application Settings
save_api_key = db_api_settings.save_api_key
get_api_key = db_api_settings.get_api_key
set_application_setting = db_api_settings.set_application_setting
get_application_setting = db_api_settings.get_application_setting

# Podcast Project Management
add_podcast_project = db_podcasts.add_podcast_project
get_podcast_project = db_podcasts.get_podcast_project
get_all_podcast_projects = db_podcasts.get_all_podcast_projects
update_podcast_project = db_podcasts.update_podcast_project

# Job Processing Management
add_processing_job = db_jobs.add_processing_job
get_job_details = db_jobs.get_job_details
update_job_status = db_jobs.update_job_status
get_job_status = db_jobs.get_job_status
get_all_active_jobs = db_jobs.get_all_active_jobs
delete_job = db_jobs.delete_job
get_job_history = db_jobs.get_job_history
recreate_job_from_existing = db_jobs.recreate_job_from_existing

# Job Logs
add_job_log = db_jobs.add_job_log
get_job_logs = db_jobs.get_job_logs

# Scheduled Episodes Management
record_scheduled_episode = db_episodes.record_scheduled_episode
delete_scheduled_episode = db_episodes.delete_scheduled_episode
get_all_scheduled_episodes = db_episodes.get_all_scheduled_episodes
get_latest_scheduled_publish_time = db_episodes.get_latest_scheduled_publish_time
update_episode_metadata_in_db = db_episodes.update_episode_metadata_in_db
get_episode_details_for_reupload = db_episodes.get_episode_details_for_reupload

# Schedule Configuration
get_schedule_config = db_episodes.get_schedule_config
update_schedule_config = db_episodes.update_schedule_config
