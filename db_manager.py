import os
import logging
from datetime import datetime
from contextlib import contextmanager
import json # Added for explicit JSON parsing
from google.oauth2 import service_account # Added for explicit credentials

logger = logging.getLogger(__name__)

# Configure logging to show INFO level messages and above
logging.basicConfig(level=logging.INFO)

# Check if running in cloud environment
IS_CLOUD_ENV = bool(os.environ.get('INSTANCE_CONNECTION_NAME'))

if IS_CLOUD_ENV:
    # Cloud SQL PostgreSQL setup
    import pg8000
    from google.cloud.sql.connector import Connector, IPTypes # Added IPTypes for completeness, though not used in connect()

    INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASS = os.environ.get("DB_PASS")
    DB_NAME = os.environ.get("DB_NAME", "postgres")
    
    # Global variables for connector and credentials to ensure they are initialized once
    _connector = None
    _credentials = None
    
    def _initialize_cloud_sql_connector_and_credentials():
        """
        Initializes the Cloud SQL Connector and Google Cloud credentials.
        This function explicitly loads credentials from the file path provided by
        GOOGLE_APPLICATION_CREDENTIALS environment variable.
        """
        global _connector, _credentials

        # Log the path where GOOGLE_APPLICATION_CREDENTIALS is expected to be
        gac_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        logger.info(f"Attempting to load credentials from GOOGLE_APPLICATION_CREDENTIALS path: {gac_path}")

        if not gac_path:
            logger.error("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set. Cannot connect to Cloud SQL.")
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable is required for Cloud SQL connection.")
        
        # Explicitly read the JSON content from the file path
        try:
            with open(gac_path, 'r') as f:
                credentials_info = json.load(f)
            
            # Create credentials object from the loaded JSON info
            _credentials = service_account.Credentials.from_service_account_info(credentials_info)
            logger.info("Successfully loaded credentials from GOOGLE_APPLICATION_CREDENTIALS file.")
        except FileNotFoundError:
            logger.error(f"Credentials file not found at path: {gac_path}. Please ensure the secret is correctly mounted.")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from credentials file at {gac_path}: {e}. Ensure the secret content is valid JSON.")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading credentials from {gac_path}: {e}")
            raise

        # Initialize the connector with the explicitly loaded credentials
        _connector = Connector(credentials=_credentials)
        logger.info("Cloud SQL Connector initialized with explicit credentials.")

    def get_db_connection():
        """Establishes and returns a new database connection."""
        global _connector, _credentials
        
        # Initialize connector and credentials if they haven't been already
        if _connector is None:
            _initialize_cloud_sql_connector_and_credentials()
        
        logger.info(f"Connecting to Cloud SQL instance: {INSTANCE_CONNECTION_NAME} as user: {DB_USER}")
        conn = _connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user=DB_USER,
            password=DB_PASS, # Ensure DB_PASS is correctly set in Cloud Run secrets
            db=DB_NAME,
            # ip_type=IPTypes.PUBLIC # Optional: Use this if connecting via public IP, otherwise remove
        )
        logger.info("Successfully connected to database.")
        return conn
        
    @contextmanager
    def managed_db_connection():
        """Context manager for PostgreSQL connections"""
        conn = None # Initialize conn to None
        try:
            conn = get_db_connection()
            yield conn
            conn.commit()
        except Exception as e:
            if conn: # Only attempt rollback if connection was established
                conn.rollback()
            logger.error(f"Database error during transaction: {e}")
            raise
        finally:
            if conn: # Only attempt close if connection was established
                conn.close()
                logger.info("Database connection closed.")
            
