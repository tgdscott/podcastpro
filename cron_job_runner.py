import logging
import subprocess
import sys
import os
import time

# Add the parent directory to sys.path to allow imports from sibling modules
# This assumes cron_job_runner.py is in the same directory as db_manager.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import db_manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Path to the run_podcast_job.py script
JOB_RUNNER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_podcast_job.py")

def get_pending_jobs():
    """Fetches all jobs with 'pending' status from the database."""
    # Now uses the db_jobs module's function
    try:
        # db_manager.get_all_active_jobs() returns dicts, filter for 'pending' and extract IDs
        active_jobs = db_manager.get_all_active_jobs()
        return [job['id'] for job in active_jobs if job['status'] == 'pending']
    except Exception as e:
        logger.error(f"Error fetching pending jobs: {e}")
        return []

def main():
    logger.info("Cron job runner started. Checking for pending jobs...")
    
    # Initialize DB in case it hasn't been by app.py (e.g. if runner starts first)
    # or if this script is run independently for testing.
    db_manager.init_db()

    pending_job_ids = get_pending_jobs()

    if not pending_job_ids:
        logger.info("No pending jobs found.")
        return

    logger.info(f"Found {len(pending_job_ids)} pending job(s): {pending_job_ids}")

    for job_id in pending_job_ids:
        logger.info(f"Processing job ID: {job_id}")
        try:
            # It's important that run_podcast_job.py updates the status to 'processing'
            # as its first step to avoid this runner picking it up again if it runs frequently.
            # The run_podcast_job.py already does this.
            process = subprocess.run([sys.executable, JOB_RUNNER_SCRIPT, str(job_id)], capture_output=True, text=True, check=True)
            logger.info(f"Job {job_id} script stdout:\n{process.stdout}")
            if process.stderr:
                logger.warning(f"Job {job_id} script stderr:\n{process.stderr}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error running script for job ID {job_id}. Return code: {e.returncode}")
            logger.error(f"Stdout: {e.stdout}")
            logger.error(f"Stderr: {e.stderr}")
            # The run_podcast_job.py script should handle setting its own status to 'failed'
            # upon encountering an error.
        except Exception as e:
            logger.error(f"An unexpected error occurred while trying to run job {job_id}: {e}")
        
        # Optional: Add a small delay if you want to space out job executions
        # time.sleep(5) 

    logger.info("Cron job runner finished.")

if __name__ == "__main__":
    main()