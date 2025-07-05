"""
Unified database manager supporting both local SQLite and Cloud SQL PostgreSQL
"""
import os
import logging
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Check if we're in a cloud environment
IS_CLOUD_ENV = bool(os.environ.get('INSTANCE_CONNECTION_NAME'))

if IS_CLOUD_ENV:
    # Cloud SQL PostgreSQL setup
    import psycopg2
    import psycopg2.extras
    from google.cloud.sql.connector import Connector
    
    INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASS = os.environ.get("DB_PASS")
    DB_NAME = os.environ.get("DB_NAME", "postgres")
    
    connector = None
    
    def get_db_connection():
        """Establishes a connection to Cloud SQL PostgreSQL."""
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
        """Provides a database connection within a context."""
        conn = get_db_connection()
        try:
            yield conn
        finally:
            if conn:
                conn.close()
                
else:
    # Local SQLite setup
    import sqlite3
    
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_PATH = os.path.join(_SCRIPT_DIR, "podcast_automation.db")
    
    def get_db_connection():
        """Establishes and returns a new SQLite database connection."""
        conn = sqlite3.connect(DATABASE_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    
    @contextmanager
    def managed_db_connection():
        """Provides a SQLite database connection within a context."""
        conn = get_db_connection()
        try:
            yield conn
        finally:
            if conn:
                conn.close()

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    try:
        if IS_CLOUD_ENV:
            _init_postgresql_db()
        else:
            _init_sqlite_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        raise

def _init_postgresql_db():
    """Initialize PostgreSQL database schema."""
    with managed_db_connection() as conn, conn.cursor() as cursor:
        # Processing jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_jobs (
                id SERIAL PRIMARY KEY,
                podcast_id INTEGER DEFAULT 1,
                template_path TEXT,
                recording_filename TEXT,
                uploaded_recording_path TEXT,
                output_base_filename TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                episode_number TEXT,
                episode_topic TEXT,
                ai_intro_text TEXT,
                job_base_output_dir TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        
        # Job logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_logs (
                id SERIAL PRIMARY KEY,
                job_id INTEGER NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
                timestamp TIMESTAMPTZ DEFAULT NOW(),
                log_level TEXT NOT NULL,
                message TEXT NOT NULL
            )
        """)
        
        # Episodes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id SERIAL PRIMARY KEY,
                episode_number TEXT,
                episode_topic TEXT,
                spreaker_episode_id TEXT UNIQUE,
                processed_mp3_path TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        
        conn.commit()

def _init_sqlite_db():
    """Initialize SQLite database schema."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Processing jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                podcast_id INTEGER DEFAULT 1,
                template_path TEXT,
                recording_filename TEXT,
                uploaded_recording_path TEXT,
                output_base_filename TEXT,
                status TEXT DEFAULT 'pending',
                episode_number TEXT,
                episode_topic TEXT,
                ai_intro_text TEXT,
                job_base_output_dir TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Job logs table
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
        
        # Episodes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_number TEXT,
                episode_topic TEXT,
                spreaker_episode_id TEXT,
                processed_mp3_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        
    finally:
        if conn:
            conn.close()

# Simplified function implementations
def add_job(podcast_id: int, episode_topic: str, episode_number: str, 
           template_path: str, recording_filename: str, uploaded_recording_path: str,
           output_base_filename: str, job_base_output_dir: str, ai_intro_text: str = None) -> Optional[int]:
    """Adds a new processing job."""
    try:
        if IS_CLOUD_ENV:
            with managed_db_connection() as conn, conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO processing_jobs (
                        podcast_id, episode_topic, episode_number, template_path, 
                        recording_filename, uploaded_recording_path, output_base_filename,
                        job_base_output_dir, ai_intro_text, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (podcast_id, episode_topic, episode_number, template_path,
                      recording_filename, uploaded_recording_path, output_base_filename,
                      job_base_output_dir, ai_intro_text, 'pending'))
                job_id = cursor.fetchone()[0]
                conn.commit()
                return job_id
        else:
            with managed_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO processing_jobs (
                        podcast_id, episode_topic, episode_number, template_path,
                        recording_filename, uploaded_recording_path, output_base_filename,
                        job_base_output_dir, ai_intro_text, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (podcast_id, episode_topic, episode_number, template_path,
                      recording_filename, uploaded_recording_path, output_base_filename,
                      job_base_output_dir, ai_intro_text, 'pending'))
                job_id = cursor.lastrowid
                conn.commit()
                return job_id
    except Exception as e:
        logger.error(f"Error adding job: {e}")
        return None

