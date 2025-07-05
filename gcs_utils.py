import os
import logging
from google.cloud import storage
from typing import Optional
from datetime import timedelta

logger = logging.getLogger(__name__)

# This global variable will be set by the app's config upon startup
GCS_BUCKET_NAME = None
storage_client = None

def _get_gcs_client() -> storage.Client:
    """Initializes and returns a singleton GCS client."""
    global storage_client
    if storage_client is None:
        logger.info("Initializing Google Cloud Storage client...")
        storage_client = storage.Client()
    return storage_client

def upload_file_to_gcs(source_file_path: str, destination_blob_name: str) -> Optional[str]:
    """
    Uploads a file to the GCS bucket.

    Args:
        source_file_path: Path to the file to upload.
        destination_blob_name: The name of the object in GCS (e.g., 'uploads/my_file.mp3').

    Returns:
        The GCS URI of the uploaded file (e.g., 'gs://bucket-name/path/to/file'), or None if upload fails.
    """
    if not GCS_BUCKET_NAME:
        logger.error("GCS_BUCKET_NAME is not configured. Cannot upload file.")
        return None
    
    try:
        client = _get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(destination_blob_name)

        logger.info(f"Uploading '{source_file_path}' to 'gs://{GCS_BUCKET_NAME}/{destination_blob_name}'...")
        blob.upload_from_filename(source_file_path)
        logger.info("Upload successful.")
        
        # Return the GCS URI, which is the standard way to reference objects internally.
        return f"gs://{GCS_BUCKET_NAME}/{destination_blob_name}"
    except Exception as e:
        logger.error(f"Failed to upload {source_file_path} to GCS: {e}", exc_info=True)
        return None

def generate_signed_url(blob_name: str, expiration_minutes: int = 60) -> Optional[str]:
    """
    Generates a signed URL to provide temporary public access to a GCS object.
    """
    if not GCS_BUCKET_NAME:
        logger.error("GCS_BUCKET_NAME is not configured. Cannot generate signed URL.")
        return None

    try:
        client = _get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)

        url = blob.generate_signed_url(version="v4", expiration=timedelta(minutes=expiration_minutes), method="GET")
        return url
    except Exception as e:
        logger.error(f"Failed to generate signed URL for {blob_name}: {e}", exc_info=True)
        return None

def delete_gcs_blob(blob_name: str) -> bool:
    """Deletes a blob from the GCS bucket."""
    if not GCS_BUCKET_NAME:
        logger.error("GCS_BUCKET_NAME is not configured. Cannot delete blob.")
        return False
    
    try:
        client = _get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        
        if blob.exists():
            logger.info(f"Deleting blob 'gs://{GCS_BUCKET_NAME}/{blob_name}'...")
            blob.delete()
            logger.info("Deletion successful.")
        else:
            logger.warning(f"Blob 'gs://{GCS_BUCKET_NAME}/{blob_name}' not found for deletion.")
        return True
    except Exception as e:
        logger.error(f"Failed to delete blob {blob_name} from GCS: {e}", exc_info=True)
        return False

def download_gcs_blob(source_blob_name: str, destination_file_path: str) -> bool:
    """
    Downloads a blob from the GCS bucket to a local file.

    Args:
        source_blob_name: The name of the object in GCS (e.g., 'uploads/my_file.mp3').
        destination_file_path: The local path where the file should be saved.

    Returns:
        True if download is successful, False otherwise.
    """
    if not GCS_BUCKET_NAME:
        logger.error("GCS_BUCKET_NAME is not configured. Cannot download blob.")
        return False

    try:
        client = _get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(source_blob_name)

        logger.info(f"Downloading 'gs://{GCS_BUCKET_NAME}/{source_blob_name}' to '{destination_file_path}'...")
        blob.download_to_filename(destination_file_path)
        logger.info("Download successful.")
        return True
    except Exception as e:
        logger.error(f"Failed to download blob {source_blob_name} from GCS: {e}", exc_info=True)
        return False