import argparse
import logging
import os
import sys
from datetime import datetime
import pytz
from typing import Optional, Tuple, List # Import Optional and other typing hints

# Add the parent directory to sys.path to allow imports from sibling modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import db_manager
from spreaker_client import SpreakerClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_spreaker_episode_id_from_db(episode_number_to_fix: str) -> Optional[str]:
    """
    Fetches the Spreaker episode ID from the local 'episodes' table
    based on the podcast's internal episode number.
    """
    # Use db_manager.get_all_scheduled_episodes and filter
    all_episodes = db_manager.get_all_scheduled_episodes()
    for ep in all_episodes:
        if ep.get('episode_number') == episode_number_to_fix and ep.get('spreaker_episode_id'):
            logger.info(f"Found Spreaker ID {ep['spreaker_episode_id']} for episode number {episode_number_to_fix} in local DB.")
            return ep['spreaker_episode_id']
    logger.warning(f"No Spreaker ID found for episode number {episode_number_to_fix} in local DB.")
    return None

def main():
    parser = argparse.ArgumentParser(description="Reschedule an existing Spreaker episode and update local DB.")
    parser.add_argument("episode_number", help="The internal episode number to fix (e.g., '155').")
    parser.add_argument("pacific_date", help="The correct publish date in YYYY-MM-DD format (Pacific Time).")
    parser.add_argument("pacific_time", help="The correct publish time in HH:MM format (24-hour, Pacific Time).")
    parser.add_argument("--title", help="Optional: New title for the episode on Spreaker.")
    # Add --season and --new_episode_number_spreaker if needed for Spreaker's own numbering
    parser.add_argument("--tags", help="Optional: Comma-separated list of tags for the episode on Spreaker.")

    args = parser.parse_args()

    spreaker_api_token = os.environ.get('SPREAKER_API_TOKEN')
    if not spreaker_api_token:
        # Fallback to trying to get it from a template (less ideal for a utility script)
        # For simplicity, this script will require the env var.
        logger.error("SPREAKER_API_TOKEN environment variable not set. Cannot proceed.")
        sys.exit(1)

    spreaker_episode_id = get_spreaker_episode_id_from_db(args.episode_number)
    if not spreaker_episode_id:
        logger.error(f"Could not find a Spreaker episode ID for episode number {args.episode_number}. Cannot update Spreaker.")
        # You might still want to update/insert into local DB if the goal is to fix local records for future calculations
        # For now, we'll exit if we can't update Spreaker.
        sys.exit(1)

    try:
        pacific_tz = pytz.timezone('America/Los_Angeles')
        utc_tz = pytz.utc
        correct_pacific_dt_naive = datetime.strptime(f"{args.pacific_date} {args.pacific_time}", "%Y-%m-%d %H:%M")
        correct_pacific_dt_aware = pacific_tz.localize(correct_pacific_dt_naive)
        correct_utc_dt_aware = correct_pacific_dt_aware.astimezone(utc_tz)
        new_publish_at_utc_iso = correct_utc_dt_aware.isoformat().replace('+00:00', 'Z')
    except ValueError as e:
        logger.error(f"Invalid date/time format: {e}. Please use YYYY-MM-DD and HH:MM.")
        sys.exit(1)

    client = SpreakerClient(api_token=spreaker_api_token)
    
    logger.info(f"Attempting to update Spreaker episode ID {spreaker_episode_id} (for local ep {args.episode_number}) to schedule at {new_publish_at_utc_iso} (Pacific: {args.pacific_date} {args.pacific_time}).")
    
    success_spreaker, msg_spreaker = client.update_episode_details(
        episode_id=spreaker_episode_id,
        publish_at_utc_iso=new_publish_at_utc_iso,
        title=args.title, # Pass new title if provided
        tags_list=args.tags.split(',') if args.tags else None # Pass tags if provided
        # Pass other details like season/episode number if arguments are added
    )

    logger.info(f"Spreaker update result: {success_spreaker} - {msg_spreaker}")

    if success_spreaker:
        # If Spreaker update was successful, update the local DB metadata
        db_manager.update_episode_metadata_in_db(
            spreaker_episode_id=spreaker_episode_id,
            new_publish_at_utc_iso=new_publish_at_utc_iso,
            new_tags_list=args.tags.split(',') if args.tags else None
        )

if __name__ == "__main__":
    db_manager.init_db() # Ensure DB schema is up-to-date
    main()