else:
    # Local SQLite setup
    import sqlite3
    
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    DATABASE_PATH = os.path.join(_SCRIPT_DIR, "podcast_automation.db")
    
    def get_db_connection():
        """Establishes and returns a new database connection."""
        logger.info(f"Connecting to local SQLite database: {DATABASE_PATH}")
        conn = sqlite3.connect(DATABASE_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        logger.info("Successfully connected to SQLite database.")
        return conn
    
    @contextmanager
    def managed_db_connection():
        """Context manager for SQLite connections"""
        conn = None # Initialize conn to None
        try:
            conn = get_db_connection()
            yield conn
            conn.commit()
        except Exception as e:
            if conn: # Only attempt rollback if connection was established
                conn.rollback()
            logger.error(f"Database error during transaction: {e}")
            raise
        finally:
            if conn: # Only attempt close if connection was established
                conn.close()
                logger.info("SQLite connection closed.")

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
    logger.info("Attempting to initialize PostgreSQL schema.")
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
        logger.info("Jobs table checked/created.")
        
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
        logger.info("Job logs table checked/created.")
        
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
        logger.info("Episodes table checked/created.")
        
        conn.commit()
        logger.info("PostgreSQL schema initialization committed.")

def _init_sqlite_db():
    """Initialize SQLite database schema."""
    logger.info("Attempting to initialize SQLite schema.")
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
        logger.info("Jobs table checked/created.")
        
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
        logger.info("Job logs table checked/created.")
        
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
        logger.info("Episodes table checked/created.")
        
        conn.commit()
        logger.info("SQLite schema initialization committed.")

def create_job(job_data):
    """Create a new job in the database"""
    logger.info(f"Attempting to create job: {job_data.get('title')}")
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
            logger.info(f"Job created with ID: {job_id}")
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
            job_id = cursor.lastrowid
            logger.info(f"Job created with ID: {job_id}")
            return job_id

def get_all_jobs():
    """Get all jobs from the database"""
    logger.info("Fetching all jobs.")
    with managed_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        jobs = [dict(zip(columns, row)) for row in rows]
        logger.info(f"Fetched {len(jobs)} jobs.")
        return jobs

def get_job_logs(job_id):
    """Get logs for a specific job"""
    logger.info(f"Fetching logs for job ID: {job_id}")
    with managed_db_connection() as conn:
        cursor = conn.cursor()
        if IS_CLOUD_ENV:
            cursor.execute("SELECT * FROM job_logs WHERE job_id = %s ORDER BY timestamp", (job_id,))
        else:
            cursor.execute("SELECT * FROM job_logs WHERE job_id = ? ORDER BY timestamp", (job_id,))
        
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        logs = [dict(zip(columns, row)) for row in rows]
        logger.info(f"Fetched {len(logs)} logs for job ID: {job_id}")
        return logs

def update_job_status(job_id, status):
    """Update job status"""
    logger.info(f"Updating status for job ID {job_id} to: {status}")
    with managed_db_connection() as conn:
        cursor = conn.cursor()
        if IS_CLOUD_ENV:
            cursor.execute("UPDATE jobs SET status = %s, updated_at = NOW() WHERE id = %s", (status, job_id))
        else:
            cursor.execute("UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, job_id))
        logger.info(f"Status updated for job ID: {job_id}")

def delete_job(job_id):
    """Delete a job and its logs"""
    logger.info(f"Deleting job with ID: {job_id}")
    with managed_db_connection() as conn:
        cursor = conn.cursor()
        if IS_CLOUD_ENV:
            cursor.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
        else:
            cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        logger.info(f"Job with ID {job_id} deleted.")

def get_all_episodes():
    """Get all episodes from the database"""
    logger.info("Fetching all episodes.")
    with managed_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM episodes ORDER BY created_at DESC")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        episodes = [dict(zip(columns, row)) for row in rows]
        logger.info(f"Fetched {len(episodes)} episodes.")
        return episodes

# Stub functions for compatibility
def add_job_log(job_id, level, message):
    """Add a log entry for a job"""
    logger.info(f"Adding log for job ID {job_id}: [{level}] {message}")
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
        logger.info(f"Log added for job ID: {job_id}")

# Import db_api_settings module and inject dependencies
# This part assumes db_api_settings.py exists and needs these injected.
# If not, this try-except block might be removed.
try:
    import db_api_settings
    db_api_settings.managed_db_connection = managed_db_connection
    db_api_settings.IS_CLOUD_ENV = IS_CLOUD_ENV
    logger.info("Injected database dependencies into db_api_settings module.")
except ImportError:
    logger.warning("db_api_settings module not found. Skipping dependency injection.")