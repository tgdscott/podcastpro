# view_local_episodes_db.py
import os
import sys
import logging
from datetime import datetime
import pytz

# Add parent dir to path to find db_manager
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db_manager # Assuming db_manager.py is in the same directory or accessible

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def display_pacific_time(utc_iso_str):
    if not utc_iso_str:
        return "N/A"
    try:
        dt_utc = datetime.fromisoformat(utc_iso_str.replace('Z', '+00:00')).astimezone(pytz.utc)
        pacific_tz = pytz.timezone('America/Los_Angeles')
        dt_pacific = dt_utc.astimezone(pacific_tz)
        return dt_pacific.strftime('%Y-%m-%d %I:%M:%S %p PT')
    except Exception:
        return utc_iso_str # Return original if parsing fails

def view_episodes():
    logger.info("Fetching all scheduled episodes from the local database...")
    db_manager.init_db() # Ensure DB is initialized
    
    episodes = db_manager.get_all_scheduled_episodes()

    if not episodes:
        print("No episodes found in the local database.")
        return

    print(f"\n--- Found {len(episodes)} Episode(s) in Local DB ---")
    for ep in episodes:
        print(f"  DB ID: {ep.get('id')}, Episode #: {ep.get('episode_number', 'N/A')}, Title: {ep.get('movie_title', 'N/A')}")
        print(f"    Spreaker ID: {ep.get('spreaker_episode_id', 'N/A')}")
        print(f"    Publish At (UTC): {ep.get('publish_at_utc_iso', 'N/A')}")
        print(f"    Publish At (Pacific): {display_pacific_time(ep.get('publish_at_utc_iso'))}")
        print(f"    MP3 Path: {ep.get('processed_mp3_path', 'N/A')}")
        print(f"    Poster Path: {ep.get('poster_path', 'N/A')}")
        print(f"    Show Notes Path: {ep.get('show_notes_path', 'N/A')}")
        print(f"    Tags: {ep.get('tags', 'N/A')}")
        print(f"    DB Record Created (UTC): {ep.get('created_at', 'N/A')}")
        print("-" * 20)

if __name__ == "__main__":
    view_episodes()