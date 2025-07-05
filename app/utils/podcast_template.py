"""
Defines the PodcastTemplate class for managing podcast template configurations.
"""
import json
import os # Import os for path operations
from typing import Dict, Optional # Import Optional

class PodcastTemplate:
    """Class to represent a podcast template configuration"""

    def __init__(self, template_config: Dict, template_dir: Optional[str] = None):
        """
        Initialize template from configuration

        Args:
            template_config: Dictionary containing template configuration
            template_dir: The directory where the template file was loaded from.
        """
        self.config = template_config
        self.template_dir = template_dir # Store the directory of the template file
        
        # New: ordered_segments is a list defining the sequence of audio parts
        self.ordered_segments = template_config.get('ordered_segments', [])
        
        # New: for defining background music that spans multiple segments
        self.background_music_beds = template_config.get('background_music_beds', [])

        # Legacy: For backward compatibility with old templates.
        # New templates should define timing within ordered_segments or background_music_beds.
        self.legacy_segments_dict = template_config.get('segments', {}) # Old dict format
        self.legacy_timing_dict = template_config.get('timing', {})     # Old timing dict

        self._raw_audio_files = template_config.get('audio_files', {}) # Store raw paths
        self.elevenlabs = template_config.get('elevenlabs', {
            'api_key': '',
            'voice_id': 'YOUR_ELEVENLABS_VOICE_ID_HERE', # Default voice ID
            'enabled': False
        })
        self.stop_word = template_config.get('stop_word', {
            'enabled': False,
            'word': ''
        })
        # NEW: Commercial Break Settings
        self.commercial_breaks = template_config.get('commercial_breaks', {
            'enabled': False,
            'break_count': 1, # Default to 1 commercial break
            'min_duration_between_breaks_sec': 300, # 5 minutes
            'max_duration_between_breaks_sec': 600, # 10 minutes
            'min_silence_for_break_ms': 1000, # 1 second of silence
            'cue_phrases': [], # e.g., ["commercial break", "ad time"]
            'commercial_audio_keys': [] # Keys from audio_files, e.g., ["ad_1", "ad_2"]
        })

    @property
    def audio_files(self) -> Dict[str, Optional[str]]:
        """Returns audio file paths, resolved relative to the template file's directory if they are relative."""
        if not self.template_dir: # If no template_dir, assume paths are absolute or already correctly relative to CWD
            return self._raw_audio_files
        
        resolved_files = {}
        for key, path_val in self._raw_audio_files.items():
            if path_val and not os.path.isabs(path_val):
                # Resolve relative path based on the template file's directory
                resolved_path = os.path.normpath(os.path.join(self.template_dir, path_val))
                resolved_files[key] = resolved_path
            else:
                resolved_files[key] = path_val # It's an absolute path or None
        return resolved_files

    @classmethod
    def from_files(cls, intro_file: str, background_file: str, transition_file: str,
                   outro_file: str, timing_config: Dict = None, elevenlabs_config: Dict = None,
                   stop_word_config: Dict = None, commercial_breaks_config: Dict = None): # Added commercial_breaks_config
        """
        Create template from individual audio files
        This now creates a default `ordered_segments` structure.
        """
        # These legacy timing values might be used by EnhancedAudioProcessor if ordered_segments is basic
        legacy_timing_values = {
            'background_start_offset': 1500, 'background_fade_duration': 3500,
            'transition_overlap': 3000, 'outro_overlap': 10000,
            'fade_in_duration': 2000, 'fade_out_duration': 2000
        } # Generic default voice, user should configure their own.
        default_elevenlabs = { 'api_key': '', 'voice_id': 'YOUR_ELEVENLABS_VOICE_ID_HERE', 'enabled': False }
        default_stop_word = { 'enabled': False, 'word': '' }
        # NEW: Default commercial break settings
        default_commercial_breaks = {
            'enabled': False,
            'break_count': 1,
            'min_duration_between_breaks_sec': 300,
            'max_duration_between_breaks_sec': 600,
            'min_silence_for_break_ms': 1000,
            'cue_phrases': [],
            'commercial_audio_keys': []
        }
        
        # Update legacy timing if provided, but new structure is preferred
        if timing_config: legacy_timing_values.update(timing_config)
        if elevenlabs_config: default_elevenlabs.update(elevenlabs_config)
        if stop_word_config: default_stop_word.update(stop_word_config)
        if commercial_breaks_config: default_commercial_breaks.update(commercial_breaks_config) # Update commercial breaks

        config = {
            'audio_files': {
                'intro_segment_audio': intro_file,
                'transition_segment_audio': transition_file,
                'outro_segment_audio': outro_file,
                'main_background_music': background_file # Example key for background music
            },
            'elevenlabs': default_elevenlabs,
            'stop_word': default_stop_word,
            'ordered_segments': [
                {"name": "Intro", "type": "file", "source_key": "intro_segment_audio", "role": "intro",
                 "processing": {"fade_in_ms": legacy_timing_values.get('fade_in_duration', 2000)}},
                {"name": "AI Intro", "type": "generated", "source_api": "elevenlabs", "role": "ai_intro",
                 "text_source_variable": "gui_default_ai_intro_text"}, # Placeholder for text source
                {"name": "Transition", "type": "file", "source_key": "transition_segment_audio", "role": "transition",
                 "processing": {"crossfade_with_previous_ms": legacy_timing_values.get('transition_overlap',3000)}},
                {"name": "Main Content", "type": "recording", "source_key": "user_recording", "role": "main_content"},
                {"name": "Outro", "type": "file", "source_key": "outro_segment_audio", "role": "outro",
                 "processing": {"crossfade_with_previous_ms": legacy_timing_values.get('outro_overlap',10000), 
                                "fade_out_ms": legacy_timing_values.get('fade_out_duration',2000)}}
            ],
            'background_music_beds': [
                {
                    "name": "Primary Background Music",
                    "source_key": "main_background_music",
                    "applies_to_roles": ["intro", "ai_intro", "transition"],
                    "start_offset_ms": legacy_timing_values.get('background_start_offset', 1500),
                    "end_offset_ms": -legacy_timing_values.get('background_fade_duration', 3500), # Negative from end
                    "volume_db": -12, # Example default
                    "fade_in_ms": legacy_timing_values.get('fade_in_duration',2000),
                    "fade_out_ms": legacy_timing_values.get('background_fade_duration',3500) # Fade out of music itself
                }
            ],
            'commercial_breaks': default_commercial_breaks, # NEW
            # Keep legacy fields for potential backward compatibility during transition
            # but new processor should primarily use ordered_segments and background_music_beds
            'segments': { # Legacy
                 'intro': {'type': 'intro', 'file': 'intro_segment_audio'},
                 'background': {'type': 'background', 'file': 'main_background_music'},
                 'ai_intro': {'type': 'generated', 'source': 'elevenlabs'},
                 'transition': {'type': 'transition', 'file': 'transition_segment_audio'},
                 'main_podcast': {'type': 'recording', 'source': 'user_recording'},
                 'outro': {'type': 'outro', 'file': 'outro_segment_audio'}
            },
            'timing': legacy_timing_values # Legacy
        }
        return cls(config)

    def save_to_file(self, filepath: str):
        """Save template configuration to JSON file"""
        # Ensure the commercial_breaks dictionary is part of the config to be saved
        with open(filepath, 'w', encoding='utf-8') as f: 
            json.dump(self.config, f, indent=2)

    @classmethod
    def load_from_file(cls, file_path):
        # First, we get the directory name from the full path
        template_dir = os.path.dirname(file_path)

        # Now, we open and load the JSON file
        with open(file_path, 'r') as f:
            config = json.load(f)

        # And finally, we return, passing both the loaded config and the directory
        return cls(config, template_dir=template_dir)