import os
from flask import (Blueprint, request, render_template, redirect, url_for, flash, session, current_app, jsonify)
from werkzeug.utils import secure_filename
import logging
from werkzeug.exceptions import BadRequestKeyError, BadRequest # Import specific exceptions
from datetime import datetime
import tempfile # For temporary file handling
import gcs_utils # Import our new GCS utility
import db_manager
from google.cloud import storage

logger = logging.getLogger(__name__)

submit_bp = Blueprint('submit', __name__, template_folder='../../templates')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@submit_bp.route('/submit/generate-upload-url', methods=['POST'])
def generate_upload_url():
    """Generates a signed URL for uploading a file directly to GCS."""
    try:
        data = request.get_json()
        filename = data.get('filename')
        content_type = data.get('contentType')
        
        if not filename:
            return jsonify({'error': 'Filename is required'}), 400

        # Get the bucket name from environment variables
        bucket_name = os.environ.get('GCS_BUCKET_NAME')
        if not bucket_name:
            logger.error("GCS_BUCKET_NAME environment variable not set.")
            return jsonify({'error': 'Server is not configured for file uploads.'}), 500

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        # Create a unique filename to avoid overwriting files
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_filename = f"uploads/{timestamp}_{secure_filename(filename)}"
        blob = bucket.blob(unique_filename)

        # Generate the signed URL, valid for 15 minutes
        from datetime import timedelta
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="PUT",
            content_type=content_type
        )
        
        # The permanent path to the file after upload
        file_path = f"gs://{bucket_name}/{unique_filename}"

        return jsonify({'upload_url': url, 'file_path': file_path})

    except Exception as e:
        logger.error(f"Could not generate signed URL: {e}", exc_info=True)
        return jsonify({'error': 'Failed to generate upload URL'}), 500

@submit_bp.route('/submit/', methods=['POST'])
def submit_job_api():
    """API endpoint for submitting job metadata after file upload"""
    try:
        # Get form data
        job_type = request.form.get('job_type')
        title = request.form.get('title')
        description = request.form.get('description')
        priority = request.form.get('priority', 'normal')
        file_path = request.form.get('file_path')  # GCS path from upload
        
        if not job_type or not title:
            return jsonify({'error': 'Job type and title are required'}), 400
        
        # For now, create a simple job entry
        # You can expand this to integrate with your existing job system
        job_id = f"job_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        logger.info(f"Job submitted: {job_id}, type: {job_type}, title: {title}, file: {file_path}")
        
        return jsonify({
            'job_id': job_id,
            'status': 'submitted',
            'message': 'Job submitted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error submitting job: {e}", exc_info=True)
        return jsonify({'error': 'Failed to submit job'}), 500

@submit_bp.route('/submit', methods=['GET', 'POST'])
def submit_job_form():
    if request.method == 'POST':
        # --- Handle the form submission ---
        # DEBUG: Log the entire form content to see what's being received
        logger.info(f"Received form data: {request.form.to_dict()}")
        logger.info(f"Received files: {list(request.files.keys())}")

        # The broad try-except for BadRequest is removed. The global error handler in __init__.py will catch it.
        
        if 'audio_file' not in request.files:
            flash('No audio file part in the request. Please select an audio file.', 'error')
            return redirect(request.url)
        
        file = request.files['audio_file']
        
        if file.filename == '':
            flash('No selected audio file. Please choose a file.', 'error')
            return redirect(request.url)

        # --- Get form data ---
        podcast_id = request.form.get('podcast_id')
        episode_topic = request.form.get('episode_topic')
        # NOTE: The HTML form needs an input with name="episode_number"
        episode_number = request.form.get('episode_number')
        ai_intro_text = request.form.get('ai_intro_text', '')

        # --- Validate required fields ---
        if not podcast_id or not episode_topic or not episode_number:
            flash('A Podcast, Episode Topic, and Episode Number are required.', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            unique_filename = f"{timestamp}_{filename}"
            
            # Save to a temporary local file first
            temp_filepath = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}") as temp_file:
                    file.save(temp_file.name)
                    temp_filepath = temp_file.name
                logger.info(f"Audio file saved temporarily to {temp_filepath}")

                # Upload the temporary file to GCS
                gcs_destination_blob = f"uploads/{unique_filename}"
                gcs_uri = gcs_utils.upload_file_to_gcs(temp_filepath, gcs_destination_blob)

                if not gcs_uri:
                    flash('Failed to upload audio file to cloud storage.', 'error')
                    return redirect(request.url)
            finally:
                # Clean up the temporary file
                if temp_filepath and os.path.exists(temp_filepath):
                    os.remove(temp_filepath)

            # --- Construct arguments for the database job ---
            # NOTE: A mechanism to select a template should be added to the UI.
            # For now, we are hardcoding a default path.
            template_path = "config/spreaker.json"
            
            # The base filename for all output artifacts (transcript, show notes, etc.)
            output_base_filename = f"{timestamp}_{os.path.splitext(filename)[0]}"

            # The base directory for all output artifacts for this specific job.
            # In a cloud environment, this is a "virtual" path prefix in GCS.
            job_base_output_dir = f"processed_output/{output_base_filename}"

            try:
                # --- Correctly call the database function ---
                job_id = db_manager.add_job(
                    podcast_id=podcast_id,
                    episode_topic=episode_topic,
                    episode_number=episode_number,
                    template_path=template_path,
                    recording_filename=filename, # Original filename
                    uploaded_recording_path=gcs_uri, # Use the GCS URI
                    output_base_filename=output_base_filename,
                    job_base_output_dir=job_base_output_dir,
                    ai_intro_text=ai_intro_text
                    # Other settings like remove_fillers will use defaults in db_jobs.py
                )
                
                if not job_id:
                    raise Exception("Failed to create job ID in the database.")

                podcast = db_manager.get_podcast_project(podcast_id)
                podcast_title = podcast['title'] if podcast else f"ID {podcast_id}"
                flash(f"Job for '{podcast_title}' submitted successfully with ID {job_id}!", "success")
                return redirect(url_for('admin.admin_page'))
            except Exception as e:
                logger.error(f"Error adding job to database: {e}", exc_info=True)
                flash(f"An internal database error occurred: {e}", "error")
                # If DB write fails, try to clean up the GCS object
                if gcs_uri: gcs_utils.delete_gcs_blob(gcs_destination_blob)
                return redirect(request.url)
        else:
            flash('The selected file type is not allowed. Please upload an MP3, WAV, or M4A file.', 'error')
            return redirect(request.url)

    # For a GET request, just render the form.
    # The 'podcasts' variable might not be used in the simplified template, but it's harmless.
    return render_template('submit_job.html')
