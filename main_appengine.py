#!/usr/bin/env python3
"""
Main entry point for Google App Engine deployment
This file serves as the entry point for the Streamlit application on App Engine
"""

import os
import sys
import subprocess

def main():
    """Main entry point for App Engine"""
    # Set environment variables for production
    os.environ['DEV_MODE'] = 'False'
    os.environ['STREAMLIT_SERVER_PORT'] = '8080'
    os.environ['STREAMLIT_SERVER_ADDRESS'] = '0.0.0.0'
    os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'
    os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
    
    # Import and run the main Streamlit app
    try:
        import main
        main.main()
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
