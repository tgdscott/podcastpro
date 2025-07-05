import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or 'a-super-secret-key-that-you-should-change'
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    PROCESSED_OUTPUT_FOLDER = os.path.join(basedir, 'processed_output')
    TEMPLATES_FOLDER = os.path.join(basedir, 'app', 'templates')
    COVER_ART_FOLDER = os.path.join(basedir, 'app', 'static', 'assets', 'cover_art')
    ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a'}
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024 * 1024  # 1 GB upload limit

    # Google Cloud Storage bucket name
    GCS_BUCKET = os.environ.get('GCS_BUCKET_NAME') or 'podcast-pro-464303-media'

    @staticmethod
    def init_app(app):
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['PROCESSED_OUTPUT_FOLDER'], exist_ok=True)
        os.makedirs(app.config['COVER_ART_FOLDER'], exist_ok=True)