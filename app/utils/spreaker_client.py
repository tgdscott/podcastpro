"""
Client for interacting with the Spreaker API.
"""
import os
import requests
import logging
from typing import Optional, Tuple, List
from datetime import datetime, timedelta
import pytz
# Import db_manager to access schedule configuration
import db_manager # Assuming db_manager.py is in the same directory or accessible


logger = logging.getLogger(__name__)

class SpreakerClient:
    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token

    def set_api_token(self, api_token: str):
        self.api_token = api_token

    def calculate_next_publish_time(self, podcast_timezone_str_override: Optional[str] = None) -> Optional[str]:
        """
        Calculates the next publish time based on the user-defined schedule
        stored in the database. Returns it as UTC ISO string (ending with 'Z').
        Can be overridden by podcast_timezone_str_override.
        """
        try:
            schedule_config = db_manager.get_schedule_config()
            if not schedule_config:
                logger.error("Spreaker scheduling failed: No schedule configuration found in DB.")
                return None
            
            # TODO: Get this from podcast settings. Defaulting to 'America/Los_Angeles' for now.
            # Use override if provided, else from schedule_config (which itself might be a global default or future podcast-specific)
            podcast_local_timezone_str = podcast_timezone_str_override or schedule_config.get('podcast_timezone', 'America/Los_Angeles')
            
            local_tz = pytz.timezone(podcast_local_timezone_str)
            logger.info(f"SpreakerClient: Using timezone '{podcast_local_timezone_str}' for 'Next Available Slot' calculation.")
            utc_tz = pytz.utc
            now_local = datetime.now(local_tz)

            publish_time_local_str = schedule_config.get('publish_time_local', '05:00') # Expects HH:MM
            try:
                publish_hour, publish_minute = map(int, publish_time_local_str.split(':'))
            except ValueError:
                logger.error(f"Invalid publish_time_local format '{publish_time_local_str}' in schedule_config. Using 05:00.")
                publish_hour, publish_minute = 5, 0

            last_scheduled_utc_iso = db_manager.get_latest_scheduled_publish_time()
            # search_start_dt_local will be determined below

            if last_scheduled_utc_iso: # This is UTC
                try:
                    normalized_iso_str = last_scheduled_utc_iso.replace('Z', '+00:00')
                    dt_object = datetime.fromisoformat(normalized_iso_str)
                    if dt_object.tzinfo is None or dt_object.utcoffset() is None:
                        last_publish_utc = utc_tz.localize(dt_object) # Assume UTC if naive
                    else:
                        last_publish_utc = dt_object.astimezone(utc_tz)
                    last_publish_local = last_publish_utc.astimezone(local_tz)
                    # Start searching from the day after the last scheduled episode
                    search_start_dt_local = (last_publish_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                except ValueError as ve:
                    logger.warning(f"Could not parse last_scheduled_utc_iso ('{last_scheduled_utc_iso}') from DB: {ve}. Starting search from now.")
            else: # No last scheduled, start from now_local
                search_start_dt_local = now_local

            # Ensure we are not scheduling in the past relative to now + a small buffer (e.g., 1 hour)
            min_schedule_time_local = now_local + timedelta(hours=1)
            search_start_dt_local = max(search_start_dt_local, min_schedule_time_local)
            candidate_dt = search_start_dt_local # Start with a datetime object

            if schedule_config.get('schedule_type') == 'weekly':
                days_of_week_str = schedule_config.get('days_of_week', '0,2,4') # Default M/W/F
                target_weekdays = [int(d.strip()) for d in days_of_week_str.split(',') if d.strip().isdigit()]
                if not target_weekdays:
                    logger.error("No valid days_of_week in schedule_config. Cannot calculate schedule.")
                    return None

                # Adjust candidate_dt to the specified publish time on its current day
                candidate_dt = candidate_dt.replace(hour=publish_hour, minute=publish_minute, second=0, microsecond=0)
                
                # If this time is already past for today (or before min_schedule_time_pacific), move to next day before starting loop
                if candidate_dt < search_start_dt_local :
                     candidate_dt = (search_start_dt_local + timedelta(days=1)).replace(hour=publish_hour, minute=publish_minute, second=0, microsecond=0)

                for _ in range(366): # Search up to a year
                    if candidate_dt.weekday() in target_weekdays:
                        target_dt_utc = candidate_dt.astimezone(utc_tz)
                        return target_dt_utc.isoformat().replace('+00:00', 'Z')
                    candidate_dt += timedelta(days=1)
                logger.error("Could not find a valid weekly schedule slot within the next year.")
                return None
            # TODO: Implement 'monthly' schedule_type if needed
            else:
                logger.error(f"Unsupported schedule_type: {schedule_config.get('schedule_type')}")
                return None
        except Exception as e:
            logger.error(f"Error calculating next publish time: {e}", exc_info=True)
            return None

    def upload_episode(self, file_path: str, show_id: str, title: str, 
                       description: str, publish_at_utc_iso: Optional[str] = None,
                       image_file_path: Optional[str] = None, tags: Optional[List[str]] = None,
                       season_number_str: Optional[str] = None,
                       episode_number_str: Optional[str] = None,
                       transcript_url: Optional[str] = None,
                       force_draft: bool = False) -> Tuple[bool, str]:
        if not self.api_token:
            return False, "❌ Spreaker API token not set."
        logger.info(f"SpreakerClient: Attempting upload with API token ending with '...{self.api_token[-8:] if self.api_token else 'N/A'}'")

        spreaker_api_url = f"https://api.spreaker.com/v2/shows/{show_id}/episodes"
        headers = {"Authorization": f"Bearer {self.api_token}"}
        data = {"title": title} 

        if publish_at_utc_iso: # Explicit schedule time
            # Use 'auto_published_at' for scheduling new uploads as per Spreaker's POST example
            data["auto_published_at"] = publish_at_utc_iso
            logger.info(f"Spreaker: Scheduling '{title}' for {publish_at_utc_iso}.")
        elif force_draft: # Explicitly told to make it a draft
            data["auto_publish"] = "false"
            # Do not set publish_at if it's meant to be a pure draft
            logger.info(f"Spreaker: Saving '{title}' as DRAFT because scheduling failed or was forced.")
        else: # No schedule time, not forced draft -> This case should ideally not be hit if we always schedule or draft.
            data["auto_publish"] = "true"
            logger.info(f"Spreaker: Publishing '{title}' immediately.")

        if description: data["description"] = description
        if tags: data["tags"] = ",".join(tags); logger.info(f"Spreaker: Adding tags: {data['tags']}")
        
        if transcript_url: data["transcript_url"] = transcript_url
        if season_number_str:
            try: data["season_number"] = int(season_number_str)
            except ValueError: logger.warning(f"Invalid season number for Spreaker: {season_number_str}")
        if episode_number_str:
            try: data["episode_number"] = int(episode_number_str)
            except ValueError: logger.warning(f"Invalid episode number for Spreaker: {episode_number_str}")
        
        logger.info(f"Spreaker payload data (excluding files): {data}")
        # Add specific log for clarity on key fields being sent
        logger.info(f"Spreaker: Attempting to set Transcript URL: {data.get('transcript_url')}, Season: {data.get('season_number')}, Episode: {data.get('episode_number')}")
        
        files_payload = {}; media_file_handle = None; image_file_handle = None
        try:
            media_file_handle = open(file_path, 'rb'); files_payload['media_file'] = (os.path.basename(file_path), media_file_handle, 'audio/mpeg')
            if image_file_path and os.path.exists(image_file_path):
                img_mime = 'image/jpeg' if image_file_path.lower().endswith(('.jpg','.jpeg')) else 'image/png' if image_file_path.lower().endswith('.png') else 'application/octet-stream'
                image_file_handle = open(image_file_path, 'rb'); files_payload['image_file'] = (os.path.basename(image_file_path), image_file_handle, img_mime)
                logger.info(f"Spreaker: Including image: {image_file_path}")
            logger.info(f"Spreaker: Uploading {file_path} to show {show_id}..."); response = requests.post(spreaker_api_url, headers=headers, data=data, files=files_payload, timeout=900); response.raise_for_status()
            res_data = response.json()
            if res_data.get('response', {}).get('episode', {}).get('episode_id'):
                ep_id = res_data['response']['episode']['episode_id']; logger.info(f"Spreaker: Upload successful. Episode ID: {ep_id}"); return True, f"📢 Successfully uploaded to Spreaker. Episode ID: {ep_id}"
            logger.error(f"Spreaker: Unexpected response: {res_data}"); return False, f"⚠️ Spreaker upload OK but unexpected response: {response.text}"
        except requests.exceptions.HTTPError as e: logger.error(f"Spreaker HTTP Error: {e.response.status_code} - {e.response.text}"); return False, f"❌ Spreaker HTTP Error: {e.response.status_code} - {e.response.text}"
        except requests.exceptions.RequestException as e: logger.error(f"Spreaker Request Error: {e}"); return False, f"❌ Spreaker API Request Error: {e}"
        except Exception as e: logger.error(f"Spreaker upload error: {e}", exc_info=True); return False, f"❌ Unexpected Spreaker upload error: {e}"
        finally:
            if media_file_handle: media_file_handle.close()
            if image_file_handle: image_file_handle.close()

    def update_episode_details(self, episode_id: str,
                               title: Optional[str] = None,
                               description: Optional[str] = None,
                               publish_at_utc_iso: Optional[str] = None, # To reschedule
                              ###
                               auto_publish: Optional[bool] = None, # To change publish status
                               season_number_str: Optional[str] = None,
                               episode_number_str: Optional[str] = None,
                               tags_list: Optional[List[str]] = None # New: for tags
                               ) -> Tuple[bool, str]:
        if not self.api_token:
            return False, "❌ Spreaker API token not set."
        if not episode_id:
            return False, "❌ Spreaker episode ID is required for an update."

        spreaker_api_url = f"https://api.spreaker.com/v2/episodes/{episode_id}"
        headers = {"Authorization": f"Bearer {self.api_token}"}
        data = {}

        if title is not None: data["title"] = title
        if description is not None: data["description"] = description
        
        if publish_at_utc_iso is not None:
            data["publish_at"] = publish_at_utc_iso
            data["auto_publish"] = "false" # Explicitly schedule
            logger.info(f"Spreaker: Updating episode {episode_id} to schedule for {publish_at_utc_iso}.")
        elif auto_publish is not None: # If publish_at is not set, auto_publish controls draft/live
            data["auto_publish"] = "true" if auto_publish else "false"
            if not auto_publish and "publish_at" not in data : # Making it a draft
                logger.info(f"Spreaker: Updating episode {episode_id} to be a draft (auto_publish: false).")
            elif auto_publish:
                logger.info(f"Spreaker: Updating episode {episode_id} to publish immediately (auto_publish: true).")

        if season_number_str is not None:
            try: data["season_number"] = int(season_number_str)
            except ValueError: logger.warning(f"Invalid season number for Spreaker update: {season_number_str}")
        if episode_number_str is not None:
            try: data["episode_number"] = int(episode_number_str)
            except ValueError: logger.warning(f"Invalid episode number for Spreaker update: {episode_number_str}")
        if tags_list is not None: # Spreaker API expects a comma-separated string for tags
            data["tags"] = ",".join(tags_list)

        if not data: return False, "ℹ️ No details provided to update for Spreaker episode."

        logger.info(f"Spreaker: Updating episode {episode_id} with data: {data}")
        try:
            response = requests.put(spreaker_api_url, headers=headers, data=data, timeout=60)
            response.raise_for_status()
            logger.info(f"Spreaker: Successfully updated episode {episode_id}.")
            return True, f"📢 Successfully updated Spreaker episode {episode_id}."
        except requests.exceptions.HTTPError as e: logger.error(f"Spreaker HTTP Error updating episode {episode_id}: {e.response.status_code} - {e.response.text}"); return False, f"❌ Spreaker HTTP Error updating episode: {e.response.status_code} - {e.response.text}"
        except requests.exceptions.RequestException as e: logger.error(f"Spreaker Request Error updating episode {episode_id}: {e}"); return False, f"❌ Spreaker API Request Error updating episode: {e}"
        except Exception as e: logger.error(f"Spreaker update error for episode {episode_id}: {e}", exc_info=True); return False, f"❌ Unexpected Spreaker update error: {e}"
