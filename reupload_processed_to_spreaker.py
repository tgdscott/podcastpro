import argparse
import logging
import os
import sys
from datetime import datetime
import pytz
from typing import Optional, List, Dict, Any
import re # For extracting Spreaker episode ID from message

# Add the parent directory to sys.path to allow imports from sibling modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import db_manager
from spreaker_client import SpreakerClient
from podcast_template import PodcastTemplate # For Spreaker Show ID from template if needed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_episode_details_for_reupload(episode_number_to_upload: str) -> Optional[Dict[str, Any]]:
    """Fetches all necessary details for an episode from the local DB."""
    conn = None
    try:
        conn = db_manager.sqlite3.connect(db_manager.DATABASE_PATH)
        conn.row_factory = db_manager.sqlite3.Row
        cursor = conn.cursor()
        # Fetch the latest entry for this episode number
        cursor.execute("""
            SELECT episode_number, movie_title, processed_mp3_path, poster_path, show_notes_path, tags
            FROM episodes
            WHERE episode_number = ?
            ORDER BY created_at DESC LIMIT 1
        """, (episode_number_to_upload,))
        data = cursor.fetchone()
        if data:
            logger.info(f"Found details for episode {episode_number_to_upload} in local DB: {dict(data)}")
            return dict(data)
        logger.warning(f"No details found for episode {episode_number_to_upload} in local DB for re-upload.")
        return None
    except db_manager.sqlite3.Error as e:
        logger.error(f"Database error fetching details for episode {episode_number_to_upload}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def main():
    parser = argparse.ArgumentParser(description="Re-upload a processed episode to Spreaker using stored metadata and a new schedule.")
    parser.add_argument("episode_number", help="The internal episode number to re-upload (e.g., '155').")
    # Schedule will be calculated automatically, but we could add overrides later if needed.
    # parser.add_argument("pacific_date", help="The desired publish date in YYYY-MM-DD format (Pacific Time).")
    # parser.add_argument("pacific_time", help="The desired publish time in HH:MM format (24-hour, Pacific Time).")
    parser.add_argument("--template_path", help="Path to a .json template file to fetch Spreaker Show ID if not set by env var.", default="config/spreaker.json")
    parser.add_argument("--ai_intro_text", help="Optional: Override AI intro text / description for the episode. If not provided, will try to use existing or generate default.")

    args = parser.parse_args()

    spreaker_api_token = os.environ.get('SPREAKER_API_TOKEN')
    spreaker_show_id_env = os.environ.get('SPREAKER_SHOW_ID')

    if not spreaker_api_token:
        logger.error("SPREAKER_API_TOKEN environment variable not set. Cannot proceed.")
        sys.exit(1)

    episode_data = get_episode_details_for_reupload(args.episode_number)
    if not episode_data:
        logger.error(f"Could not retrieve data for episode {args.episode_number} from the database. Cannot re-upload.")
        sys.exit(1)

    processed_mp3_path = episode_data.get("processed_mp3_path")
    movie_title = episode_data.get("movie_title", f"Episode {args.episode_number}")
    tags_str = episode_data.get("tags")
    tags_list = tags_str.split(',') if tags_str else []
    poster_path = episode_data.get("poster_path")
    # show_notes_path = episode_data.get("show_notes_path") # Not directly used in Spreaker upload payload, but description is.

    if not processed_mp3_path or not os.path.exists(processed_mp3_path):
        logger.error(f"Processed MP3 path for episode {args.episode_number} ('{processed_mp3_path}') not found or invalid. Cannot re-upload.")
        sys.exit(1)

    effective_spreaker_show_id = spreaker_show_id_env
    if not effective_spreaker_show_id:
        logger.info("SPREAKER_SHOW_ID env var not set, trying to load from template...")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_full_path = args.template_path if os.path.isabs(args.template_path) else os.path.join(script_dir, args.template_path)
        if os.path.exists(template_full_path):
            try:
                template_obj = PodcastTemplate.load_from_file(template_full_path)
                effective_spreaker_show_id = template_obj.config.get('gui_spreaker_show_id')
                if not effective_spreaker_show_id:
                    logger.error(f"Spreaker Show ID not found in template: {template_full_path}"); sys.exit(1)
                logger.info(f"Using Spreaker Show ID '{effective_spreaker_show_id}' from template: {template_full_path}")
            except Exception as e: logger.error(f"Error loading template {template_full_path}: {e}"); sys.exit(1)
        else: logger.error(f"SPREAKER_SHOW_ID env var not set and template file not found: {template_full_path}"); sys.exit(1)

    client = SpreakerClient(api_token=spreaker_api_token)
    
    # Calculate the next schedule time automatically
    publish_at_utc_iso = client.calculate_next_publish_time()
    if not publish_at_utc_iso:
        logger.error(f"Could not automatically calculate a schedule for episode {args.episode_number}. Re-upload aborted.")
        # Consider adding a fallback to upload as draft here if desired
        sys.exit(1)

    current_year = datetime.now().year
    calculated_season_number = str(current_year - 2023) # Base year 2024 for Season 1

    final_title = f"E{args.episode_number} - {movie_title} - What Would YOU Do?"
    description = args.ai_intro_text or f"Cinema IRL - Episode {args.episode_number} - {movie_title}" # Use provided or default

    logger.info(f"Attempting to re-upload '{final_title}' (EP: {args.episode_number}) from {processed_mp3_path} to Spreaker show ID {effective_spreaker_show_id}, scheduling for {publish_at_utc_iso}.")
    
    # Before re-uploading, you might want to delete the old entry for this episode_number from your local DB
    # to avoid UNIQUE constraint issues on publish_at_utc_iso if the new calculated time is the same as an old incorrect one.
    # Or, ensure the old Spreaker episode is deleted from Spreaker first.
    # For now, assuming old entries are handled (e.g., deleted from DB or Spreaker).

    success_spreaker, msg_spreaker = client.upload_episode(
        file_path=processed_mp3_path,
        show_id=effective_spreaker_show_id,
        title=final_title,
        description=description,
        publish_at_utc_iso=publish_at_utc_iso,
        tags=tags_list,
        season_number_str=calculated_season_number,
        episode_number_str=args.episode_number,
        image_file_path=poster_path,
        force_draft=False # We are explicitly scheduling
    )

    logger.info(f"Spreaker re-upload result: {success_spreaker} - {msg_spreaker}")

    if success_spreaker:
        spreaker_episode_id_match = re.search(r"Episode ID: (\S+)", msg_spreaker)
        new_spreaker_episode_id = spreaker_episode_id_match.group(1) if spreaker_episode_id_match else None
        if new_spreaker_episode_id:
            # Record this new upload in the local DB
            # Important: Ensure any old record for this episode_number is deleted or updated to avoid UNIQUE constraint on publish_at_utc_iso
            # For simplicity, we'll assume record_scheduled_episode handles new entries.
            # If an old entry for this episode_number exists with a *different* spreaker_episode_id, it should be removed.
            db_manager.record_scheduled_episode(
                args.episode_number, movie_title, new_spreaker_episode_id, publish_at_utc_iso,
                processed_mp3_path=processed_mp3_path, poster_path=poster_path,
                show_notes_path=episode_data.get("show_notes_path"), # Use stored show_notes_path
                tags_list=tags_list
            )
        else:
            logger.error("Could not extract new Spreaker Episode ID from success message after re-upload.")

if __name__ == "__main__":
    db_manager.init_db() # Ensure DB schema is up-to-date
    main()