def get_all_active_jobs() -> List[Dict[str, Any]]:
    """Fetches all active jobs."""
    jobs = []
    try:
        if IS_CLOUD_ENV:
            with managed_db_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM processing_jobs 
                    WHERE status IN ('pending', 'processing') 
                    ORDER BY created_at ASC
                """)
                jobs = [dict(row) for row in cursor.fetchall()]
        else:
            with managed_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM processing_jobs 
                    WHERE status IN ('pending', 'processing') 
                    ORDER BY created_at ASC
                """)
                jobs = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching active jobs: {e}")
    return jobs

def get_job_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetches job history."""
    jobs = []
    try:
        if IS_CLOUD_ENV:
            with managed_db_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM processing_jobs
                    WHERE status NOT IN ('pending', 'processing')
                    ORDER BY updated_at DESC NULLS LAST, created_at DESC
                    LIMIT %s
                """, (limit,))
                jobs = [dict(row) for row in cursor.fetchall()]
        else:
            with managed_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM processing_jobs
                    WHERE status NOT IN ('pending', 'processing')
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT ?
                """, (limit,))
                jobs = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching job history: {e}")
    return jobs

def get_all_scheduled_episodes() -> List[Dict[str, Any]]:
    """Fetches all scheduled episodes."""
    episodes = []
    try:
        if IS_CLOUD_ENV:
            with managed_db_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT * FROM episodes ORDER BY created_at DESC")
                episodes = [dict(row) for row in cursor.fetchall()]
        else:
            with managed_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM episodes ORDER BY created_at DESC")
                episodes = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching scheduled episodes: {e}")
    return episodes

def delete_job(job_id: int) -> bool:
    """Deletes a job."""
    try:
        if IS_CLOUD_ENV:
            with managed_db_connection() as conn, conn.cursor() as cursor:
                cursor.execute("DELETE FROM processing_jobs WHERE id = %s", (job_id,))
                conn.commit()
        else:
            with managed_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM processing_jobs WHERE id = ?", (job_id,))
                conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error deleting job: {e}")
        return False

def get_job_status(job_id: int) -> Optional[str]:
    """Gets job status."""
    try:
        if IS_CLOUD_ENV:
            with managed_db_connection() as conn, conn.cursor() as cursor:
                cursor.execute("SELECT status FROM processing_jobs WHERE id = %s", (job_id,))
                row = cursor.fetchone()
                return row[0] if row else None
        else:
            with managed_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT status FROM processing_jobs WHERE id = ?", (job_id,))
                row = cursor.fetchone()
                return row[0] if row else None
    except Exception as e:
        logger.error(f"Error fetching job status: {e}")
        return None

def add_job_log(job_id: int, log_level: str, message: str):
    """Adds a log entry."""
    try:
        if IS_CLOUD_ENV:
            with managed_db_connection() as conn, conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO job_logs (job_id, log_level, message) 
                    VALUES (%s, %s, %s)
                """, (job_id, log_level, message))
                conn.commit()
        else:
            with managed_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO job_logs (job_id, log_level, message) 
                    VALUES (?, ?, ?)
                """, (job_id, log_level, message))
                conn.commit()
    except Exception as e:
        logger.error(f"Error adding job log: {e}")

def get_job_logs(job_id: int) -> List[Dict[str, Any]]:
    """Gets job logs."""
    logs = []
    try:
        if IS_CLOUD_ENV:
            with managed_db_connection() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT timestamp, log_level, message FROM job_logs 
                    WHERE job_id = %s ORDER BY timestamp ASC
                """, (job_id,))
                logs = [dict(row) for row in cursor.fetchall()]
        else:
            with managed_db_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT timestamp, log_level, message FROM job_logs 
                    WHERE job_id = ? ORDER BY timestamp ASC
                """, (job_id,))
                logs = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching job logs: {e}")
    return logs
