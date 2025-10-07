#!/bin/bash

# GCU Management System - Google Cloud Deployment Script
# This script deploys the Streamlit app to Google App Engine

echo "🚀 Starting deployment of GCU Management System to Google Cloud..."

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

# Set the project (replace with your project ID)
echo "📋 Setting up Google Cloud project..."
read -p "Enter your Google Cloud Project ID: " PROJECT_ID
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required Google Cloud APIs..."
gcloud services enable appengine.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Deploy to App Engine
echo "🚀 Deploying to Google App Engine..."
gcloud app deploy app.yaml --version=v1 --promote

# Get the app URL
echo "✅ Deployment completed!"
echo "🌐 Your app is available at:"
gcloud app browse

echo "📊 To view logs:"
echo "   gcloud app logs tail -s default"

echo "🔄 To update the app:"
echo "   gcloud app deploy app.yaml"
