import os
import json
from flask import (Blueprint, request, render_template, redirect, url_for,
                   flash, current_app)
from werkzeug.utils import secure_filename

templates_bp = Blueprint('templates', __name__, template_folder='../templates')

def get_template_files():
    """Helper to get a list of .json files from the templates directory."""
    try:
        files = [f for f in os.listdir(current_app.config['TEMPLATES_FOLDER']) if f.endswith('.json')]
        return sorted(files)
    except FileNotFoundError:
        current_app.logger.error(f"Templates directory not found: {current_app.config['TEMPLATES_FOLDER']}")
        return []

@templates_bp.route('/templates')
def list_templates():
    return render_template('list_templates.html', templates=get_template_files())

@templates_bp.route('/templates/new', methods=['GET', 'POST'])
def new_template():
    if request.method == 'POST':
        filename = request.form.get('filename')
        if not filename:
            flash('Filename is required.', 'error')
            return render_template('edit_template.html', form_action='new', template_filename=None, template_data={})
        
        safe_filename = secure_filename(filename if filename.endswith('.json') else f"{filename}.json")
        filepath = os.path.join(current_app.config['TEMPLATES_FOLDER'], safe_filename)

        if os.path.exists(filepath):
            flash(f"Template '{safe_filename}' already exists.", 'error')
            return render_template('edit_template.html', form_action='new', template_filename=safe_filename, template_data={'config': request.form})

        default_template_content = {"config": {}, "audio_files": {}, "ordered_segments": [], "background_music_beds": [], "elevenlabs": {}, "stop_word": {}}
        try:
            with open(filepath, 'w') as f:
                json.dump(default_template_content, f, indent=2)
            flash(f"Template '{safe_filename}' created successfully. You can now edit it.", 'success')
            return redirect(url_for('templates.edit_template', template_filename=safe_filename))
        except Exception as e:
            flash(f"Error creating template file: {e}", 'error')
            return redirect(url_for('templates.list_templates'))

    return render_template('edit_template.html', form_action='new', template_filename='new_template.json', template_data={'config': {}})

@templates_bp.route('/templates/edit/<path:template_filename>', methods=['GET', 'POST'])
def edit_template(template_filename):
    safe_filename = secure_filename(template_filename)
    filepath = os.path.join(current_app.config['TEMPLATES_FOLDER'], safe_filename)

    if not os.path.exists(filepath):
        flash(f"Template file not found: {safe_filename}", 'error')
        return redirect(url_for('templates.list_templates'))

    if request.method == 'POST':
        try:
            with open(filepath, 'r') as f: data = json.load(f)
            
            # Update simple configs
            data['config'] = {
                'podcast_title': request.form.get('podcast_title', ''),
                'spreaker_title_template': request.form.get('spreaker_title_template', '')
            }
            data['elevenlabs'] = {'enabled': 'elevenlabs_enabled' in request.form, 'voice_id': request.form.get('elevenlabs_voice_id', '')}
            data['stop_word'] = {'enabled': 'stop_word_enabled' in request.form, 'word': request.form.get('stop_word_text', '')}

            # Update complex list-based sections
            new_ordered_segments = []
            for i, name in enumerate(request.form.getlist('segment_name')):
                if not name: continue
                segment_type = request.form.getlist('segment_type')[i]
                source_key_or_duration = request.form.getlist('segment_source_key')[i]
                new_ordered_segments.append({ "name": name, "type": segment_type, "role": request.form.getlist('segment_role')[i], "source_key": source_key_or_duration if segment_type != 'silence' else None, "duration_ms": int(source_key_or_duration or 1000) if segment_type == 'silence' else None })
            data['ordered_segments'] = new_ordered_segments
            data['background_music_beds'] = [
                {
                    "name": name, "source_key": request.form.getlist('music_bed_source_key')[i],
                    "volume_db": float(request.form.getlist('music_bed_volume_db')[i] or 0.0),
                    "loop": request.form.get(f'music_bed_loop_{i}') == 'true',
                    "fade_in_ms": int(request.form.getlist('music_bed_fade_in_ms')[i] or 0),
                    "fade_out_ms": int(request.form.getlist('music_bed_fade_out_ms')[i] or 0),
                    "start_offset_ms": int(request.form.getlist('music_bed_start_offset_ms')[i] or 0),
                    "end_offset_ms": int(request.form.getlist('music_bed_end_offset_ms')[i] or 0)
                } for i, name in enumerate(request.form.getlist('music_bed_name')) if name
            ]
            
            # Rebuild audio_files from scratch to handle additions/deletions
            new_audio_files = {}
            audio_keys = request.form.getlist('audio_file_key')
            audio_paths = request.form.getlist('audio_file_path')
            for i, key in enumerate(audio_keys):
                if key.strip() and i < len(audio_paths): # Ensure key is not empty and path exists
                    new_audio_files[key.strip()] = audio_paths[i]
            data['audio_files'] = new_audio_files

            with open(filepath, 'w') as f: json.dump(data, f, indent=2)
            flash(f"Template '{safe_filename}' saved successfully.", 'success')
        except Exception as e:
            flash(f"Error saving template: {e}", 'error')
        return redirect(url_for('templates.edit_template', template_filename=safe_filename))

    # GET request
    try:
        with open(filepath, 'r') as f: template_data = json.load(f)
        return render_template('edit_template.html', form_action='edit', template_filename=safe_filename, template_data=template_data)
    except Exception as e:
        flash(f"Error reading template file {safe_filename}: {e}", "error")
        return redirect(url_for('templates.list_templates'))

@templates_bp.route('/templates/delete/<path:template_filename>', methods=['POST'])
def delete_template(template_filename):
    safe_filename = secure_filename(template_filename)
    filepath = os.path.join(current_app.config['TEMPLATES_FOLDER'], safe_filename)
    try:
        os.remove(filepath)
        flash(f"Template '{safe_filename}' deleted successfully.", 'success')
    except Exception as e:
        flash(f"Error deleting template: {e}", 'error')
    return redirect(url_for('templates.list_templates'))

@templates_bp.route('/templates/duplicate/<path:template_filename>', methods=['POST'])
def duplicate_template(template_filename):
    safe_filename = secure_filename(template_filename)
    filepath = os.path.join(current_app.config['TEMPLATES_FOLDER'], safe_filename)
    try:
        with open(filepath, 'r') as f: template_content = json.load(f)
        new_filename = safe_filename.replace('.json', '_copy.json')
        new_filepath = os.path.join(current_app.config['TEMPLATES_FOLDER'], new_filename)
        with open(new_filepath, 'w') as f: json.dump(template_content, f, indent=2)
        flash(f"Template '{safe_filename}' duplicated to '{new_filename}' successfully.", 'success')
    except Exception as e:
        flash(f"Error duplicating template: {e}", 'error')
    return redirect(url_for('templates.list_templates'))