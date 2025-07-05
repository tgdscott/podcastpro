import os
import logging
from flask import Flask, jsonify
from werkzeug.exceptions import BadRequest

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app(config_class=None):
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024 * 1024  # 1GB
    app.config['GCS_BUCKET'] = os.environ.get('GCS_BUCKET_NAME', 'podcast-pro-464303-media')
    app.config['ALLOWED_EXTENSIONS'] = {'mp3', 'wav', 'm4a'}
    
    # Set up directories
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['UPLOAD_FOLDER'] = os.path.join(basedir, '..', 'uploads')
    app.config['PROCESSED_OUTPUT_FOLDER'] = os.path.join(basedir, '..', 'processed_output')
    
    # Ensure directories exist
    for folder in [app.config['UPLOAD_FOLDER'], app.config['PROCESSED_OUTPUT_FOLDER']]:
        os.makedirs(folder, exist_ok=True)

    # Initialize GCS if available
    try:
        import gcs_utils
        gcs_utils.GCS_BUCKET_NAME = app.config['GCS_BUCKET']
    except ImportError:
        logger.warning("GCS utilities not available. File uploads will be local only.")

    # Health check endpoint
    @app.route('/health')
    def health_check():
        try:
            return jsonify({
                'status': 'healthy',
                'environment': 'cloud' if os.environ.get('INSTANCE_CONNECTION_NAME') else 'local'
            }), 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

    # Register blueprints with error handling
    try:
        from .views.submit2 import submit_bp
        from .views.admin import admin_bp
        
        app.register_blueprint(submit_bp)
        app.register_blueprint(admin_bp, url_prefix='/admin')
        
    except ImportError as e:
        logger.error(f"Failed to import blueprints: {e}")
        # Create minimal blueprint if imports fail
        from flask import Blueprint, render_template_string
        
        minimal_bp = Blueprint('minimal', __name__)
        
        @minimal_bp.route('/')
        def minimal_home():
            return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head><title>Podcast Automation</title></head>
            <body>
                <h1>Podcast Automation Platform</h1>
                <p>Service is running but some features may be unavailable.</p>
                <p><a href="/health">Health Check</a></p>
            </body>
            </html>
            ''')
        
        app.register_blueprint(minimal_bp)

    # Global error handlers
    @app.errorhandler(BadRequest)
    def handle_bad_request(e):
        logger.error(f"Bad Request: {e.description}")
        return jsonify(error=f"Bad Request: {e.description}"), 400

    @app.errorhandler(500)
    def handle_internal_error(e):
        logger.error(f"Internal Server Error: {e}")
        return jsonify(error="Internal server error occurred"), 500

    return app
