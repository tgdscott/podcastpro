import os
import logging
from flask import Blueprint, request, jsonify, render_template_string
from werkzeug.utils import secure_filename
import db_manager
from google.cloud import storage # <-- Make sure this import is here
import datetime # <-- Add this import for the URL expiration

logger = logging.getLogger(__name__)

submit_bp = Blueprint('submit', __name__)

# --- NEW: Route to generate a secure upload URL ---
@submit_bp.route('/generate-upload-url', methods=['POST'])
def generate_upload_url():
    """Generates a signed URL for uploading a file directly to GCS."""
    data = request.get_json()
    filename = data.get('filename')
    if not filename:
        return jsonify({'error': 'Filename is required'}), 400

    try:
        # Get the bucket name from environment variables
        bucket_name = os.environ.get('GCS_BUCKET_NAME')
        if not bucket_name:
            logger.error("GCS_BUCKET_NAME environment variable not set.")
            return jsonify({'error': 'Server is not configured for file uploads.'}), 500

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        # Create a unique filename to avoid overwriting files
        unique_filename = f"uploads/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{secure_filename(filename)}"
        blob = bucket.blob(unique_filename)

        # Generate the signed URL, valid for 15 minutes
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="PUT",
            content_type=data.get('contentType')
        )
        
        # The permanent path to the file after upload
        file_path = f"gs://{bucket_name}/{unique_filename}"

        return jsonify({'upload_url': url, 'file_path': file_path})

    except Exception as e:
        logger.error(f"Could not generate signed URL: {e}")
        return jsonify({'error': 'Could not generate upload URL'}), 500


# --- MODIFIED: The HTML form will be updated in the next step ---
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
        #status-message { margin-top: 20px; padding: 10px; border-radius: 4px; display: none; }
        .success { background-color: #d4edda; color: #155724; }
        .error { background-color: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <h1>Podcast Pro - Submit Job</h1>
    <form id="job-form">
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
    
    <div id="status-message"></div>
    <p><a href="/admin">View Admin Dashboard</a></p>

    <script>
        const form = document.getElementById('job-form');
        const statusMessage = document.getElementById('status-message');

        form.addEventListener('submit', async (event) => {
            event.preventDefault(); // Stop the default form submission
            
            const submitButton = form.querySelector('button[type="submit"]');
            submitButton.disabled = true;
            submitButton.textContent = 'Submitting...';
            
            const fileInput = document.getElementById('file');
            const file = fileInput.files[0];
            let filePath = null;

            try {
                // Step 1: If a file is selected, upload it to GCS first
                if (file) {
                    showMessage('Requesting upload URL...', 'info');
                    // Get the signed URL from our backend
                    const signedUrlResponse = await fetch('/submit/generate-upload-url', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ filename: file.name, contentType: file.type })
                    });

                    if (!signedUrlResponse.ok) throw new Error('Could not get upload URL.');
                    const { upload_url, file_path } = await signedUrlResponse.json();
                    filePath = file_path;

                    // Upload the file directly to GCS
                    showMessage(`Uploading ${file.name}...`, 'info');
                    const uploadResponse = await fetch(upload_url, {
                        method: 'PUT',
                        headers: { 'Content-Type': file.type },
                        body: file
                    });

                    if (!uploadResponse.ok) throw new Error('File upload to storage failed.');
                }

                // Step 2: Submit the job metadata to our backend
                showMessage('Saving job details...', 'info');
                const formData = new FormData(form);
                if (filePath) {
                    formData.append('file_path', filePath); // Add the GCS file path
                }
                formData.delete('file'); // Remove the actual file data

                const jobSubmitResponse = await fetch('/submit/', {
                    method: 'POST',
                    body: new URLSearchParams(formData) // Send as form-urlencoded
                });

                const result = await jobSubmitResponse.json();
                if (!jobSubmitResponse.ok) {
                    throw new Error(result.error || 'Failed to submit job.');
                }

                showMessage(`Job submitted successfully! Job ID: ${result.job_id}`, 'success');
                form.reset();

            } catch (error) {
                console.error('Submission failed:', error);
                showMessage(`Error: ${error.message}`, 'error');
            } finally {
                submitButton.disabled = false;
                submitButton.textContent = 'Submit Job';
            }
        });

        function showMessage(message, type) {
            statusMessage.textContent = message;
            statusMessage.className = type; // 'success' or 'error'
            statusMessage.style.display = 'block';
        }
    </script>
</body>
</html>
"""

# --- MODIFIED: The submit_job function no longer handles file uploads directly ---
@submit_bp.route('/', methods=['GET', 'POST'])
def submit_job():
    if request.method == 'GET':
        # We will update this SUBMIT_FORM in the next step to include JavaScript
        return render_template_string(SUBMIT_FORM)
    
    # This is for the POST request after the file is in GCS
    try:
        # Get form data
        job_type = request.form.get('job_type')
        title = request.form.get('title')
        description = request.form.get('description', '')
        priority = request.form.get('priority', 'normal')
        
        # IMPORTANT: The file path now comes from a hidden form field,
        # not from a direct file upload.
        file_path = request.form.get('file_path', None)
        
        if not job_type or not title:
            return jsonify({'error': 'Job type and title are required'}), 400
        
        # Create job in database
        job_data = {
            'job_type': job_type,
            'title': title,
            'description': description,
            'status': 'pending',
            'priority': priority,
            'file_path': file_path # This will be the "gs://..." path or None
        }
        
        job_id = db_manager.create_job(job_data)
        logger.info(f"Job created with ID: {job_id} and file_path: {file_path}")
        
        return jsonify({
            'message': 'Job submitted successfully',
            'job_id': job_id,
            'status': 'pending'
        })
        
    except Exception as e:
        logger.error(f"Error submitting job: {e}")
        return jsonify({'error': 'Failed to submit job'}), 500


# --- UNCHANGED: This route is fine as is ---
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