s#!/bin/bash

# Podcast Pro MVP Deployment Script
# This script will update your files and deploy to Google Cloud

set -e  # Exit on any error

echo "🚀 Podcast Pro MVP Deployment Script"
echo "======================================"

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Error: Not in a git repository. Please run this from your project root."
    exit 1
fi

echo "📝 Creating backup of current state..."
git stash push -m "Pre-MVP backup $(date)"

echo "🔄 Updating files for MVP deployment..."

# Create requirements.txt
cat > requirements.txt << 'EOF'
# Core Flask and web framework
Flask==2.3.3
gunicorn==21.2.0
Werkzeug==2.3.7

# Database
psycopg2-binary==2.9.7
cloud-sql-python-connector[pg8000]==1.4.0

# Google Cloud services
google-cloud-storage==2.10.0
google-cloud-secret-manager==2.16.4
google-generativeai==0.3.0

# Audio processing
pydub==0.25.1

# External APIs
requests==2.31.0
elevenlabs==0.2.26

# Utility libraries
pytz==2023.3
python-dateutil==2.8.2
EOF

echo "✅ Created requirements.txt"

# Create unified db_manager.py
cat > db_manager.py << 'EOF'
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
EOF

echo "✅ Created unified db_manager.py"

# Update Dockerfile
cat > Dockerfile << 'EOF'
# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set the working directory
WORKDIR /app

# Install system dependencies required for audio processing and PostgreSQL
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libpq-dev \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads processed_output app/static/assets/cover_art

# Expose the port that the app runs on
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD exec gunicorn --bind :${PORT:-8080} --workers 1 --threads 8 --timeout 0 --access-logfile - --error-logfile - wsgi:app
EOF

echo "✅ Updated Dockerfile"

# Update cloudbuild.yaml
cat > cloudbuild.yaml << 'EOF'
# Cloud Build configuration for Podcast Pro
steps:
  # Build the container image
  - name: 'gcr.io/cloud-builders/docker'
    args: [
      'build', 
      '-t', '${_REGION}-docker.pkg.dev/$PROJECT_ID/${_AR_REPO}/${_SERVICE_NAME}:$BUILD_ID',
      '-t', '${_REGION}-docker.pkg.dev/$PROJECT_ID/${_AR_REPO}/${_SERVICE_NAME}:latest',
      '.'
    ]

  # Push the container image to Artifact Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: [
      'push', 
      '--all-tags',
      '${_REGION}-docker.pkg.dev/$PROJECT_ID/${_AR_REPO}/${_SERVICE_NAME}'
    ]

  # Deploy to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - '${_SERVICE_NAME}'
      - '--image=${_REGION}-docker.pkg.dev/$PROJECT_ID/${_AR_REPO}/${_SERVICE_NAME}:$BUILD_ID'
      - '--region=${_REGION}'
      - '--platform=managed'
      - '--allow-unauthenticated'
      - '--service-account=${_RUN_SERVICE_ACCOUNT_NAME}@$PROJECT_ID.iam.gserviceaccount.com'
      - '--add-cloudsql-instances=$PROJECT_ID:${_REGION}:${_SQL_INSTANCE_NAME}'
      - '--set-env-vars=INSTANCE_CONNECTION_NAME=$PROJECT_ID:${_REGION}:${_SQL_INSTANCE_NAME},DB_USER=${_DB_USER},DB_NAME=${_DB_NAME},GCS_BUCKET_NAME=${_GCS_BUCKET}'
      - '--set-secrets=DB_PASS=DB_PASS:latest,FLASK_SECRET_KEY=FLASK_SECRET_KEY:latest'
      - '--memory=2Gi'
      - '--cpu=2'
      - '--timeout=3600'
      - '--concurrency=80'
      - '--min-instances=0'
      - '--max-instances=10'

# Substitution variables
substitutions:
  _REGION: 'us-west1'
  _AR_REPO: 'podcast-pro-images'
  _SERVICE_NAME: 'podcast-pro-backend'
  _SQL_INSTANCE_NAME: 'podcast-pro-db'
  _DB_USER: 'postgres'
  _DB_NAME: 'postgres'
  _GCS_BUCKET: 'podcast-pro-464303-media'
  _RUN_SERVICE_ACCOUNT_NAME: 'podcast-run-sa'

