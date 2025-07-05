import argparse
import logging
import os
import sys
import re
from typing import Optional, Tuple, List, Any
from datetime import datetime
import time
import tempfile

# Add the parent directory to sys.path to allow imports from sibling modules
# This is important if run_podcast_job.py is executed directly or via a separate process
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_SCRIPT_DIR)

import db_manager
import gcs_utils # Import the GCS utility
from enhanced_audio_processor import EnhancedAudioProcessor
from podcast_template import PodcastTemplate

# Set up logging
# We configure the root logger to send to console, and add a DB handler per-job.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

# Custom logging handler to write logs to the database for a specific job
class DatabaseLogHandler(logging.Handler):
    """A logging handler that writes logs to the database."""
    def __init__(self, job_id: int):
        super().__init__() # Call parent constructor
        self.job_id = job_id

    def emit(self, record):
        # Use db_manager to add the log entry
        db_manager.add_job_log(self.job_id, record.levelname, self.format(record))

# Helper function to parse episode number and movie name from recording path
# Similar to the one in cinema_irl_app_fixed.py
# NOTE: For a general product, relying on path parsing is fragile. Metadata should primarily come from user input.
def parse_details_from_path_fallback(filepath: str) -> Tuple[Optional[str], Optional[str]]:
    """
    (Fallback) Parses the recording filepath to extract episode number and topic.
    Assumes a directory structure like '.../EpisodeNum - Episode Topic/recording.mp3'
    """
    if not filepath:
        return None, None
    try:
        # Get the directory containing the file
        dir_path = os.path.dirname(filepath)
        # Get the last part of the directory path (e.g., "150 - Movie Title" or "150 - [Movie Title]")
        episode_topic_folder = os.path.basename(dir_path)

        # Regex to handle "X - [Y]" (movie name in group 2) or "X - Y" (movie name in group 3)
        # Added handling for just "X" or "X -"
        match = re.match(r'^\s*(\d+)\s*(?:-\s*(?:\[(.*?)\]|(.*)))?\s*$', episode_topic_folder)
        if match:
            episode_num = match.group(1)
            topic_in_brackets = match.group(2)
            topic_plain = match.group(3)

            topic_name = None
            if topic_in_brackets is not None: # Check explicitly for None, as group(2) might match empty string inside []
                topic_name = topic_in_brackets.strip()
            elif topic_plain is not None: # Check explicitly for None
                topic_name = topic_plain.strip()

            if topic_name == "": # If topic was explicitly empty like "123 - []" or "123 - "
                 topic_name = None # Treat empty string as no topic found

            if episode_num and topic_name is None:
                 logger.warning(f"Parsed episode number '{episode_num}' but extracted no topic from folder: {episode_topic_folder}")
            elif not episode_num and topic_name:
                 logger.warning(f"Parsed topic '{topic_name}' but extracted no episode number from folder: {episode_topic_folder}")
            elif not episode_num and not topic_name:
                 logger.warning(f"Could not parse episode number or topic from folder name: {episode_topic_folder}")


            return episode_num if episode_num else None, topic_name # Return None if parsing failed

        else:
            logger.warning(f"Could not parse episode number and topic from folder name: {episode_topic_folder} using path: {filepath}")
            return None, None
    except Exception as e:
        logger.error(f"Error parsing recording details from path '{filepath}': {e}", exc_info=True)
        return None, None

