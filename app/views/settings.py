from flask import Blueprint, request, render_template, redirect, url_for, flash
import pytz
import db_manager

settings_bp = Blueprint('settings', __name__, template_folder='../templates')

@settings_bp.route('/settings', methods=['GET', 'POST'])
def settings_page():
    if request.method == 'POST':
        # --- Save API Keys ---
        api_keys_to_update = {
            'elevenlabs': request.form.get('elevenlabs_api_key'),
            'gemini': request.form.get('gemini_api_key'),
            'omdb': request.form.get('omdb_api_key'),
            'spreaker_token': request.form.get('spreaker_api_token')
        }
        for service, key_value in api_keys_to_update.items():
            if key_value:
                db_manager.save_api_key(service, key_value)

        db_manager.save_api_key('spreaker_show_id', request.form.get('spreaker_show_id', ''))

        # --- Save Application Settings ---
        app_settings_to_save = {
            'enable_elevenlabs': 'true' if request.form.get('enable_elevenlabs') else 'false',
            'enable_gemini': 'true' if request.form.get('enable_gemini') else 'false',
            'enable_spreaker': 'true' if request.form.get('enable_spreaker') else 'false',
            'show_notes_template': request.form.get('show_notes_template', '')
        }
        for setting_name, setting_value in app_settings_to_save.items():
            db_manager.set_application_setting(setting_name, setting_value)

        # --- Save Schedule Configuration ---
        days_of_week_str = ','.join(request.form.getlist('days_of_week'))
        schedule_config_to_save = {
            'schedule_type': request.form.get('schedule_type'),
            'times_per_period': request.form.get('times_per_period'),
            'days_of_week': days_of_week_str,
            'publish_time_local': request.form.get('publish_time_local'),
            'podcast_timezone': request.form.get('podcast_timezone')
        }
        try:
             times_per_period_value = int(schedule_config_to_save['times_per_period'])
             if not (1 <= times_per_period_value <= 7): raise ValueError("Invalid range")
        except (ValueError, TypeError):
             flash("Invalid value for 'Times per Week', must be a number between 1 and 7.", 'error')
             return redirect(url_for('settings.settings_page'))

        db_manager.update_schedule_config(schedule_config_to_save)
        flash('Settings saved successfully!', 'success')
        return redirect(url_for('settings.settings_page'))

    # --- GET request: Load current settings ---
    current_api_keys = {
        'elevenlabs': db_manager.get_api_key('elevenlabs'),
        'gemini': db_manager.get_api_key('gemini'),
        'omdb': db_manager.get_api_key('omdb'),
        'spreaker_token': db_manager.get_api_key('spreaker_token'),
        'spreaker_show_id': db_manager.get_api_key('spreaker_show_id') or ''
    }
    current_app_settings = {
        'enable_elevenlabs': db_manager.get_application_setting('enable_elevenlabs', 'true').lower() == 'true',
        'enable_gemini': db_manager.get_application_setting('enable_gemini', 'true').lower() == 'true',
        'enable_spreaker': db_manager.get_application_setting('enable_spreaker', 'true').lower() == 'true',
        'show_notes_template': db_manager.get_application_setting('show_notes_template', '')
    }
    
    current_schedule_config = db_manager.get_schedule_config() or {}
    default_schedule_keys = {
        'schedule_type': 'weekly', 'times_per_period': 3, 'days_of_week': '0,2,4', 
        'publish_time_local': '05:00', 'podcast_timezone': 'America/Los_Angeles'
    }
    for key, default_val in default_schedule_keys.items():
        current_schedule_config.setdefault(key, default_val)

    return render_template('settings.html', 
                           api_keys=current_api_keys, 
                           app_settings=current_app_settings,
                           schedule_config=current_schedule_config,
                           timezones=pytz.common_timezones)