"""
Clients for interacting with external APIs: OMDb, Google Gemini, ElevenLabs.
"""
import os
import re
import requests
import logging
import tempfile
from typing import Optional, Tuple, List
from datetime import datetime
from pydub import AudioSegment

try:
    from spellchecker import SpellChecker
except ImportError:
    SpellChecker = None

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import elevenlabs
except ImportError:
    elevenlabs = None

class OMDbClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def set_api_key(self, api_key: str):
        self.api_key = api_key

    def search_movie_poster(self, movie_title: str) -> Tuple[Optional[str], Optional[str]]:
        if not self.api_key:
            logger.warning("OMDb API key not set.")
            return None, movie_title # Return original title if API key is missing
        if not movie_title:
            logger.warning("No movie title provided for OMDb search.")
            return None, None
        
        final_search_title = movie_title.strip()
        original_title_for_return = final_search_title # Keep a copy before potential modification
        year_match = re.match(r'^(.*?)\s*\((\d{4})\)$', final_search_title)
        if year_match: final_search_title = year_match.group(1).strip()

        base_url = "https://www.omdbapi.com/"
        current_year = datetime.now().year
        years_to_try = [str(current_year), str(current_year - 1), str(current_year - 2)]

        for year_to_attempt in years_to_try:
            params = {'apikey': self.api_key, 't': final_search_title, 'y': year_to_attempt, 'plot': 'long', 'r': 'json'}
            try:
                logger.info(f"OMDb search: Title='{final_search_title}', Year='{year_to_attempt}'")
                response = requests.get(base_url, params=params); response.raise_for_status()
                data = response.json()
                if data.get('Response') == 'True' and data.get('Poster') and data['Poster'] != 'N/A':
                    return data['Poster'], final_search_title # Return found poster and the title used for search
            except requests.exceptions.RequestException as e:
                logger.error(f"OMDb API error during search for '{final_search_title}' (year: {year_to_attempt}): {e}")
        logger.warning(f"OMDb search failed for '{final_search_title}' across attempted years.")
        return None, original_title_for_return # Return None for poster, and the title that was searched

class GeminiClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.model = None
        if self.api_key and genai:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-2.0-flash')
                logger.info("Gemini client initialized successfully.")
            except Exception as e:
                logger.warning(f"Google Gemini initialization failed: {e}")
                self.model = None
        elif not genai:
            logger.warning("Google Generative AI SDK not installed.")

    def generate_content(self, transcript_text: str, episode_title: str, episode_movie_title: Optional[str] = None) -> Tuple[Optional[str], List[str]]:
        if not self.model: logger.warning("Gemini model not available."); return None, []
        
        full_ep_title = f"{episode_title}" + (f": {episode_movie_title}" if episode_movie_title else "")
        prompt = f"""You are an assistant for the "Cinema IRL" podcast.
For the episode titled "{full_ep_title}", based on the following transcript:
Transcript:
---
{transcript_text}
---
Please provide:
1. A concise and engaging episode introduction (50-150 words) for the podcast's show notes.
2. A list of 10-20 SEO-optimized tags (each tag 30 characters or less).
Format your response as follows:
SUMMARY:
[Your summary here]
TAGS:
[tag1, tag2, tag3, ...]"""
        try:
            response = self.model.generate_content(prompt)
            text_content = response.text.strip()
            summary_match = re.search(r"SUMMARY:\s*(.*?)\s*TAGS:", text_content, re.DOTALL | re.IGNORECASE)
            tags_match = re.search(r"TAGS:\s*(.*)", text_content, re.DOTALL | re.IGNORECASE)
            summary = summary_match.group(1).strip() if summary_match else None
            tags_str = tags_match.group(1).strip() if tags_match else ""
            tags_list = [tag.strip() for tag in tags_str.split(',') if tag.strip() and len(tag.strip()) <= 30][:20]
            if not summary: logger.warning("Gemini: Could not parse summary.")
            if not tags_list: logger.warning("Gemini: Could not parse tags.")
            return summary, tags_list
        except Exception as e: logger.error(f"Gemini content generation error: {e}", exc_info=True); return None, []

class ElevenLabsClient:
    def __init__(self, api_key: Optional[str] = None):
        self.client = None
        if api_key and elevenlabs:
            try:
                self.client = elevenlabs.ElevenLabs(api_key=api_key)
                logger.info("ElevenLabs client initialized successfully.")
            except Exception as e:
                logger.warning(f"ElevenLabs client initialization failed: {e}")
        elif not elevenlabs:
            logger.warning("ElevenLabs SDK not installed.")

    def generate_audio(self, text: str, voice_id: str) -> Optional[AudioSegment]:
        if not self.client: logger.warning("ElevenLabs client not available."); return None
        try:
            audio_generator = self.client.text_to_speech.convert(voice_id=voice_id, text=text, model_id="eleven_monolingual_v1")
            audio_bytes = b''.join(audio_generator)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf: tf.write(audio_bytes); temp_path = tf.name
            audio = AudioSegment.from_mp3(temp_path); os.unlink(temp_path)
            return audio
        except Exception as e: logger.error(f"ElevenLabs audio generation error: {e}"); return None