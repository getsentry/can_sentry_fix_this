#!/bin/bash

# Deploy script for Photo Frame Generator Cloud Function
# Make sure you have gcloud CLI installed and configured

set -e

# Configuration
FUNCTION_NAME="can-sentry-fix-this"
REGION="us-central1"
PROJECT_ID=$(gcloud config get-value project)
GCS_BUCKET_NAME="sentry-fix-this-bucket"

echo "🚀 Deploying Photo Frame Generator Cloud Function..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Function: $FUNCTION_NAME"

# Check if gcloud is configured
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: gcloud is not configured. Please run 'gcloud auth login' and 'gcloud config set project YOUR_PROJECT_ID'"
    exit 1
fi

# Check if GCS_BUCKET_NAME is set (we'll use Secret Manager for GEMINI_API_KEY)
if [ -z "$GCS_BUCKET_NAME" ]; then
    echo "Using default GCS bucket name: $GCS_BUCKET_NAME"
fi

# Verify that the GEMINI_API_KEY secret exists in Secret Manager
echo "🔐 Checking GEMINI_API_KEY secret in Secret Manager..."
if ! gcloud secrets describe GEMINI_API_KEY --project=$PROJECT_ID >/dev/null 2>&1; then
    echo "❌ Error: GEMINI_API_KEY secret not found in Secret Manager"
    echo "Please create the secret with: gcloud secrets create GEMINI_API_KEY --data-file=- <<< 'your_api_key_here'"
    exit 1
fi
echo "✅ GEMINI_API_KEY secret found in Secret Manager"

# Create GCS bucket if it doesn't exist
echo "📦 Checking/creating GCS bucket..."
gsutil ls -b gs://$GCS_BUCKET_NAME > /dev/null 2>&1 || gsutil mb -l $REGION gs://$GCS_BUCKET_NAME

# Make bucket publicly readable (for serving images)
gsutil iam ch allUsers:objectViewer gs://$GCS_BUCKET_NAME

echo "✅ GCS bucket ready: gs://$GCS_BUCKET_NAME"

# Deploy the cloud function
echo "🚀 Deploying cloud function..."
gcloud functions deploy $FUNCTION_NAME \
    --gen2 \
    --runtime=python313 \
    --region=$REGION \
    --source=. \
    --entry-point=process_photo \
    --trigger-http \
    --allow-unauthenticated \
    --memory=2GB \
    --timeout=540s \
    --service-account="gha-cloud-functions-deployment@jeffreyhung-test.iam.gserviceaccount.com" \
    --set-env-vars="GCS_BUCKET_NAME=$GCS_BUCKET_NAME" \
    --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest"

# Get the function URL
FUNCTION_URL=$(gcloud functions describe $FUNCTION_NAME --region=$REGION --gen2 --format="value(serviceConfig.uri)")

echo "✅ Deployment successful!"
echo "🌐 Function URL: $FUNCTION_URL"
echo ""
echo "📝 Next steps:"
echo "1. Update the frontend to use this URL: $FUNCTION_URL"
echo "2. Test the function by taking a photo on your mobile device"
echo "3. Check the GCS bucket for processed images"
echo ""
echo "🔧 To update the function, run this script again"
