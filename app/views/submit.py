import os
import logging
from flask import Blueprint, request, jsonify, render_template_string
from werkzeug.utils import secure_filename
import db_manager

logger = logging.getLogger(__name__)

submit_bp = Blueprint('submit', __name__)

# Simple HTML form template
SUBMIT_FORM = """
<!DOCTYPE html>
<html>
<head>
    <title>Podcast Pro - Submit Job</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, textarea, select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        button { background-color: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background-color: #0056b3; }
    </style>
</head>
<body>
    <h1>Podcast Pro - Submit Job</h1>
    <form method="POST" enctype="multipart/form-data">
        <div class="form-group">
            <label for="job_type">Job Type:</label>
            <select id="job_type" name="job_type" required>
                <option value="">Select job type</option>
                <option value="audio_processing">Audio Processing</option>
                <option value="podcast_creation">Podcast Creation</option>
                <option value="transcription">Transcription</option>
            </select>
        </div>
        
        <div class="form-group">
            <label for="title">Title:</label>
            <input type="text" id="title" name="title" required>
        </div>
        
        <div class="form-group">
            <label for="description">Description:</label>
            <textarea id="description" name="description" rows="4"></textarea>
        </div>
        
        <div class="form-group">
            <label for="file">Upload File (optional):</label>
            <input type="file" id="file" name="file" accept=".mp3,.wav,.m4a,.pdf,.txt">
        </div>
        
        <div class="form-group">
            <label for="priority">Priority:</label>
            <select id="priority" name="priority">
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="low">Low</option>
            </select>
        </div>
        
        <button type="submit">Submit Job</button>
    </form>
    
    <p><a href="/admin">View Admin Dashboard</a></p>
</body>
</html>
"""

@submit_bp.route('/', methods=['GET', 'POST'])
def submit_job():
    if request.method == 'GET':
        return render_template_string(SUBMIT_FORM)
    
    try:
        # Get form data
        job_type = request.form.get('job_type')
        title = request.form.get('title')
        description = request.form.get('description', '')
        priority = request.form.get('priority', 'normal')
        
        if not job_type or not title:
            return jsonify({'error': 'Job type and title are required'}), 400
        
        # Handle file upload
        file_path = None
        if 'file' in request.files:
            file = request.files['file']
            if file.filename:
                filename = secure_filename(file.filename)
                
                # Save file locally or to GCS
                if os.environ.get('INSTANCE_CONNECTION_NAME'):
                    # Cloud environment - save to GCS
                    try:
                        from google.cloud import storage
                        client = storage.Client()
                        bucket_name = os.environ.get('GCS_BUCKET_NAME')
                        bucket = client.bucket(bucket_name)
                        blob = bucket.blob(f"uploads/{filename}")
                        blob.upload_from_file(file)
                        file_path = f"gs://{bucket_name}/uploads/{filename}"
                        logger.info(f"File uploaded to GCS: {file_path}")
                    except Exception as e:
                        logger.error(f"Failed to upload to GCS: {e}")
                        # Fall back to local storage
                        upload_dir = 'uploads'
                        os.makedirs(upload_dir, exist_ok=True)
                        file_path = os.path.join(upload_dir, filename)
                        file.save(file_path)
                else:
                    # Local environment - save locally
                    upload_dir = 'uploads'
                    os.makedirs(upload_dir, exist_ok=True)
                    file_path = os.path.join(upload_dir, filename)
                    file.save(file_path)
                    logger.info(f"File saved locally: {file_path}")
        
        # Create job in database
        job_data = {
            'job_type': job_type,
            'title': title,
            'description': description,
            'status': 'pending',
            'priority': priority,
            'file_path': file_path
        }
        
        job_id = db_manager.create_job(job_data)
        logger.info(f"Job created with ID: {job_id}")
        
        return jsonify({
            'message': 'Job submitted successfully',
            'job_id': job_id,
            'status': 'pending'
        })
        
    except Exception as e:
        logger.error(f"Error submitting job: {e}")
        return jsonify({'error': 'Failed to submit job'}), 500

@submit_bp.route('/status/<job_id>')
def job_status(job_id):
    """Get job status"""
    try:
        job = db_manager.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify({
            'job_id': job_id,
            'status': job.get('status', 'unknown'),
            'title': job.get('title', ''),
            'created_at': job.get('created_at', ''),
            'updated_at': job.get('updated_at', '')
        })
        
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        return jsonify({'error': 'Failed to get job status'}), 500