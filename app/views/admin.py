import os
from flask import (Blueprint, redirect, url_for, flash, render_template, jsonify, send_from_directory, current_app, request)
import logging
from datetime import datetime
import db_manager
import gcs_utils # Import our GCS utility

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, template_folder='../../templates')

@admin_bp.route('/')
def admin_page():
    active_jobs = db_manager.get_all_active_jobs()
    job_history = db_manager.get_job_history()
    scheduled_episodes = db_manager.get_all_scheduled_episodes()
    return render_template('admin.html', jobs=active_jobs, job_history=job_history, scheduled_episodes=scheduled_episodes)

@admin_bp.route('/job_status/<int:job_id>')
def job_status(job_id):
    status_info = db_manager.get_job_status(job_id)
    if status_info:
        # Manually create the dictionary to prevent the ValueError.
        # This assumes get_job_status returns a tuple like: (status, log_file_path)
        status_dict = {
            'status': status_info[0],
            'log_file_path': status_info[1] if len(status_info) > 1 else None
        }
        return jsonify(status_dict)
    else:
        return jsonify({'status': 'not_found'})

@admin_bp.route('/delete_job/<int:job_id>', methods=['POST'])
def delete_job(job_id):
    db_manager.delete_job(job_id)
    flash(f"Job ID {job_id} deleted.", "success")
    return redirect(url_for('admin.admin_page'))

# Add other admin routes like rerun, unschedule, etc. here

@admin_bp.route('/rerun_job/<int:job_id>', methods=['POST'])
def rerun_job(job_id):
    new_job_id = db_manager.recreate_job_from_existing(job_id)
    if new_job_id:
        flash(f"Job {job_id} re-queued as new Job ID {new_job_id}.", "success")
    else:
        flash(f"Failed to re-run job {job_id}.", "error")
    return redirect(url_for('admin.admin_page'))

@admin_bp.route('/get_job_logs_api/<int:job_id>')
def get_job_logs_api(job_id):
    """API endpoint to fetch logs for a specific job."""
    try:
        logs = db_manager.get_job_logs(job_id)
        # Convert datetime objects to string for JSON serialization
        serialized_logs = [{'timestamp': log.timestamp.isoformat(), 'message': log.message} for log in logs]
        return jsonify(serialized_logs)
    except Exception as e:
        logger.error(f"Error fetching logs for job {job_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/unschedule_episode/<int:episode_id>', methods=['POST'])
def unschedule_episode(episode_id):
    db_manager.delete_scheduled_episode(episode_id) # Assuming this function exists in db_manager
    flash(f"Scheduled episode ID {episode_id} removed from local DB.", "success")
    return redirect(url_for('admin.admin_page'))

@admin_bp.route('/get_download_url/<int:episode_id>/<file_type>')
def get_download_url(episode_id, file_type):
    """Generates a signed URL for a processed file stored in GCS."""
    episode_details = db_manager.get_episode_by_id(episode_id)
    
    if not episode_details:
        return jsonify({'error': 'Episode not found in database.'}), 404

    gcs_uri = None
    if file_type == 'mp3':
        gcs_uri = episode_details.get('processed_mp3_path')
    elif file_type == 'shownotes':
        gcs_uri = episode_details.get('show_notes_path')
    elif file_type == 'poster':
        gcs_uri = episode_details.get('poster_path')
    else:
        return jsonify({'error': 'Invalid file type specified.'}), 400

    if not gcs_uri or not gcs_uri.startswith('gs://'):
        return jsonify({'error': f'No valid GCS path found for {file_type}. Path: {gcs_uri}'}), 404

    # Extract blob name from gs://bucket-name/path/to/file
    try:
        blob_name = gcs_uri.split('/', 3)[-1]
    except (IndexError, AttributeError):
        return jsonify({'error': 'Invalid GCS URI format in database.'}), 500

    signed_url = gcs_utils.generate_signed_url(blob_name)

    if not signed_url:
        return jsonify({'error': 'Could not generate download URL.'}), 500

    return jsonify({'url': signed_url})