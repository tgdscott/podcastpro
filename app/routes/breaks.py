import os
import tempfile
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
# Corrected import path
from ..utils.enhanced_audio_processor import analyze_audio_for_breaks

breaks_bp = Blueprint('breaks', __name__)

@breaks_bp.route('/preview', methods=['POST'])
def preview_breaks_route():
    if 'audio_file' not in request.files:
        return jsonify({"error": "No audio file part"}), 400
    
    file = request.files['audio_file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    filename = secure_filename(file.filename)
    # Use a temporary directory for safety
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = os.path.join(temp_dir, filename)
        file.save(temp_path)

        try:
            settings = {
                'silence_threshold': request.form.get('silence_threshold', -40, type=int),
                'min_silence_len': request.form.get('min_silence_len', 1500, type=int)
            }
            timestamps = analyze_audio_for_breaks(temp_path, settings)
            return jsonify({"breaks": timestamps})
        except Exception as e:
            current_app.logger.error(f"Error in preview_breaks_route: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500