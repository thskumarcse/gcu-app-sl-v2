#!/usr/bin/env python3
"""
Google App Engine entry point for Streamlit application
"""

import os
import sys
import subprocess
import threading
import time
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def main():
    """Main entry point for App Engine"""
    print("Starting GCU Management System...")
    
    # Set environment variables for production
    os.environ['DEV_MODE'] = 'False'
    os.environ['STREAMLIT_SERVER_PORT'] = '8080'
    os.environ['STREAMLIT_SERVER_ADDRESS'] = '0.0.0.0'
    os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'
    os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
    
    # Change to the app directory
    os.chdir(current_dir)
    
    try:
        # Import and run the main Streamlit app
        import main
        main.main()
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()