@echo off
REM Deploy script for GCU App with proper secrets handling

echo 🚀 Deploying GCU App to Google Cloud...

REM Check if secrets.toml exists
if not exist ".streamlit\secrets.toml" (
    echo ❌ Error: .streamlit\secrets.toml not found!
    echo Please ensure your secrets.toml file is in the .streamlit directory.
    pause
    exit /b 1
)

echo ✅ Found secrets.toml file

REM Deploy to App Engine
echo 📦 Deploying to App Engine...
gcloud app deploy app.yaml --quiet

if %ERRORLEVEL% EQU 0 (
    echo ✅ Deployment successful!
    echo 🌐 Your app is available at:
    gcloud app browse
) else (
    echo ❌ Deployment failed. Check the logs above for details.
    pause
    exit /b 1
)

pause

