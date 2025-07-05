from app import create_app
import argparse

# The application factory function is called by the Gunicorn server.
# Any initialization, like database setup, should be handled by a one-time script
# or a command, not at the module level.
app = create_app()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Podcast Automation Flask App")
    parser.add_argument('--port', type=int, default=5002, help="Port to run the web server on.")
    args = parser.parse_args()
    
    app.run(host='0.0.0.0', port=args.port, debug=True)