import os
from flask import Flask, jsonify
from werkzeug.exceptions import BadRequest

from config import Config
import db_manager
import gcs_utils

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize GCS Utility with the bucket name from config
    gcs_utils.GCS_BUCKET_NAME = app.config['GCS_BUCKET']
    if not gcs_utils.GCS_BUCKET_NAME:
        app.logger.warning("GCS_BUCKET_NAME is not set in the environment or config. File uploads will fail.")

    # Register blueprints
    from .views.submit import submit_bp
    from .views.admin import admin_bp
    from .views.podcasts import podcasts_bp
    from .views.settings import settings_bp
    from .views.templates import templates_bp

    app.register_blueprint(submit_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(podcasts_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(templates_bp)

    # Global error handler for bad requests (e.g., missing file in form)
    @app.errorhandler(BadRequest)
    def handle_bad_request(e):
        app.logger.error(f"Bad Request: {e.description}")
        return jsonify(error=f"Bad Request: {e.description}"), 400

    return app