def analyze_audio_for_commercial_breaks(audio_file_path: str, commercial_settings: dict) -> Any:
    """
    Analyzes an audio file to identify potential commercial break locations.

    Args:
        audio_file_path: The path to the audio file.
        commercial_settings: A dictionary containing the settings for commercial break analysis.

    Returns:
        A list of potential commercial break locations, or None if an error occurs.  The
        exact format of this return will depend on the underlying implementation in EnhancedAudioProcessor.
    """
    try:
        processor = EnhancedAudioProcessor()  # You might need to adjust instantiation if constructor requires params

        # Extract commercial break parameters from the settings dictionary
        commercial_breaks_enabled = commercial_settings.get('commercial_breaks_enabled', False)
        commercial_breaks_count = commercial_settings.get('commercial_breaks_count', 2)
        commercial_breaks_min_duration_between_sec = commercial_settings.get('commercial_breaks_min_duration_between_sec', 600)
        commercial_breaks_max_duration_between_sec = commercial_settings.get('commercial_breaks_max_duration_between_sec', 1200)
        commercial_breaks_min_silence_ms = commercial_settings.get('commercial_breaks_min_silence_ms', 500)
        commercial_breaks_cue_phrases = commercial_settings.get('commercial_breaks_cue_phrases', "")
        commercial_breaks_audio_keys = commercial_settings.get('commercial_breaks_audio_keys', "")

        if not commercial_breaks_enabled:
            logger.info("Commercial break analysis is disabled.")
            return None

        logger.info(f"Analyzing audio file '{audio_file_path}' for commercial breaks.")
        commercial_break_locations = processor.find_commercial_break_locations(
            audio_file_path,
            commercial_breaks_count=commercial_breaks_count,
            commercial_breaks_min_duration_between_sec=commercial_breaks_min_duration_between_sec,
            commercial_breaks_max_duration_between_sec=commercial_breaks_max_duration_between_sec,
            commercial_breaks_min_silence_ms=commercial_breaks_min_silence_ms,
            commercial_breaks_cue_phrases=commercial_breaks_cue_phrases,
            commercial_breaks_audio_keys=commercial_breaks_audio_keys
        )

        if commercial_break_locations:
            logger.info(f"Found commercial break locations: {commercial_break_locations}")
        else:
            logger.info("No commercial break locations found.")

        return commercial_break_locations

    except Exception as e:
        logger.error(f"Error analyzing audio for commercial breaks: {e}", exc_info=True)
        return None


