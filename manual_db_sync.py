# manual_db_sync.py
import argparse
import os
import sys
# Add parent dir to path to find db_manager
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db_manager # Assuming db_manager.py is in the same directory or accessible
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def sync_episode_publish_time(spreaker_ep_id: str, new_publish_time_utc: str):
    """
    Updates the publish_at_utc_iso for a given Spreaker episode ID in the local database.
    """
    if not spreaker_ep_id or not new_publish_time_utc:
        logger.error("Spreaker Episode ID and New Publish Time (UTC ISO format) are required.")
        return

    # Basic validation for UTC ISO format (ends with Z, contains T)
    if not ('T' in new_publish_time_utc and new_publish_time_utc.endswith('Z')):
        logger.error(f"Invalid UTC ISO format for publish time: '{new_publish_time_utc}'. Expected format like 'YYYY-MM-DDTHH:MM:SSZ'.")
        print("Please use UTC ISO format, e.g., 2023-10-27T14:30:00Z")
        return

    logger.info(f"Attempting to update Spreaker Episode ID {spreaker_ep_id} in local DB to publish at {new_publish_time_utc}.")
    
    # This function will also update the 'created_at' field in the database to the current time.
    success = db_manager.update_episode_metadata_in_db( # This call is already correct
        spreaker_episode_id=spreaker_ep_id,
        new_publish_at_utc_iso=new_publish_time_utc
    )

    if success:
        logger.info(f"Successfully updated publish time for Spreaker Episode ID {spreaker_ep_id} in the local database.")
    else:
        logger.error(f"Failed to update publish time for Spreaker Episode ID {spreaker_ep_id}. Check logs. Ensure the episode ID exists in the local 'episodes' table.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manually sync Spreaker episode publish time in the local database.")
    parser.add_argument("spreaker_episode_id", type=str, help="The Spreaker Episode ID (e.g., 12345678).")
    parser.add_argument("new_publish_time_utc_iso", type=str, help="The new publish time in UTC ISO format (e.g., YYYY-MM-DDTHH:MM:SSZ).")
    
    args = parser.parse_args()
    
    db_manager.init_db() 
    
    sync_episode_publish_time(args.spreaker_episode_id, args.new_publish_time_utc_iso)
    print(f"\nCheck the application logs for confirmation or errors.")
    print(f"If successful, episode {args.spreaker_episode_id} in the local DB should now have publish time {args.new_publish_time_utc_iso}.")