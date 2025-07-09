import os
import logging
import sqlite3
from datetime import datetime
from contextlib import contextmanager

# Import the new modules
import db_api_settings
import db_podcasts
import db_jobs
import db_episodes

logger = logging.getLogger(__name__)

# Check if running in cloud environment
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
else:
    # Local SQLite setup
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_PATH = os.path.join(_SCRIPT_DIR, "podcast_automation.db")
    
    def get_db_connection():
        """Establishes and returns a new database connection."""
        conn = sqlite3.connect(DATABASE_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

@contextmanager
def managed_db_connection():
    """Context manager for database connections"""
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

def _init_postgresql_db():
    """Initialize PostgreSQL database schema"""
    with managed_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_jobs (
                    id SERIAL PRIMARY KEY,
                    user_email VARCHAR(255),
                    source_file_path TEXT,
                    status VARCHAR(50) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

def _init_sqlite_db():
    """Initialize SQLite database schema"""
    with managed_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT,
                source_file_path TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
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

def create_job(job_data):
    """Create a new job in the database"""
    if IS_CLOUD_ENV:
        # PostgreSQL version
        insert_sql = """
        INSERT INTO jobs (job_type, title, description, status, priority, file_path)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
        """
        with managed_db_connection() as conn, conn.cursor() as cursor:
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
            cursor = conn.execute(insert_sql, (
                job_data['job_type'],
                job_data['title'],
                job_data['description'],
                job_data['status'],
                job_data['priority'],
                job_data.get('file_path')
            ))
            return cursor.lastrowid

def get_job(job_id):
    """Get a job by ID"""
    if IS_CLOUD_ENV:
        select_sql = "SELECT * FROM jobs WHERE id = %s"
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute(select_sql, (job_id,))
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
    else:
        select_sql = "SELECT * FROM jobs WHERE id = ?"
        with managed_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(select_sql, (job_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
    return None

def get_all_jobs():
    """Get all jobs ordered by created_at DESC"""
    if IS_CLOUD_ENV:
        select_sql = "SELECT * FROM jobs ORDER BY created_at DESC"
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute(select_sql)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    else:
        select_sql = "SELECT * FROM jobs ORDER BY created_at DESC"
        with managed_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(select_sql)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

def update_job_status(job_id, status):
    """Update job status"""
    if IS_CLOUD_ENV:
        update_sql = """
        UPDATE jobs 
        SET status = %s, updated_at = CURRENT_TIMESTAMP 
        WHERE id = %s
        """
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute(update_sql, (status, job_id))
    else:
        update_sql = """
        UPDATE jobs 
        SET status = ?, updated_at = CURRENT_TIMESTAMP 
        WHERE id = ?
        """
        with managed_db_connection() as conn:
            conn.execute(update_sql, (status, job_id))

def save_job_result(job_id, result_data):
    """Save job processing results"""
    if IS_CLOUD_ENV:
        import json
        insert_sql = """
        INSERT INTO job_results (job_id, result_data)
        VALUES (%s, %s)
        """
        with managed_db_connection() as conn, conn.cursor() as cursor:
            cursor.execute(insert_sql, (job_id, json.dumps(result_data)))
    else:
        import json
        insert_sql = """
        INSERT INTO job_results (job_id, result_data)
        VALUES (?, ?)
        """
        with managed_db_connection() as conn:
            conn.execute(insert_sql, (job_id, json.dumps(result_data)))