def run_job(job_id: int):
    # Add the database handler to the root logger. All loggers inherit from it.
    db_log_handler = DatabaseLogHandler(job_id=job_id)
    # Set a specific format for the DB logger to avoid duplicating the timestamp.
    db_log_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    root_logger = logging.getLogger()
    root_logger.addHandler(db_log_handler)
    
    try:
        logger.info(f"Attempting to run job ID: {job_id}")
        db_manager.update_job_status(job_id, "processing")

        job_details = db_manager.get_job_details(job_id)
        if not job_details:
            logger.error(f"Job ID {job_id} not found in database.")
            db_manager.update_job_status(job_id, "failed", "Job ID not found")
            return

        logger.info(f"Processing job: {job_details}")

        # Resolve the template path
        template_path_from_db = job_details.get("template_path")
        if template_path_from_db and not os.path.isabs(template_path_from_db):
            template_path = os.path.join(_SCRIPT_DIR, template_path_from_db)
        else:
            template_path = template_path_from_db # It's already absolute or None

        # Resolve the uploaded recording path
        uploaded_recording_path_from_db = job_details.get("uploaded_recording_path")
        if uploaded_recording_path_from_db and not os.path.isabs(uploaded_recording_path_from_db):
            uploaded_recording_path = os.path.join(_SCRIPT_DIR, uploaded_recording_path_from_db)
        else:
            uploaded_recording_path = uploaded_recording_path_from_db

        output_base_filename = job_details.get("output_base_filename")
        episode_number_db = job_details.get("episode_number") # New from DB
        episode_topic_db = job_details.get("episode_topic") # Changed from movie_title to episode_topic
        # Get new job-specific settings from DB
        job_ai_intro_text = job_details.get("ai_intro_text")
        job_stop_word_detection_enabled = job_details.get("stop_word_detection_enabled") # This will be 0 or 1
        job_base_output_dir_db = job_details.get("job_base_output_dir") # New
        job_remove_fillers = job_details.get("remove_fillers") # This will be 0 or 1 from SQLite for boolean
        job_intern_command_enabled = job_details.get("intern_command_enabled") # This will be 0 or 1
        job_intern_command_keyword = job_details.get("intern_command_keyword")
        job_season_number = job_details.get("season_number") # New
        job_remove_pauses = job_details.get("remove_pauses") # New
        job_generate_transcript = job_details.get("generate_transcript") # New
        job_generate_show_notes = job_details.get("generate_show_notes") # New
        job_use_gemini_for_summary = job_details.get("use_gemini_for_summary") # New
        job_download_poster = job_details.get("download_poster") # New
        job_min_pause_duration_sec = job_details.get("min_pause_duration_sec") # New
        job_custom_filler_words_csv = job_details.get("custom_filler_words_csv") # New
        job_podcast_id = job_details.get("podcast_id") # Get the associated podcast_id

        # NEW: Commercial Break Settings from DB
        job_commercial_breaks_enabled = bool(job_details.get('commercial_breaks_enabled'))
        job_commercial_breaks_count = job_details.get('commercial_breaks_count')
        job_commercial_breaks_min_duration_between_sec = job_details.get('commercial_breaks_min_duration_between_sec')
        job_commercial_breaks_max_duration_between_sec = job_details.get('commercial_breaks_max_duration_between_sec')
        job_commercial_breaks_min_silence_ms = job_details.get('commercial_breaks_min_silence_ms')
        job_commercial_breaks_cue_phrases = job_details.get('commercial_breaks_cue_phrases')
        job_commercial_breaks_audio_keys = job_details.get('commercial_breaks_audio_keys')

        # Store Commercial Break settings into a dictionary for analysis
        commercial_settings = {
            'commercial_breaks_enabled': job_commercial_breaks_enabled,
            'commercial_breaks_count': job_commercial_breaks_count,
            'commercial_breaks_min_duration_between_sec': job_commercial_breaks_min_duration_between_sec,
            'commercial_breaks_max_duration_between_sec': job_commercial_breaks_max_duration_between_sec,
            'commercial_breaks_min_silence_ms': job_commercial_breaks_min_silence_ms,
            'commercial_breaks_cue_phrases': job_commercial_breaks_cue_phrases,
            'commercial_breaks_audio_keys': job_commercial_breaks_audio_keys
        }

        if not uploaded_recording_path or not output_base_filename:
            logger.error(f"Job {job_id} is missing critical data (recording or output filename).")
            db_manager.update_job_status(job_id, "failed", "Missing critical job data")
            return

        # Determine the base output directory for this job's artifacts
        if not job_base_output_dir_db:
            logger.error(f"Job {job_id} is missing 'job_base_output_dir'. Cannot determine where to save files.")
            db_manager.update_job_status(job_id, "failed", "Missing job_base_output_dir")
            return

        # Ensure the job-specific base output directory exists
        if not os.path.exists(job_base_output_dir_db):
            os.makedirs(job_base_output_dir_db, exist_ok=True)

        # --- Fetch Podcast Project Details if podcast_id is present ---
        podcast_project_details = None
        if job_podcast_id:
            podcast_project_details = db_manager.get_podcast_project(job_podcast_id)
            if podcast_project_details:
                logger.info(f"Job {job_id} is associated with Podcast Project ID {job_podcast_id} ('{podcast_project_details.get('title')}').")
                # Override template_path if not set in job and default_template_path exists in project
                if not template_path and podcast_project_details.get('default_template_path'):
                    default_project_template_path = podcast_project_details.get('default_template_path')
                    # Assume default template path from project is relative to script dir unless absolute
                    if default_project_template_path and not os.path.isabs(default_project_template_path):
                        template_path = os.path.join(_SCRIPT_DIR, default_project_template_path)
                    else:
                        template_path = default_project_template_path
                    if template_path:
                         logger.info(f"Using default template path from podcast project: {template_path}")
                    else:
                         logger.warning("Podcast project has a default_template_path but it's empty or invalid.")
            else:
                logger.warning(f"Job {job_id} has podcast_id {job_podcast_id}, but project details not found in DB.")

        if not template_path or not os.path.exists(template_path):
            logger.error(f"Template file not found or path missing: {template_path} for job ID {job_id}")
            db_manager.update_job_status(job_id, "failed", f"Template file not found: {template_path or 'N/A'}")
            return

        if not os.path.exists(uploaded_recording_path):
            logger.error(f"Recording file not found: {uploaded_recording_path} for job ID {job_id}")
            db_manager.update_job_status(job_id, "failed", f"Recording file not found: {uploaded_recording_path}")
            return

        try:
            podcast_template_obj = PodcastTemplate.load_from_file(template_path)
            logger.info(f"Successfully loaded template: {template_path}")

            # Construct the full prefix for output files using the job's specific base output directory
            output_path_prefix = os.path.join(job_base_output_dir_db, output_base_filename)

            # --- API Key Fetching Logic ---
            # Priority: 1. DB, 2. Environment Variable, 3. Template (for some, not all)
            # The `is_globally_enabled_setting_name` refers to a key in the `application_settings` table.
            def get_effective_api_key(db_key_name: str, env_var_name: str,
                                      template_config_key: Optional[str] = None,
                                      template_is_enabled_check_key: Optional[str] = None,
                                      is_globally_enabled_setting_name: Optional[str] = None) -> Optional[str]:

                # Check global application setting first if provided
                if is_globally_enabled_setting_name:
                    globally_enabled_str = db_manager.get_application_setting(is_globally_enabled_setting_name, 'true') # Default to true if setting not found
                    if globally_enabled_str.lower() != 'true':
                        logger.info(f"Service related to '{db_key_name}' is globally disabled via application setting '{is_globally_enabled_setting_name}'. Skipping key retrieval.")
                        return None

                key_from_db = db_manager.get_api_key(db_key_name)
                if key_from_db:
                    logger.info(f"Using API key for '{db_key_name}' from database.")
                    return key_from_db

                key_from_env = os.environ.get(env_var_name)
                if key_from_env:
                    logger.info(f"Using API key for '{db_key_name}' from environment variable '{env_var_name}'.")
                    return key_from_env

                # Check if feature is enabled in template before trying to get key from template
                # Note: template_is_enabled_check_key is used to check if the *feature* is enabled in the template config,
                # not necessarily if the key itself is present in the template.
                template_feature_enabled = podcast_template_obj.config.get(template_is_enabled_check_key, False) if template_is_enabled_check_key else True # Assume enabled if no check key
                if template_config_key and template_feature_enabled:
                     # For ElevenLabs, the key is in the 'elevenlabs' sub-dict
                     if db_key_name == 'elevenlabs' and 'elevenlabs' in podcast_template_obj.config:
                          key_from_template = podcast_template_obj.config['elevenlabs'].get(template_config_key)
                     else: # For others, assume key is directly in config
                        key_from_template = podcast_template_obj.config.get(template_config_key)

                     if key_from_template:
                        logger.info(f"Using API key for '{db_key_name}' from template config key '{template_config_key}'.")
                        return key_from_template

                logger.info(f"No API key found for '{db_key_name}' from DB, Env Var '{env_var_name}', or Template.")
                return None

            elevenlabs_key_effective = get_effective_api_key('elevenlabs', 'ELEVENLABS_API_KEY', 'api_key', 'elevenlabs.enabled', 'enable_elevenlabs') # Note: template key is 'api_key' within 'elevenlabs' dict
            gemini_key_effective = get_effective_api_key('gemini', 'GEMINI_API_KEY', 'gui_gemini_api_key', 'gui_use_gemini_for_show_notes', 'enable_gemini')
            omdb_key_effective = get_effective_api_key('omdb', 'OMDB_API_KEY', 'gui_omdb_api_key', 'gui_download_poster', 'enable_omdb')

            # Spreaker Show ID: Prioritize podcast project default, then global DB, then env, then template
            # This logic is now more robust.
            # 1. Check the podcast project details first.
            # 2. Fallback to global settings if not defined at the project level.
            spreaker_show_id_from_project = podcast_project_details.get('default_spreaker_show_id') if podcast_project_details else None
            if spreaker_show_id_from_project:
                logger.info(f"Using Spreaker Show ID '{spreaker_show_id_from_project}' from podcast project settings.")
                spreaker_show_id_effective = spreaker_show_id_from_project
            else:
                spreaker_show_id_effective = get_effective_api_key('spreaker_show_id', 'SPREAKER_SHOW_ID', 'gui_spreaker_show_id', 'gui_spreaker_enabled', 'enable_spreaker')

            spreaker_token_effective = get_effective_api_key('spreaker_token', 'SPREAKER_API_TOKEN', 'gui_spreaker_api_token', 'gui_spreaker_enabled', 'enable_spreaker') # Token is usually global

            # Determine if features are effectively enabled based on API keys and template settings
            # OMDb now also checks the podcast-specific setting.
            podcast_uses_omdb = bool(podcast_project_details.get('uses_omdb')) if podcast_project_details else False
            job_download_poster_flag = bool(job_download_poster) if job_download_poster is not None else True # Default to true if not specified in job

            elevenlabs_effectively_enabled = bool(elevenlabs_key_effective and podcast_template_obj.elevenlabs.get('enabled'))
            gemini_effectively_enabled = bool(gemini_key_effective and podcast_template_obj.config.get('gui_use_gemini_for_show_notes'))
            omdb_effectively_enabled = bool(omdb_key_effective and job_download_poster_flag and podcast_uses_omdb)
            spreaker_effectively_enabled = bool(spreaker_token_effective and spreaker_show_id_effective and podcast_template_obj.config.get('gui_spreaker_enabled'))

            # Get the global show notes template from settings
            global_show_notes_template = db_manager.get_application_setting('show_notes_template')

            processor = EnhancedAudioProcessor(
                elevenlabs_api_key=elevenlabs_key_effective,
                gemini_api_key=gemini_key_effective,
                omdb_api_key=omdb_key_effective
            )

            # Prioritize episode number and movie title from DB if available
            episode_number = episode_number_db
            episode_topic = episode_topic_db # Use the value from DB (which was 'movie_title' column)

            if not episode_number_db or not episode_topic_db:
                logger.info("Episode number or topic not found in DB for job, attempting to parse from path (fallback).")
                # Fallback to parsing from path if not in DB (e.g., for older jobs or if UI didn't provide)
                parsed_ep_num, parsed_topic = parse_details_from_path_fallback(uploaded_recording_path)
                if not episode_number: episode_number = parsed_ep_num
                if not episode_topic: episode_topic = parsed_topic # Use parsed_topic here
                if not episode_number: logger.warning(f"Could not determine episode number for job {job_id}. Show notes and Spreaker numbering might be affected.")
                if not episode_topic: logger.warning(f"Could not determine episode topic for job {job_id}. Show notes and Spreaker title might be affected.")

            logger.info(f"Job {job_id}: Using Episode Number '{episode_number}' for processing.")

            # --- Season Number Generalization ---
            # Prioritize job-specific season number, then podcast default, then template default, then hardcoded default
            calculated_season_number = job_season_number if job_season_number is not None else \
                                       (podcast_project_details.get('default_season_number') if podcast_project_details else None)
            if calculated_season_number is None:
                 calculated_season_number = podcast_template_obj.config.get('gui_season_number', "1") # Fallback to template default
            logger.info(f"Job {job_id}: Using Season Number '{calculated_season_number}' for Spreaker.")

            # Determine parameters for process_complex_podcast
            template_config = podcast_template_obj.config
            elevenlabs_config = podcast_template_obj.elevenlabs

            # Prioritize job-specific AI intro text if provided, else use template's default if ElevenLabs is effectively enabled
            ai_intro_text_val = job_ai_intro_text if job_ai_intro_text and elevenlabs_effectively_enabled else \
                                (template_config.get('gui_default_ai_intro_text') if elevenlabs_effectively_enabled else None)

            voice_id_val = elevenlabs_config.get('voice_id') if elevenlabs_effectively_enabled else None

            # The UI now sends 'spreaker_publish_option', 'spreaker_manual_date', 'spreaker_manual_time'
            # These are NOT currently stored in the DB job record.
            # For now, we will use a hardcoded default or rely on the template's Spreaker enabled flag.
            # TODO: Add these fields to the processing_jobs table and db_manager.
            # For now, defaulting to 'Schedule Next Available Slot' if Spreaker is enabled.
            spreaker_publish_option_val = job_details.get("spreaker_publish_option", "Schedule Next Available Slot") if spreaker_effectively_enabled else None
            spreaker_manual_date_str_val = job_details.get("spreaker_manual_date_str") # These are not in DB yet
            spreaker_manual_time_str_val = job_details.get("spreaker_manual_time_str") # These are not in DB yet


            # Use job-specific settings if available, otherwise fall back to template (or a hardcoded default)
            # SQLite stores booleans as 0 or 1.
            remove_fillers_val = bool(job_remove_fillers) if job_remove_fillers is not None else template_config.get('gui_remove_fillers', True)
            remove_pauses_val = bool(job_remove_pauses) if job_remove_pauses is not None else template_config.get('gui_remove_pauses', True)
            generate_transcript_val = bool(job_generate_transcript) if job_generate_transcript is not None else template_config.get('gui_generate_transcript', True)
            generate_show_notes_val = bool(job_generate_show_notes) if job_generate_show_notes is not None else template_config.get('gui_generate_show_notes', True)
            use_gemini_for_summary_val = bool(job_use_gemini_for_summary) if job_use_gemini_for_summary is not None else template_config.get('gui_use_gemini_for_show_notes', False)
            download_poster_val = bool(job_download_poster) if job_download_poster is not None else template_config.get('gui_download_poster', True)
            intern_enabled_val = bool(job_intern_command_enabled) if job_intern_command_enabled is not None else template_config.get('gui_intern_command_enabled', False)
            intern_keyword_val = job_intern_command_keyword if job_intern_command_keyword is not None else template_config.get('gui_intern_command_keyword', 'intern')

            # Stop word detection: use job-specific toggle, word from template
            stop_word_enabled_val = bool(job_stop_word_detection_enabled) if job_stop_word_detection_enabled is not None else podcast_template_obj.stop_word.get('enabled', True)
            stop_word_text_val = podcast_template_obj.stop_word.get('word', '') # Word always comes from template or is empty
            job_specific_stop_word_config = {'enabled': stop_word_enabled_val, 'word': stop_word_text_val} # Pass this override to processor

            min_pause_duration_sec_val = job_min_pause_duration_sec if job_min_pause_duration_sec is not None else template_config.get('gui_min_pause_duration_silence', 1.5)
            custom_filler_words_csv_val = job_custom_filler_words_csv if job_custom_filler_words_csv is not None else template_config.get('gui_custom_filler_words_csv', "um,uh,er,ah,like,you know,so,well,actually,basically,literally,right,okay,yeah")

            # Get podcast-specific timezone for Spreaker client
            podcast_specific_timezone = podcast_project_details.get('default_publish_timezone') if podcast_project_details else None

            # --- NEW: Analyze audio for commercial breaks ---
            commercial_break_locations = analyze_audio_for_commercial_breaks(uploaded_recording_path, commercial_settings)

            logger.info(f"Job {job_id}: Calling process_complex_podcast with Spreaker option: '{spreaker_publish_option_val}'")
            # Unpack all returned values correctly
            (final_audio, timed_events, generated_tags,
             processed_poster_path, processed_sn_path,
             processed_episode_topic, processed_summary, # processed_summary is not directly used later but good to unpack
             processed_transcript_url, resolved_publish_time_utc, # This will hold pub_at_utc from processor
             resolved_spreaker_episode_id) = processor.process_complex_podcast( # This will hold spreaker_episode_id_from_upload
                template=podcast_template_obj,
                recording_path=uploaded_recording_path,
                ai_intro_text=ai_intro_text_val,
                voice_id=voice_id_val,
                stop_word_config_override=job_specific_stop_word_config, # Pass the job-specific config
                remove_fillers=remove_fillers_val, # Use job override
                remove_pauses=remove_pauses_val, # Use job override
                output_base_path_for_transcript=output_path_prefix,
                generate_transcript=generate_transcript_val, # Use job override
                generate_show_notes=generate_show_notes_val, # Use job override
                episode_number_for_notes=episode_number,
                episode_topic_for_content=episode_topic, # Use the determined episode_topic
                use_gemini_for_summary=use_gemini_for_summary_val and gemini_effectively_enabled, # Use job override AND effective state
                download_poster=download_poster_val and omdb_effectively_enabled,        # Use job override AND effective state
                spreaker_enabled=spreaker_effectively_enabled,     # Pass the effective state
                spreaker_title_template=podcast_template_obj.config.get('spreaker_title_template'), # Pass template title template
                spreaker_season_number=calculated_season_number, # Use calculated season number (from job/podcast/default)
                spreaker_show_id=spreaker_show_id_effective,
                spreaker_api_token=spreaker_token_effective,
                spreaker_publish_option=spreaker_publish_option_val, # This needs to align with SpreakerClient's expectations
                spreaker_manual_date_str=spreaker_manual_date_str_val, # Not in DB yet, will be None
                spreaker_manual_time_str=spreaker_manual_time_str_val, # Not in DB yet, will be None
                intern_command_enabled=intern_enabled_val,
                intern_command_keyword=intern_keyword_val,
                min_pause_duration_sec=min_pause_duration_sec_val, # Use job override
                custom_filler_words_csv=custom_filler_words_csv_val, # Use job override
                show_notes_template_str=global_show_notes_template, # Pass global show notes template from settings
                spreaker_podcast_timezone_override=podcast_specific_timezone, # Pass to processor
                # NEW: Commercial Break Parameters (Pass the settings; actual processing occurs in Processor)
                commercial_breaks_enabled=job_commercial_breaks_enabled, # Redundant, but kept for clarity
                commercial_breaks_count=job_commercial_breaks_count,       # Redundant, but kept for clarity
                commercial_breaks_min_duration_between_sec=job_commercial_breaks_min_duration_between_sec, # Redundant, but kept for clarity
                commercial_breaks_max_duration_between_sec=job_commercial_breaks_max_duration_between_sec, # Redundant, but kept for clarity
                commercial_breaks_min_silence_ms=job_commercial_breaks_min_silence_ms, # Redundant, but kept for clarity
                commercial_breaks_cue_phrases=job_commercial_breaks_cue_phrases, # Redundant, but kept for clarity
                commercial_breaks_audio_keys=job_commercial_breaks_audio_keys    # Redundant, but kept for clarity
            )

            # Fallback for poster path if OMDb fails but a project default exists
            if download_poster_val and not processed_poster_path:
                default_cover_art_filename = podcast_project_details.get('default_cover_art_path')
                if default_cover_art_filename:
                    # We need the absolute path to this file. Assuming it's in the configured COVER_ART_FOLDER
                    # This requires run_podcast_job to know about that folder config. For now, we construct it.
                    cover_art_folder = os.path.join(_SCRIPT_DIR, 'assets', 'cover_art')
                    processed_poster_path = os.path.join(cover_art_folder, default_cover_art_filename)
                    logger.info(f"OMDb poster failed or was disabled, using default project cover art: {processed_poster_path}")

            if final_audio:
                output_mp3_path = f"{output_path_prefix}.mp3"
                processor.export_audio(final_audio, output_mp3_path)
                logger.info(f"Job {job_id} completed. Output: {output_mp3_path}. Tags generated: {generated_tags}")

                # Record scheduled episode to local DB if Spreaker upload was attempted and successful (indicated by spreaker_episode_id)