images:
  - '${_REGION}-docker.pkg.dev/$PROJECT_ID/${_AR_REPO}/${_SERVICE_NAME}:$BUILD_ID'
  - '${_REGION}-docker.pkg.dev/$PROJECT_ID/${_AR_REPO}/${_SERVICE_NAME}:latest'

options:
  logging: CLOUD_LOGGING_ONLY
  machineType: 'E2_HIGHCPU_8'
  diskSizeGb: 100

timeout: '1200s'
EOF

echo "✅ Updated cloudbuild.yaml"

# Update app/__init__.py
cat > app/__init__.py << 'EOF'
import os
import logging
from flask import Flask, jsonify
from werkzeug.exceptions import BadRequest

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app(config_class=None):
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024 * 1024  # 1GB
    app.config['GCS_BUCKET'] = os.environ.get('GCS_BUCKET_NAME', 'podcast-pro-464303-media')
    app.config['ALLOWED_EXTENSIONS'] = {'mp3', 'wav', 'm4a'}
    
    # Set up directories
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['UPLOAD_FOLDER'] = os.path.join(basedir, '..', 'uploads')
    app.config['PROCESSED_OUTPUT_FOLDER'] = os.path.join(basedir, '..', 'processed_output')
    
    # Ensure directories exist
    for folder in [app.config['UPLOAD_FOLDER'], app.config['PROCESSED_OUTPUT_FOLDER']]:
        os.makedirs(folder, exist_ok=True)

    # Initialize GCS if available
    try:
        import gcs_utils
        gcs_utils.GCS_BUCKET_NAME = app.config['GCS_BUCKET']
    except ImportError:
        logger.warning("GCS utilities not available. File uploads will be local only.")

    # Health check endpoint
    @app.route('/health')
    def health_check():
        try:
            return jsonify({
                'status': 'healthy',
                'environment': 'cloud' if os.environ.get('INSTANCE_CONNECTION_NAME') else 'local'
            }), 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

    # Register blueprints with error handling
    try:
        from .views.submit import submit_bp
        from .views.admin import admin_bp
        
        app.register_blueprint(submit_bp)
        app.register_blueprint(admin_bp, url_prefix='/admin')
        
    except ImportError as e:
        logger.error(f"Failed to import blueprints: {e}")
        # Create minimal blueprint if imports fail
        from flask import Blueprint, render_template_string
        
        minimal_bp = Blueprint('minimal', __name__)
        
        @minimal_bp.route('/')
        def minimal_home():
            return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head><title>Podcast Automation</title></head>
            <body>
                <h1>Podcast Automation Platform</h1>
                <p>Service is running but some features may be unavailable.</p>
                <p><a href="/health">Health Check</a></p>
            </body>
            </html>
            ''')
        
        app.register_blueprint(minimal_bp)

    # Global error handlers
    @app.errorhandler(BadRequest)
    def handle_bad_request(e):
        logger.error(f"Bad Request: {e.description}")
        return jsonify(error=f"Bad Request: {e.description}"), 400

    @app.errorhandler(500)
    def handle_internal_error(e):
        logger.error(f"Internal Server Error: {e}")
        return jsonify(error="Internal server error occurred"), 500

    return app
EOF

echo "✅ Updated app/__init__.py"

# Create minimal submit view
mkdir -p app/views
cat > app/views/__init__.py << 'EOF'
# Views package
EOF

cat > app/views/submit.py << 'EOF'
import os
import logging
import tempfile
from datetime import datetime
from flask import Blueprint, request, render_template_string, redirect, url_for, flash, current_app, jsonify
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

submit_bp = Blueprint('submit', __name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config.get('ALLOWED_EXTENSIONS', {'mp3', 'wav', 'm4a'})

@submit_bp.route('/')
@submit_bp.route('/submit', methods=['GET', 'POST'])
def submit_job_form():
    if request.method == 'POST':
        try:
            import db_manager
        except ImportError:
            logger.error("Database manager not available")
            flash('Service temporarily unavailable. Please try again later.', 'error')
            return redirect(request.url)

        # Validate file upload
        if 'audio_file' not in request.files:
            flash('No audio file uploaded.', 'error')
            return redirect(request.url)
        
        file = request.files['audio_file']
        if file.filename == '':
            flash('No file selected.', 'error')
            return redirect(request.url)

        # Get form data
        episode_topic = request.form.get('episode_topic')
        episode_number = request.form.get('episode_number')
        ai_intro_text = request.form.get('ai_intro_text', '')

        # Basic validation
        if not episode_topic or not episode_number:
            flash('Episode topic and number are required.', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            unique_filename = f"{timestamp}_{filename}"
            
            # Handle file storage
            try:
                # Try GCS first
                import gcs_utils
                if gcs_utils.GCS_BUCKET_NAME:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}") as temp_file:
                        file.save(temp_file.name)
                        temp_filepath = temp_file.name
                    
                    try:
                        gcs_destination_blob = f"uploads/{unique_filename}"
                        gcs_uri = gcs_utils.upload_file_to_gcs(temp_filepath, gcs_destination_blob)
                        uploaded_path = gcs_uri
                    finally:
                        if os.path.exists(temp_filepath):
                            os.remove(temp_filepath)
                else:
                    # Fall back to local storage
                    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
                    os.makedirs(upload_folder, exist_ok=True)
                    upload_path = os.path.join(upload_folder, unique_filename)
                    file.save(upload_path)
                    uploaded_path = upload_path
                    
            except Exception as e:
                logger.error(f"File upload failed: {e}")
                # Fall back to local storage
                upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
                os.makedirs(upload_folder, exist_ok=True)
                upload_path = os.path.join(upload_folder, unique_filename)
                file.save(upload_path)
                uploaded_path = upload_path

            # Create job in database
            try:
                output_base_filename = f"{timestamp}_{os.path.splitext(filename)[0]}"
                job_base_output_dir = f"processed_output/{output_base_filename}"
                
                job_id = db_manager.add_job(
                    podcast_id=1,
                    episode_topic=episode_topic,
                    episode_number=episode_number,
                    template_path="config/spreaker.json",
                    recording_filename=filename,
                    uploaded_recording_path=uploaded_path,
                    output_base_filename=output_base_filename,
                    job_base_output_dir=job_base_output_dir,
                    ai_intro_text=ai_intro_text
                )
                
                if job_id:
                    flash(f"Job submitted successfully with ID {job_id}!", "success")
                    try:
                        return redirect(url_for('admin.admin_page'))
                    except:
                        return redirect(url_for('submit.submit_job_form'))
                else:
                    flash("Failed to create job in database.", "error")
                    return redirect(request.url)
                    
            except Exception as e:
                logger.error(f"Database error: {e}")
                flash(f"Database error: {e}", "error")
                return redirect(request.url)
        else:
            flash('Invalid file type. Please upload MP3, WAV, or M4A files only.', 'error')
            return redirect(request.url)

    # GET request - show form
    return render_template_string(SUBMIT_FORM_HTML)

# HTML template for the form
SUBMIT_FORM_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Submit Podcast Job</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 40px; background-color: #f8f9fa; color: #212529; line-height: 1.6;
        }
        .container { 
            background-color: #fff; padding: 30px; border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 700px; margin: auto;
        }
        h1, h2 { text-align: center; color: #343a40; margin-bottom: 25px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; font-weight: bold; color: #495057; }
        input[type="text"], input[type="file"], textarea { 
            width: 100%; padding: 10px; border: 1px solid #ced4da; border-radius: 4px;
            box-sizing: border-box; font-size: 16px;
        }
        textarea { resize: vertical; min-height: 100px; }
        button { 
            width: 100%; padding: 12px; background-color: #007bff; color: white;
            border: none; border-radius: 4px; cursor: pointer; font-size: 18px;
            font-weight: bold; transition: background-color 0.3s ease; margin-top: 10px;
        }
        button:hover { background-color: #0056b3; }
        .note { font-size: 0.9em; color: #6c757d; margin-top: 5px; }
        .flash-messages { list-style: none; padding: 0; margin-bottom: 20px; }
        .flash-messages li { padding: 10px; margin-bottom: 10px; border-radius: 4px; }
        .flash-messages .success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .flash-messages .error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .nav-links { text-align: center; margin-bottom: 20px; }
        .nav-links a { margin: 0 10px; color: #007bff; text-decoration: none; }
        .nav-links a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <div class="nav-links">
            <a href="/health">Health Check</a>
            <a href="/admin">Admin Dashboard</a>
        </div>
        
        <h1>🎙️ Submit Podcast Job</h1>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <ul class="flash-messages">
                {% for category, message in messages %}
                    <li class="{{ category }}">{{ message }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        {% endwith %}

        <form method="post" enctype="multipart/form-data">
            <h2>Episode Details</h2>
            
            <div class="form-group">
                <label>Podcast:</label>
                <p><strong>Default Podcast</strong></p>
                <input type="hidden" name="podcast_id" value="1">
            </div>
            
            <div class="form-group">
                <label for="episode_number">Episode Number:</label>
                <input type="text" id="episode_number" name="episode_number" required>
            </div>
            
            <div class="form-group">
                <label for="episode_topic">Episode Topic:</label>
                <textarea id="episode_topic" name="episode_topic" rows="4" required></textarea>
            </div>

            <div class="form-group">
                <label for="audio_file">Upload Audio File:</label>
                <input type="file" id="audio_file" name="audio_file" accept="audio/*" required>
                <div class="note">Supported formats: MP3, WAV, M4A</div>
            </div>

            <div class="form-group">
                <label for="ai_intro_text">AI Intro Text (Optional):</label>
                <textarea id="ai_intro_text" name="ai_intro_text" rows="3"></textarea>
                <div class="note">Text for custom AI-generated intro. Leave blank for default.</div>
            </div>

            <button type="submit">🚀 Submit Processing Job</button>
        </form>
    </div>
</body>
</html>
'''
EOF

