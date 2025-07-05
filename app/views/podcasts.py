import os
from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from datetime import datetime
import tempfile
import pytz

import db_manager
import gcs_utils

podcasts_bp = Blueprint('podcasts', __name__, template_folder='../templates')

@podcasts_bp.route('/podcasts')
def list_podcasts():
    podcasts = db_manager.get_all_podcast_projects()
    return render_template('list_podcasts.html', podcasts=podcasts)

def allowed_image_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_IMAGE_EXTENSIONS']

@podcasts_bp.route('/podcasts/new', methods=['GET', 'POST'])
def new_podcast():
    if request.method == 'POST':
        title = request.form.get('title')
        if not title:
            flash('Podcast title is required.', 'error')
            return render_template('edit_podcast.html', podcast=request.form, form_action='new', timezones=pytz.common_timezones)

        cover_art_path = None
        cover_art_file = request.files.get('cover_art_file')
        if cover_art_file and cover_art_file.filename:
            if allowed_image_file(cover_art_file.filename):
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                filename = secure_filename(cover_art_file.filename)
                unique_filename = f"{timestamp}_{filename}"
                
                temp_filepath = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}") as temp_file:
                        cover_art_file.save(temp_file.name)
                        temp_filepath = temp_file.name
                    
                    gcs_destination_blob = f"assets/cover_art/{unique_filename}"
                    gcs_uri = gcs_utils.upload_file_to_gcs(temp_filepath, gcs_destination_blob)

                    if gcs_uri:
                        cover_art_path = unique_filename # Store just the filename part
                    else:
                        raise Exception("GCS upload failed.")
                finally:
                    if temp_filepath and os.path.exists(temp_filepath):
                        os.remove(temp_filepath)
            else:
                flash('Invalid cover art file type. Allowed types are png, jpg, jpeg, gif.', 'error')
                return render_template('edit_podcast.html', podcast=request.form, form_action='new', timezones=pytz.common_timezones)

        podcast_id = db_manager.add_podcast_project(
            title=title, 
            author=request.form.get('author'), 
            description=request.form.get('description'),
            default_cover_art_path=cover_art_path,
            default_template_path=request.form.get('default_template_path'),
            default_spreaker_show_id=request.form.get('default_spreaker_show_id'),
            default_publish_timezone=request.form.get('default_publish_timezone'),
            uses_omdb='uses_omdb' in request.form
        )
        if podcast_id:
            flash(f"Podcast '{title}' created successfully!", 'success')
            return redirect(url_for('podcasts.list_podcasts'))
        else:
            flash(f"Failed to create podcast '{title}'.", 'error')
            return render_template('edit_podcast.html', podcast=request.form, form_action='new', timezones=pytz.common_timezones)

    return render_template('edit_podcast.html', podcast={}, form_action='new', timezones=pytz.common_timezones)

@podcasts_bp.route('/podcasts/edit/<int:podcast_id>', methods=['GET', 'POST'])
def edit_podcast(podcast_id):
    podcast = db_manager.get_podcast_project(podcast_id)
    if not podcast:
        flash('Podcast not found.', 'error')
        return redirect(url_for('podcasts.list_podcasts'))

    # For GET requests, generate a signed URL for the cover art if it exists
    cover_art_url = None
    if request.method == 'GET' and podcast.get('default_cover_art_path'):
        try:
            blob_name = f"assets/cover_art/{podcast.get('default_cover_art_path')}"
            cover_art_url = gcs_utils.generate_signed_url(blob_name)
            if not cover_art_url:
                flash(f"Could not generate preview URL for cover art '{podcast.get('default_cover_art_path')}'.", 'warning')
        except Exception as e:
            current_app.logger.error(f"Error generating signed URL for cover art: {e}")

    if request.method == 'POST':
        title = request.form.get('title')
        if not title:
            flash('Podcast title is required.', 'error')
            updated_form_data = dict(podcast)
            updated_form_data.update(request.form)
            return render_template('edit_podcast.html', podcast=updated_form_data, podcast_id=podcast_id, form_action='edit', timezones=pytz.common_timezones)

        # Handle cover art upload
        cover_art_path = podcast.get('default_cover_art_path') # Keep old one by default
        cover_art_file = request.files.get('cover_art_file')
        if cover_art_file and cover_art_file.filename:
            if allowed_image_file(cover_art_file.filename):
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                filename = secure_filename(cover_art_file.filename)
                unique_filename = f"{timestamp}_{filename}"
                
                temp_filepath = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}") as temp_file:
                        cover_art_file.save(temp_file.name)
                        temp_filepath = temp_file.name
                    
                    gcs_destination_blob = f"assets/cover_art/{unique_filename}"
                    gcs_uri = gcs_utils.upload_file_to_gcs(temp_filepath, gcs_destination_blob)

                    if gcs_uri:
                        # If upload is successful, delete the old cover art from GCS
                        if podcast.get('default_cover_art_path'):
                            gcs_utils.delete_gcs_blob(f"assets/cover_art/{podcast.get('default_cover_art_path')}")
                        cover_art_path = unique_filename # Update to new filename
                finally:
                    if temp_filepath and os.path.exists(temp_filepath):
                        os.remove(temp_filepath)
            else:
                flash('Invalid cover art file type. Allowed types are png, jpg, jpeg, gif.', 'error')
                return redirect(url_for('podcasts.edit_podcast', podcast_id=podcast_id))


        success = db_manager.update_podcast_project(
            podcast_id=podcast_id, title=title, author=request.form.get('author'), 
            description=request.form.get('description'),
            default_cover_art_path=cover_art_path,
            default_template_path=request.form.get('default_template_path'),
            default_spreaker_show_id=request.form.get('default_spreaker_show_id'),
            default_publish_timezone=request.form.get('default_publish_timezone'),
            uses_omdb='uses_omdb' in request.form
        )
        if success:
            flash(f"Podcast '{title}' updated successfully!", 'success')
            return redirect(url_for('podcasts.list_podcasts'))
        else:
            flash(f"Failed to update podcast '{title}'.", 'error')
            return redirect(url_for('podcasts.edit_podcast', podcast_id=podcast_id))

    return render_template('edit_podcast.html', podcast=podcast, podcast_id=podcast_id, form_action='edit', timezones=pytz.common_timezones, cover_art_url=cover_art_url)