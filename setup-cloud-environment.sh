#!/bin/bash
# This script prepares the Google Cloud environment for the Podcast Pro application.
# It should only need to be run once.

set -e # Exit immediately if a command exits with a non-zero status.

# --- Configuration: Please verify these values ---
export PROJECT_ID="podcast-pro-464303"
export REGION="us-west1"
export SERVICE_NAME="podcast-pro-backend"
export SQL_INSTANCE_NAME="podcast-pro-db"
export DB_NAME="postgres"
export DB_USER="postgres"
export GCS_BUCKET="podcast-pro-464303-media"
export AR_REPO="podcast-pro-images"
export RUN_SERVICE_ACCOUNT_NAME="podcast-run-sa"
# --- End Configuration ---

echo "--- Setting project to $PROJECT_ID ---"
gcloud config set project $PROJECT_ID

echo "--- Enabling necessary Google Cloud APIs ---"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  storage.googleapis.com

echo "--- Generating secure passwords and keys ---"
export DB_PASSWORD=$(openssl rand -base64 32)
export FLASK_KEY=$(openssl rand -base64 32)

echo "--- Creating Artifact Registry repository: $AR_REPO ---"
gcloud artifacts repositories create $AR_REPO --repository-format=docker --location=$REGION --description="Docker repository for Podcast Pro" --quiet || echo "Repository $AR_REPO already exists."

echo "--- Creating GCS Bucket: $GCS_BUCKET ---"
# -l is location, -p is project, -b on is uniform bucket-level access
gcloud storage buckets create gs://$GCS_BUCKET --project=$PROJECT_ID --location=$REGION --uniform-bucket-level-access --quiet || echo "Bucket gs://$GCS_BUCKET already exists."

echo "--- Creating Cloud SQL instance: $SQL_INSTANCE_NAME ---"
echo "This may take several minutes..."
# Check if the instance already exists to avoid running the lengthy create command unnecessarily.
if ! gcloud sql instances describe $SQL_INSTANCE_NAME &>/dev/null; then
  # Note: Using a small tier for cost-effectiveness. Adjust if needed.
  gcloud sql instances create $SQL_INSTANCE_NAME \
    --database-version=POSTGRES_13 \
    --tier=db-g1-small \
    --region=$REGION \
    --root-password="$DB_PASSWORD"
else
    echo "SQL instance $SQL_INSTANCE_NAME already exists. Skipping creation."
fi

echo "--- Enabling IAM database authentication on the SQL instance ---"
gcloud sql instances patch $SQL_INSTANCE_NAME --database-flags=cloudsql.iam_authentication=on --quiet

echo "--- Creating secure secrets in Secret Manager ---"
echo -n "$DB_PASSWORD" | gcloud secrets create DB_PASS --data-file=- --replication-policy="automatic" --quiet || echo "Secret DB_PASS already exists."
echo -n "$FLASK_KEY" | gcloud secrets create FLASK_SECRET_KEY --data-file=- --replication-policy="automatic" --quiet || echo "Secret FLASK_SECRET_KEY already exists."

echo "--- Creating dedicated service account: $RUN_SERVICE_ACCOUNT_NAME ---"
gcloud iam service-accounts create $RUN_SERVICE_ACCOUNT_NAME \
  --display-name="Podcast App Cloud Run Service Account" --quiet || echo "Service account $RUN_SERVICE_ACCOUNT_NAME already exists."

echo "--- Granting your user account permission to deploy as the service account ---"
export GCLOUD_USER=$(gcloud config get-value account)
gcloud iam service-accounts add-iam-policy-binding "${RUN_SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --member="user:$GCLOUD_USER" \
    --role="roles/iam.serviceAccountUser" \
    --quiet

echo "--- Granting service account access to secrets ---"
gcloud secrets add-iam-policy-binding DB_PASS --member="serviceAccount:${RUN_SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" --role="roles/secretmanager.secretAccessor" --quiet
gcloud secrets add-iam-policy-binding FLASK_SECRET_KEY --member="serviceAccount:${RUN_SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" --role="roles/secretmanager.secretAccessor" --quiet

echo "--- Granting service account access to Cloud SQL ---"
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:${RUN_SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" --role="roles/cloudsql.client" --quiet

echo "--- Granting service account access to the GCS Bucket ---"
gcloud storage buckets add-iam-policy-binding gs://${GCS_BUCKET} \
    --member="serviceAccount:${RUN_SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin" --quiet

echo "✅ Environment setup complete!"
echo "You are now ready to build and deploy the application."