from pydub import AudioSegment
from pydub.silence import detect_silence

class EnhancedAudioProcessor:
    @staticmethod
    def analyze_audio_for_breaks(audio_file_path, settings):
        """
        Analyzes an audio file to find suitable break points based on silence.
        """
        print(f"--- Starting break analysis for: {audio_file_path} ---")

        silence_thresh = settings.get('silence_thresh', -40)
        min_silence_len = settings.get('min_silence_len', 1500)

        try:
            audio = AudioSegment.from_file(audio_file_path)
            silences = detect_silence(
                audio,
                min_silence_len=min_silence_len,
                silence_thresh=int(silence_thresh)
            )

            if not silences:
                return []

            timestamps = [((start + end) / 2) / 1000.0 for start, end in silences]
            print(f"--- Found {len(timestamps)} potential breaks at: {timestamps} ---")
            return timestamps
        except Exception as e:
            print(f"--- ERROR in analyze_audio_for_breaks: {e} ---")
            return []