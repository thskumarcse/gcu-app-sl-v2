@echo off
REM GCU Management System - Google Cloud Deployment Script for Windows
REM This script deploys the Streamlit app to Google App Engine

echo 🚀 Starting deployment of GCU Management System to Google Cloud...

REM Check if gcloud CLI is installed
where gcloud >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Google Cloud CLI is not installed. Please install it first:
    echo    https://cloud.google.com/sdk/docs/install
    pause
    exit /b 1
)

REM Check if user is authenticated
gcloud auth list --filter=status:ACTIVE --format="value(account)" | findstr /R "." >nul
if %ERRORLEVEL% NEQ 0 (
    echo 🔐 Please authenticate with Google Cloud:
    gcloud auth login
)

REM Set the project
echo 📋 Setting up Google Cloud project...
set /p PROJECT_ID="Enter your Google Cloud Project ID: "
gcloud config set project %PROJECT_ID%

REM Enable required APIs
echo 🔧 Enabling required Google Cloud APIs...
gcloud services enable appengine.googleapis.com
gcloud services enable cloudbuild.googleapis.com

REM Deploy to App Engine
echo 🚀 Deploying to Google App Engine...
gcloud app deploy app.yaml --version=v1 --promote

REM Get the app URL
echo ✅ Deployment completed!
echo 🌐 Your app is available at:
gcloud app browse

echo 📊 To view logs:
echo    gcloud app logs tail -s default

echo 🔄 To update the app:
echo    gcloud app deploy app.yaml

pause
