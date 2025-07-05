from app.utils.enhanced_audio_processor import EnhancedAudioProcessor
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json

@require_http_methods(["POST"])
def run_audio_processing_job(request):
    """
    API endpoint to trigger an audio processing job.
    Expects a JSON body with an 'audio_path'.
    """
    try:
        data = json.loads(request.body)
        audio_file_path = data.get('audio_path')

        if not audio_file_path:
            return JsonResponse({'status': 'error', 'message': 'Audio path is required.'}, status=400)

        # Assuming analyze_audio_for_breaks is part of the EnhancedAudioProcessor or uses it
        # For this task, we only modify the import statement.
        # Original code didn't show `analyze_audio_for_breaks` being called via EnhancedAudioProcessor instance.
        # If it was meant to be, that's a separate change beyond the import path correction.
        # As per instructions, only correcting the import.
        # result = EnhancedAudioProcessor.analyze_audio_for_breaks(audio_file_path) # Example if it was a static method
        # processor = EnhancedAudioProcessor(audio_file_path)
        # result = processor.analyze_audio_for_breaks() # Example if it was an instance method
        
        # Since analyze_audio_for_breaks is not defined in the provided snippet and not explicitly tied
        # to EnhancedAudioProcessor in the original code, we keep it as is, only fixing the import.
        # This implies analyze_audio_for_breaks might be a local function or imported from elsewhere.
        result = analyze_audio_for_breaks(audio_file_path) 

        return JsonResponse({'status': 'success', 'data': result}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON payload.'}, status=400)
    except FileNotFoundError:
        return JsonResponse({'status': 'error', 'message': f'Audio file not found at {audio_file_path}.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'An unexpected error occurred: {str(e)}'}, status=500)