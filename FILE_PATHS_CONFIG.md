# File Paths Configuration for Google Cloud Deployment

## 🚨 Issues Found

The application has several hardcoded file paths that need to be addressed for Google Cloud deployment:

### 1. Hardcoded Paths in `exam_transcript.py`

**Lines 623, 657, 659:**
```python
current_images_dir = os.path.join(os.getcwd(), "images")
logo_dir = os.path.join(os.getcwd(), "logo_dir")
logo_path = os.path.join(logo_dir, "logo.png")
```

**Issue**: `os.getcwd()` may not work correctly in Google App Engine.

### 2. Data File References in Notebooks

**Files with hardcoded `./data/` paths:**
- `2025_attendance_solver_chatgpt.ipynb`
- `2025_attendance_solver_fac.ipynb`
- `hr_attendance_backup.py`

**Issue**: These files reference local data directories that won't exist in production.

## 🔧 Solutions

### Option 1: Use Google Cloud Storage (Recommended)

1. **Upload data files to Google Cloud Storage:**
   ```bash
   gsutil cp -r data/ gs://your-bucket-name/data/
   gsutil cp -r images/ gs://your-bucket-name/images/
   gsutil cp -r logo_dir/ gs://your-bucket-name/logo_dir/
   ```

2. **Update code to use Cloud Storage:**
   ```python
   from google.cloud import storage
   
   def get_file_from_gcs(bucket_name, file_path):
       client = storage.Client()
       bucket = client.bucket(bucket_name)
       blob = bucket.blob(file_path)
       return blob.download_as_bytes()
   ```

### Option 2: Use Environment Variables for Paths

1. **Update `app.yaml`:**
   ```yaml
   env_variables:
     DATA_DIR: "/app/data"
     IMAGES_DIR: "/app/images"
     LOGO_DIR: "/app/logo_dir"
     OUTPUT_DIR: "/tmp/output"
   ```

2. **Update code to use environment variables:**
   ```python
   import os
   
   DATA_DIR = os.getenv('DATA_DIR', './data')
   IMAGES_DIR = os.getenv('IMAGES_DIR', './images')
   LOGO_DIR = os.getenv('LOGO_DIR', './logo_dir')
   OUTPUT_DIR = os.getenv('OUTPUT_DIR', './output')
   ```

### Option 3: Use Temporary Directories

For temporary files and outputs:
```python
import tempfile
import os

# Use system temp directory
temp_dir = tempfile.gettempdir()
output_dir = os.path.join(temp_dir, "gcu_output")
os.makedirs(output_dir, exist_ok=True)
```

## 📋 Required Changes

### 1. Update `exam_transcript.py`

Replace hardcoded paths:
```python
# Instead of:
current_images_dir = os.path.join(os.getcwd(), "images")
logo_dir = os.path.join(os.getcwd(), "logo_dir")

# Use:
current_images_dir = os.path.join(tempfile.gettempdir(), "images")
logo_dir = os.path.join(tempfile.gettempdir(), "logo_dir")
```

### 2. Update Data File References

For files that need data access:
```python
# Instead of:
df = pd.read_excel('./data/file.xlsx')

# Use:
data_dir = os.getenv('DATA_DIR', './data')
df = pd.read_excel(os.path.join(data_dir, 'file.xlsx'))
```

### 3. Update Output Paths

```python
# Instead of:
output_dir = './output'

# Use:
output_dir = os.getenv('OUTPUT_DIR', tempfile.gettempdir())
```

## 🚀 Google Cloud Storage Setup

### 1. Create Storage Bucket
```bash
gsutil mb gs://your-gcu-app-bucket
```

### 2. Upload Files
```bash
gsutil cp -r data/ gs://your-gcu-app-bucket/data/
gsutil cp -r images/ gs://your-gcu-app-bucket/images/
gsutil cp -r logo_dir/ gs://your-gcu-app-bucket/logo_dir/
```

### 3. Set Permissions
```bash
gsutil iam ch allUsers:objectViewer gs://your-gcu-app-bucket
```

## 📁 Recommended Directory Structure for Production

```
/app/
├── main.py
├── utility.py
├── *.py (all Python files)
├── data/ (if using local files)
├── images/ (if using local files)
├── logo_dir/ (if using local files)
└── /tmp/ (temporary files and outputs)
```

## ⚠️ Important Notes

1. **App Engine Limitations:**
   - Filesystem is read-only except for `/tmp`
   - Maximum file size: 32MB
   - No persistent storage between requests

2. **Best Practices:**
   - Use Cloud Storage for large files
   - Use `/tmp` for temporary files
   - Use environment variables for paths
   - Avoid hardcoded paths

3. **Testing:**
   - Test all file operations locally
   - Verify Cloud Storage access
   - Check temporary file cleanup

## 🔄 Migration Steps

1. **Identify all hardcoded paths**
2. **Choose storage solution (Cloud Storage recommended)**
3. **Update code to use dynamic paths**
4. **Test locally with environment variables**
5. **Deploy and verify file access**
6. **Monitor for file-related errors**

## 📊 File Access Patterns

- **Input Data**: Upload to Cloud Storage or use environment variables
- **Images**: Store in Cloud Storage, download to `/tmp` when needed
- **Output Files**: Generate in `/tmp`, optionally upload to Cloud Storage
- **Templates**: Store in Cloud Storage or include in deployment
