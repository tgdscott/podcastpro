import os
import logging
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Check if running in cloud environment
IS_CLOUD_ENV = bool(os.environ.get('INSTANCE_CONNECTION_NAME'))

if IS_CLOUD_ENV:
    # Cloud SQL PostgreSQL setup
    import pg8000
    from google.cloud.sql.connector import Connector
    
    INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASS = os.environ.get("DB_PASS")
    DB_NAME = os.environ.get("DB_NAME", "postgres")
    
    connector = None
    
    def get_db_connection():
        """Establishes and returns a new database connection."""
        global connector
        if connector is None:
            connector = Connector()
        
        conn = connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user=DB_USER,
            password=DB_PASS,
            db=DB_NAME,
        )
        return conn
        
    @contextmanager
    def managed_db_connection():
        """Context manager for PostgreSQL connections"""
        conn = get_db_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
            
else:
    # Local SQLite setup
    import sqlite3
    
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_PATH = os.path.join(_SCRIPT_DIR, "podcast_automation.db")
    
    def get_db_connection():
        """Establishes and returns a new database connection."""
        conn = sqlite3.connect(DATABASE_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    
    @contextmanager
    def managed_db_connection():
        """Context manager for SQLite connections"""
        conn = get_db_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

def init_db():
    """Initialize the database (called on app startup)"""
    try:
        logger.info("Initializing database schema...")
        if IS_CLOUD_ENV:
            _init_postgresql_db()
        else:
            _init_sqlite_db()
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {repr(e)}")
        raise

def _init_postgresql_db():
    """Initialize PostgreSQL database schema."""
    with managed_db_connection() as conn:
        cursor = conn.cursor()
        
        # Jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                job_type VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                priority INTEGER DEFAULT 5,
                file_path TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        
        # Job logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_logs (
                id SERIAL PRIMARY KEY,
                job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                timestamp TIMESTAMPTZ DEFAULT NOW(),
                log_level VARCHAR(20) NOT NULL,
                message TEXT NOT NULL
            )
        """)
        
        # Episodes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id SERIAL PRIMARY KEY,
                episode_number VARCHAR(20),
                episode_topic TEXT,
                spreaker_episode_id VARCHAR(100) UNIQUE,
                processed_mp3_path TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        
        conn.commit()

def _init_sqlite_db():
    """Initialize SQLite database schema."""
    with managed_db_connection() as conn:
        cursor = conn.cursor()
        
        # Jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                priority INTEGER DEFAULT 5,
                file_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Job logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                log_level TEXT NOT NULL,
                message TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            )
        """)
        
        # Episodes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_number TEXT,
                episode_topic TEXT,
                spreaker_episode_id TEXT UNIQUE,
                processed_mp3_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()

def create_job(job_data):
    """Create a new job in the database"""
    if IS_CLOUD_ENV:
        # PostgreSQL version
        insert_sql = """
        INSERT INTO jobs (job_type, title, description, status, priority, file_path)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
        """
        with managed_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(insert_sql, (
                job_data['job_type'],
                job_data['title'],
                job_data['description'],
                job_data['status'],
                job_data['priority'],
                job_data.get('file_path')
            ))
            job_id = cursor.fetchone()[0]
            return job_id
    else:
        # SQLite version
        insert_sql = """
        INSERT INTO jobs (job_type, title, description, status, priority, file_path)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        with managed_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(insert_sql, (
                job_data['job_type'],
                job_data['title'],
                job_data['description'],
                job_data['status'],
                job_data['priority'],
                job_data.get('file_path')
            ))
            return cursor.lastrowid

def get_all_jobs():
    """Get all jobs from the database"""
    with managed_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

def get_job_logs(job_id):
    """Get logs for a specific job"""
    with managed_db_connection() as conn:
        cursor = conn.cursor()
        if IS_CLOUD_ENV:
            cursor.execute("SELECT * FROM job_logs WHERE job_id = %s ORDER BY timestamp", (job_id,))
        else:
            cursor.execute("SELECT * FROM job_logs WHERE job_id = ? ORDER BY timestamp", (job_id,))
        
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

def update_job_status(job_id, status):
    """Update job status"""
    with managed_db_connection() as conn:
        cursor = conn.cursor()
        if IS_CLOUD_ENV:
            cursor.execute("UPDATE jobs SET status = %s, updated_at = NOW() WHERE id = %s", (status, job_id))
        else:
            cursor.execute("UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, job_id))

def delete_job(job_id):
    """Delete a job and its logs"""
    with managed_db_connection() as conn:
        cursor = conn.cursor()
        if IS_CLOUD_ENV:
            cursor.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
        else:
            cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

def get_all_episodes():
    """Get all episodes from the database"""
    with managed_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM episodes ORDER BY created_at DESC")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

# Stub functions for compatibility
def add_job_log(job_id, level, message):
    """Add a log entry for a job"""
    with managed_db_connection() as conn:
        cursor = conn.cursor()
        if IS_CLOUD_ENV:
            cursor.execute(
                "INSERT INTO job_logs (job_id, log_level, message) VALUES (%s, %s, %s)",
                (job_id, level, message)
            )
        else:
            cursor.execute(
                "INSERT INTO job_logs (job_id, log_level, message) VALUES (?, ?, ?)",
                (job_id, level, message)
            )

# Import db_api_settings module and inject dependencies
try:
    import db_api_settings
    db_api_settings.managed_db_connection = managed_db_connection
    db_api_settings.IS_CLOUD_ENV = IS_CLOUD_ENV
except ImportError:
    logger.warning("db_api_settings module not found")
