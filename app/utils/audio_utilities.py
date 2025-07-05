"""
Audio processing utility functions.
"""
import logging
from typing import List, Tuple
from pydub import AudioSegment
from pydub.silence import split_on_silence
import numpy as np

logger = logging.getLogger(__name__)

def audio_segment_to_whisper_input(audio: AudioSegment) -> np.ndarray:
    """Converts a pydub AudioSegment to a NumPy array suitable for Whisper."""
    audio = audio.set_channels(1).set_frame_rate(16000)
    samples = np.array(audio.get_array_of_samples()).astype(np.float32)
    # Normalize to [-1.0, 1.0]
    return samples / (2**(8 * audio.sample_width - 1))

def remove_long_pauses_from_segment(audio: AudioSegment, min_pause_duration_sec: float = 1.5, silence_thresh_db_offset: int = -16, keep_silence_ms: int = 500) -> AudioSegment:
    """Remove pauses/dead air longer than specified duration from an AudioSegment."""
    try:
        logger.info(f"Removing pauses > {min_pause_duration_sec}s...")
        min_pause_ms = int(min_pause_duration_sec * 1000)
        
        audio_chunks = split_on_silence(
            audio,
            min_silence_len=min_pause_ms,
            silence_thresh=audio.dBFS + silence_thresh_db_offset, # Relative to audio's dBFS
            keep_silence=keep_silence_ms 
        )
        processed_audio = sum(audio_chunks, AudioSegment.empty()) # Efficient way to concatenate
        removed_time = len(audio) - len(processed_audio)
        if removed_time > 0:
            logger.info(f"Removed {removed_time}ms of long pauses.")
        else:
            logger.info("No long pauses found to remove or audio unchanged.")
        return processed_audio
    except Exception as e:
        logger.warning(f"Error removing pauses: {e}. Returning original audio.")
        return audio

def remove_segments_from_audio(audio: AudioSegment, segments_to_remove_ms: List[Tuple[int, int]]) -> AudioSegment:
    """Remove specified time segments (in ms) from an audio segment."""
    if not segments_to_remove_ms: return audio
    
    clean_audio = AudioSegment.empty(); last_end = 0
    for start_ms, end_ms in sorted(segments_to_remove_ms): # Ensure segments are sorted
        if start_ms > last_end: clean_audio += audio[last_end:start_ms]
        last_end = max(last_end, end_ms) # Avoid issues with overlapping removal segments
    if last_end < len(audio): clean_audio += audio[last_end:]
    
    logger.info(f"Audio segments removed: original {len(audio)}ms -> processed {len(clean_audio)}ms")
    return clean_audio if len(clean_audio) > 0 else audio # Return original if result is empty