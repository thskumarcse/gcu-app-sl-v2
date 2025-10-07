#!/bin/bash

# GCU Management System - Google Cloud Run Deployment Script

echo "🚀 Starting deployment of GCU Management System to Google Cloud Run..."

# Set variables
PROJECT_ID="gcu-app-sl"
SERVICE_NAME="gcu-management-system"
REGION="asia-south1"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

# Check if gcloud CLI is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Google Cloud CLI is not installed. Please install it first:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "🔐 Please authenticate with Google Cloud:"
    gcloud auth login
fi

# Set the project
echo "📋 Setting up Google Cloud project..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required Google Cloud APIs..."
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable sheets.googleapis.com
gcloud services enable drive.googleapis.com

# Build and push the Docker image
echo "🐳 Building and pushing Docker image..."
gcloud builds submit --tag $IMAGE_NAME

# Deploy to Cloud Run
echo "🚀 Deploying to Google Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --port 8080 \
    --memory 2Gi \
    --cpu 2 \
    --min-instances 0 \
    --max-instances 10 \
    --timeout 3600 \
    --concurrency 80

# Get the service URL
echo "✅ Deployment completed!"
echo "🌐 Your app is available at:"
gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)"

echo "📊 To view logs:"
echo "   gcloud run services logs tail $SERVICE_NAME --region=$REGION"

echo "🔄 To update the app:"
echo "   gcloud builds submit --tag $IMAGE_NAME && gcloud run deploy $SERVICE_NAME --image $IMAGE_NAME --region=$REGION"
