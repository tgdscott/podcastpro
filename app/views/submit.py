import os
from flask import (Blueprint, request, render_template, redirect, url_for, flash, session, current_app)
from werkzeug.utils import secure_filename
import logging
from werkzeug.exceptions import BadRequestKeyError, BadRequest # Import specific exceptions
from datetime import datetime
import tempfile # For temporary file handling
import gcs_utils # Import our new GCS utility
import db_manager

logger = logging.getLogger(__name__)

submit_bp = Blueprint('submit', __name__, template_folder='../../templates')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

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
