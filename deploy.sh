#!/bin/bash
set -e

# ==============================================================================
# NEXUS CLOUD RUN DEPLOYMENT SCRIPT
# ==============================================================================
# Prerequisites:
# 1. Install Google Cloud SDK (gcloud)
# 2. Run `gcloud auth login`
# 3. Enable APIs: 
#    gcloud services enable run.googleapis.com cloudbuild.googleapis.com firestore.googleapis.com secretmanager.googleapis.com
# 
# Usage:
#   ./deploy.sh <GCP_PROJECT_ID> <REGION>
# ==============================================================================

if [ "$#" -ne 2 ]; then
    echo "Usage: ./deploy.sh <GCP_PROJECT_ID> <REGION>"
    echo "Example: ./deploy.sh my-nexus-project us-central1"
    exit 1
fi

PROJECT_ID=$1
REGION=$2
SERVICE_NAME="nexus-backend"

echo "Deploying NEXUS Backend to Google Cloud Run..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"

# Set project
gcloud config set project "$PROJECT_ID"

# Optional: Create Secret Manager secrets if they don't exist
# (You must add versions to these secrets manually via the GCP Console or CLI)
echo "Ensuring Secret Manager configuration exists..."
gcloud secrets describe gemini-api-key || gcloud secrets create gemini-api-key --replication-policy="automatic"
gcloud secrets describe github-token || gcloud secrets create github-token --replication-policy="automatic"

echo "IMPORTANT: Make sure you have added versions to the 'gemini-api-key' and 'github-token' secrets in GCP!"
echo "Waiting 5 seconds before proceeding..."
sleep 5

# Build and Deploy to Cloud Run
# We use --source to let Cloud Build automatically build the Dockerfile.
# Limits: 1 CPU, 512MB RAM, max 10 instances (protects against runaway costs)
# Concurrency: 80 (FastAPI async handles concurrency well)
echo "Deploying Cloud Run service..."
gcloud run deploy "$SERVICE_NAME" \
    --source backend/ \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 10 \
    --concurrency 80 \
    --timeout 300 \
    --set-env-vars="ENVIRONMENT=production,USE_MOCK_FIRESTORE=false,ALLOWED_ORIGINS=https://nexus-frontend-xxx.web.app" \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest,GITHUB_TOKEN=github-token:latest"

echo "======================================================"
echo "DEPLOYMENT COMPLETE"
echo "======================================================"
echo "Next steps:"
echo "1. Get the generated backend URL from the output above."
echo "2. Update your frontend's .env NEXT_PUBLIC_API_URL to point to this backend."
echo "3. Update the ALLOWED_ORIGINS environment variable in Cloud Run with your real frontend URL."
echo "   gcloud run services update $SERVICE_NAME --update-env-vars ALLOWED_ORIGINS=https://your-real-frontend-url.com"
