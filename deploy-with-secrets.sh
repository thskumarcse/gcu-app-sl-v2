#!/bin/bash

# Deploy script for GCU App with proper secrets handling
echo "🚀 Deploying GCU App to Google Cloud..."

# Check if secrets.toml exists
if [ ! -f ".streamlit/secrets.toml" ]; then
    echo "❌ Error: .streamlit/secrets.toml not found!"
    echo "Please ensure your secrets.toml file is in the .streamlit directory."
    exit 1
fi

echo "✅ Found secrets.toml file"

# Deploy to App Engine
echo "📦 Deploying to App Engine..."
gcloud app deploy app.yaml --quiet

if [ $? -eq 0 ]; then
    echo "✅ Deployment successful!"
    echo "🌐 Your app should be available at: https://$(gcloud config get-value project).appspot.com"
else
    echo "❌ Deployment failed. Check the logs above for details."
    exit 1
fi

