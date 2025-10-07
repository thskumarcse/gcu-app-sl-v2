# Google Cloud Setup Guide for GCU Management System

## 🔐 Google Sheets API Configuration

Your application uses Google Sheets API for data storage. Here's how to configure it for Google Cloud deployment:

### Current Configuration
- **Service Account**: `gcu-app-sl@mk-resources.iam.gserviceaccount.com`
- **Project ID**: `mk-resources`
- **Sheet ID**: `1OJUZFb-vDVvn29PQ9h1CG9v3qQ9cm2vq53EfuR4pKSc`

### For Google Cloud Deployment

#### Option 1: Use Google Cloud Secret Manager (Recommended)

1. **Create a secret in Google Cloud Secret Manager:**
   ```bash
   gcloud secrets create gcu-app-secrets --data-file=secrets.json
   ```

2. **Update app.yaml to use Secret Manager:**
   ```yaml
   env_variables:
     GOOGLE_APPLICATION_CREDENTIALS: "/app/credentials.json"
   ```

3. **Grant access to the secret:**
   ```bash
   gcloud secrets add-iam-policy-binding gcu-app-secrets \
     --member="serviceAccount:YOUR_PROJECT@appspot.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   ```

#### Option 2: Use Environment Variables

1. **Convert secrets.toml to environment variables in app.yaml:**
   ```yaml
   env_variables:
     GCP_SERVICE_ACCOUNT_TYPE: "service_account"
     GCP_SERVICE_ACCOUNT_PROJECT_ID: "mk-resources"
     GCP_SERVICE_ACCOUNT_PRIVATE_KEY_ID: "5441453dc96ebf9a74ac32e543502ddfb3345124"
     GCP_SERVICE_ACCOUNT_PRIVATE_KEY: "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCStfug+ysl8W1s..."
     GCP_SERVICE_ACCOUNT_CLIENT_EMAIL: "gcu-app-sl@mk-resources.iam.gserviceaccount.com"
     GCP_SERVICE_ACCOUNT_CLIENT_ID: "114452009893894748638"
     GCP_SERVICE_ACCOUNT_AUTH_URI: "https://accounts.google.com/o/oauth2/auth"
     GCP_SERVICE_ACCOUNT_TOKEN_URI: "https://oauth2.googleapis.com/token"
     GCP_SERVICE_ACCOUNT_AUTH_PROVIDER_X509_CERT_URL: "https://www.googleapis.com/oauth2/v1/certs"
     GCP_SERVICE_ACCOUNT_CLIENT_X509_CERT_URL: "https://www.googleapis.com/robot/v1/metadata/x509/gcu-app-sl%40mk-resources.iam.gserviceaccount.com"
     GCP_SERVICE_ACCOUNT_UNIVERSE_DOMAIN: "googleapis.com"
     MY_SECRETS_SHEET_ID: "1OJUZFb-vDVvn29PQ9h1CG9v3qQ9cm2vq53EfuR4pKSc"
   ```

### Required Google Cloud APIs

Enable these APIs in your Google Cloud project:

```bash
gcloud services enable sheets.googleapis.com
gcloud services enable drive.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable appengine.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### Service Account Permissions

Ensure your service account has these roles:
- **Google Sheets API**: Editor access to the specific spreadsheet
- **Google Drive API**: Access to the spreadsheet file
- **Secret Manager**: Secret Accessor (if using Secret Manager)

### Testing the Configuration

1. **Test locally with environment variables:**
   ```bash
   set DEV_MODE=False
   set GCP_SERVICE_ACCOUNT_TYPE=service_account
   # ... set other variables
   streamlit run main.py
   ```

2. **Test Google Sheets connection:**
   ```python
   from utility import connect_gsheet
   client = connect_gsheet()
   print("✅ Google Sheets connection successful")
   ```

## 🚀 Deployment Steps

1. **Update app.yaml with your project settings**
2. **Deploy using the provided scripts:**
   ```bash
   # Windows
   deploy.bat
   
   # Linux/Mac
   ./deploy.sh
   ```

3. **Or deploy manually:**
   ```bash
   gcloud app deploy app.yaml --version=v1 --promote
   ```

## 🔧 Troubleshooting

### Common Issues:

1. **Authentication Error**: Check service account permissions
2. **Sheet Access Denied**: Verify sheet sharing with service account email
3. **Secret Manager Access**: Ensure proper IAM roles are assigned
4. **Environment Variables**: Check variable names and values

### Debug Commands:

```bash
# Check deployment logs
gcloud app logs tail -s default

# Check service account permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID

# Test Google Sheets API
gcloud auth application-default print-access-token
```

## 📋 Pre-Deployment Checklist

- [x] Google Sheets API credentials configured
- [x] Service account has proper permissions
- [x] Required Google Cloud APIs enabled
- [x] Environment variables set correctly
- [x] app.yaml configured for production
- [x] Dependencies verified
- [x] File paths reviewed
- [x] Authentication system tested