echo "✅ Created app/views/submit.py"

# Create minimal admin view
cat > app/views/admin.py << 'EOF'
import logging
from flask import Blueprint, render_template_string, jsonify, redirect, url_for, flash

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/')
def admin_page():
    try:
        import db_manager
        active_jobs = db_manager.get_all_active_jobs()
        job_history = db_manager.get_job_history()
        scheduled_episodes = db_manager.get_all_scheduled_episodes()
    except ImportError:
        logger.error("Database manager not available")
        active_jobs = []
        job_history = []
        scheduled_episodes = []
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        active_jobs = []
        job_history = []
        scheduled_episodes = []

    return render_template_string(ADMIN_HTML, 
                                jobs=active_jobs, 
                                job_history=job_history, 
                                scheduled_episodes=scheduled_episodes)

@admin_bp.route('/job_status/<int:job_id>')
def job_status(job_id):
    try:
        import db_manager
        status = db_manager.get_job_status(job_id)
        if status:
            return jsonify({'status': status})
        else:
            return jsonify({'status': 'not_found'})
    except Exception as e:
        logger.error(f"Error fetching job status: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@admin_bp.route('/delete_job/<int:job_id>', methods=['POST'])
def delete_job(job_id):
    try:
        import db_manager
        if db_manager.delete_job(job_id):
            flash(f"Job ID {job_id} deleted.", "success")
        else:
            flash(f"Failed to delete job ID {job_id}.", "error")
    except Exception as e:
        logger.error(f"Error deleting job: {e}")
        flash(f"Error deleting job: {e}", "error")
    
    return redirect(url_for('admin.admin_page'))

@admin_bp.route('/get_job_logs_api/<int:job_id>')
def get_job_logs_api(job_id):
    try:
        import db_manager
        logs = db_manager.get_job_logs(job_id)
        serialized_logs = []
        for log in logs:
            if isinstance(log, dict):
                serialized_logs.append({
                    'timestamp': str(log.get('timestamp', '')),
                    'message': str(log.get('message', ''))
                })
            else:
                serialized_logs.append({
                    'timestamp': str(log[0]) if len(log) > 0 else '',
                    'message': str(log[1]) if len(log) > 1 else str(log)
                })
        return jsonify(serialized_logs)
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return jsonify({'error': str(e)}), 500

# HTML template for admin page
ADMIN_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Admin Dashboard</title>
    <style>
        body { font-family: sans-serif; margin: 20px; background-color: #f4f4f4; color: #333; }
        .container { background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); max-width: 1200px; margin: auto; }
        h1, h2 { color: #333; border-bottom: 1px solid #eee; padding-bottom: 10px; }
        a { color: #007bff; text-decoration: none; }
        a:hover { text-decoration: underline; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; vertical-align: middle; }
        th { background-color: #e9ecef; }
        .flash-messages { list-style: none; padding: 0; }
        .flash-messages li { padding: 10px; margin-bottom: 10px; border-radius: 4px; }
        .flash-messages .success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .flash-messages .error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .action-button, button { color: white; padding: 5px 10px; margin: 2px; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9em; text-decoration: none; display: inline-block; }
        .delete-button { background-color: #dc3545; }
        .delete-button:hover { background-color: #c82333; }
        .logs-button { background-color: #6c757d; }
        .logs-button:hover { background-color: #5a6268; }
        .log-container { max-height: 300px; overflow-y: auto; background-color: #333; color: #f8f9fa; padding: 10px; border-radius: 4px; font-family: monospace; white-space: pre-wrap; margin-top: 10px; display: none; }
        .nav-links { margin-bottom: 20px; }
        .nav-links a { margin-right: 15px; }
        .status-indicator { padding: 3px 8px; border-radius: 3px; font-size: 0.8em; font-weight: bold; }
        .status-pending { background-color: #fff3cd; color: #856404; }
        .status-processing { background-color: #cce5ff; color: #004085; }
        .status-completed { background-color: #d4edda; color: #155724; }
        .status-failed { background-color: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="container">
        <div class="nav-links">
            <a href="/">🏠 Back to Submit</a>
            <a href="/health">❤️ Health Check</a>
        </div>
        
        <h1>📊 Admin Dashboard</h1>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <ul class="flash-messages">
                {% for category, message in messages %}
                    <li class="{{ category }}">{{ message }}</li>
                {% endfor %}
                </ul>
            {% endif %}
        {% endwith %}

        <h2>🔄 Active Jobs</h2>
        {% if jobs %}
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Status</th>
                        <th>Episode</th>
                        <th>Submitted</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for job in jobs %}
                    <tr>
                        <td>{{ job.id }}</td>
                        <td><span id="status-{{ job.id }}" class="status-indicator status-{{ job.status|lower }}">{{ job.status }}</span></td>
                        <td>{{ job.episode_topic or 'N/A' }} (Ep #{{ job.episode_number or 'N/A' }})</td>
                        <td>{{ job.created_at or 'N/A' }}</td>
                        <td>
                            <button class="logs-button" onclick="toggleLogs({{ job.id }}, this)">📋 View Logs</button>
                            <form method="post" action="/admin/delete_job/{{ job.id }}" style="display:inline;" 
                                  onsubmit="return confirm('Delete job {{ job.id }}?');">
                                <button type="submit" class="delete-button">🗑️ Delete</button>
                            </form>
                        </td>
                    </tr>
                    <tr id="log-row-{{ job.id }}" style="display: none;">
                        <td colspan="5"><div id="log-container-{{ job.id }}" class="log-container"></div></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% else %}
            <p>✨ No active jobs. <a href="/">Submit your first job!</a></p>
        {% endif %}

        <h2 style="margin-top: 40px;">📚 Job History (Last 50)</h2>
        {% if job_history %}
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Status</th>
                        <th>Episode</th>
                        <th>Last Updated</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for job in job_history %}
                    <tr>
                        <td>{{ job.id }}</td>
                        <td><span class="status-indicator status-{{ job.status|lower }}">{{ job.status }}</span></td>
                        <td>{{ job.episode_topic or 'N/A' }} (Ep #{{ job.episode_number or 'N/A' }})</td>
                        <td>{{ job.updated_at or job.created_at or 'N/A' }}</td>
                        <td>
                            <button class="logs-button" onclick="toggleLogs({{ job.id }}, this)">📋 View Logs</button>
                            <form method="post" action="/admin/delete_job/{{ job.id }}" style="display:inline;"
                                  onsubmit="return confirm('Delete job {{ job.id }}?');">
                                <button type="submit" class="delete-button">🗑️ Delete</button>
                            </form>
                        </td>
                    </tr>
                    <tr id="log-row-{{ job.id }}" style="display: none;">
                        <td colspan="5"><div id="log-container-{{ job.id }}" class="log-container"></div></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% else %}
            <p>📝 No job history found.</p>
        {% endif %}

        <h2 style="margin-top: 40px;">📅 Scheduled Episodes</h2>
        {% if scheduled_episodes %}
            <table>
                <thead>
                    <tr><th>ID</th><th>Episode #</th><th>Topic</th><th>Spreaker ID</th><th>Created</th></tr>
                </thead>
                <tbody>
                    {% for episode in scheduled_episodes %}
                    <tr>
                        <td>{{ episode.id }}</td>
                        <td>{{ episode.episode_number }}</td>
                        <td>{{ episode.episode_topic }}</td>
                        <td>{{ episode.spreaker_episode_id or 'N/A' }}</td>
                        <td>{{ episode.created_at or 'N/A' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% else %}
            <p>📻 No scheduled episodes found.</p>
        {% endif %}
    </div>

    <script>
        async function fetchLogs(jobId) {
            const logContainer = document.getElementById(`log-container-${jobId}`);
            logContainer.textContent = 'Loading logs...';
            try {
                const response = await fetch(`/admin/get_job_logs_api/${jobId}`);
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const logs = await response.json();
                if (logs.length > 0) {
                    logContainer.textContent = logs.map(log => `${log.timestamp}: ${log.message}`).join('\\n');
                } else {
                    logContainer.textContent = 'No logs found for this job.';
                }
            } catch (error) {
                console.error('Error fetching logs:', error);
                logContainer.textContent = 'Error loading logs.';
            }
        }

        function toggleLogs(jobId, button) {
            const logRow = document.getElementById(`log-row-${jobId}`);
            if (logRow.style.display === 'none') {
                logRow.style.display = 'table-row';
                button.textContent = '📋 Hide Logs';
                fetchLogs(jobId);
            } else {
                logRow.style.display = 'none';
                button.textContent = '📋 View Logs';
            }
        }

        // Auto-refresh job statuses every 30 seconds
        setInterval(async () => {
            const statusElements = document.querySelectorAll('[id^="status-"]');
            for (const element of statusElements) {
                const jobId = element.id.split('-')[1];
                try {
                    const response = await fetch(`/admin/job_status/${jobId}`);
                    if (response.ok) {
                        const data = await response.json();
                        if (data.status && data.status !== element.textContent) {
                            element.textContent = data.status;
                            element.className = `status-indicator status-${data.status.toLowerCase()}`;
                        }
                    }
                } catch (error) {
                    console.error(`Error updating status for job ${jobId}:`, error);
                }
            }
        }, 30000);
    </script>
</body>
</html>
'''
EOF

echo "✅ Created app/views/admin.py"

echo "🧪 Testing local setup..."

# Quick local test
python3 -c "
try:
    import db_manager
    db_manager.init_db()
    print('✅ Database initialization successful')
except Exception as e:
    print(f'❌ Database test failed: {e}')
"

echo ""
echo "📝 Files updated successfully!"
echo "🔍 Summary of changes:"
echo "   • requirements.txt - Added all necessary dependencies"
echo "   • db_manager.py - Unified SQLite/PostgreSQL database manager"
echo "   • Dockerfile - Fixed for Cloud Run deployment"
echo "   • cloudbuild.yaml - Improved build configuration"
echo "   • app/__init__.py - Added health checks and error handling"
echo "   • app/views/submit.py - Minimal job submission form"
echo "   • app/views/admin.py - Minimal admin dashboard"
echo ""
echo "🚀 Ready to deploy! Next steps:"
echo "   1. git add ."
echo "   2. git commit -m 'MVP deployment fixes'"
echo "   3. git push origin main"
echo ""
echo "🔗 After deployment, check:"
echo "   • Health: [YOUR_URL]/health"
echo "   • Submit: [YOUR_URL]/"
echo "   • Admin: [YOUR_URL]/admin"
echo ""

# Function to get service URL after deployment
echo "💡 To get your service URL after deployment:"
echo "   gcloud run services describe podcast-pro-backend --region=us-west1 --format='value(status.url)'"
echo ""
echo "🎉 Let's get this thing live!"
EOF

echo "✅ Created deployment script!"

chmod +x deploy_mvp.sh

echo ""
echo "🎯 **READY TO DEPLOY!**"
echo ""
echo "Just run this single command in your project directory:"
echo ""
echo "   ./deploy_mvp.sh"
echo ""
echo "This script will:"
echo "  ✅ Update all necessary files"
echo "  ✅ Test the database setup locally"
echo "  ✅ Give you the exact git commands to run"
echo "  ✅ Tell you how to check if deployment worked"
echo ""
echo "After running the script, you'll just need to:"
echo "  1. Run the git commands it shows you"
echo "  2. Watch Cloud Build do its magic"
echo "  3. Visit your live URL and see it working!"
echo ""
echo "Ready to make this happen? 🚀"