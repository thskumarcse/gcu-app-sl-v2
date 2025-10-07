#!/usr/bin/env python3
"""
Test script to verify production mode configuration
"""
import os
import sys

# Set production mode
os.environ['DEV_MODE'] = 'False'

# Add current directory to path
sys.path.insert(0, '.')

def test_imports():
    """Test if all modules can be imported"""
    try:
        print("Testing imports...")
        
        # Test main imports
        import streamlit as st
        print("✅ Streamlit imported successfully")
        
        from streamlit_option_menu import option_menu
        print("✅ streamlit-option-menu imported successfully")
        
        import utility
        print("✅ utility module imported successfully")
        
        import login
        print("✅ login module imported successfully")
        
        # Test HR modules
        import hr_attendance
        print("✅ hr_attendance imported successfully")
        
        import hr_feedback
        print("✅ hr_feedback imported successfully")
        
        # Test exam modules
        import exam_transcript
        print("✅ exam_transcript imported successfully")
        
        import exam_marksheet
        print("✅ exam_marksheet imported successfully")
        
        import exam_admitcard
        print("✅ exam_admitcard imported successfully")
        
        import exam_results
        print("✅ exam_results imported successfully")
        
        import exam_results_all
        print("✅ exam_results_all imported successfully")
        
        # Test mentoring modules
        import mentoring_assign
        print("✅ mentoring_assign imported successfully")
        
        import mentoring_mentoring
        print("✅ mentoring_mentoring imported successfully")
        
        import mentoring_reports
        print("✅ mentoring_reports imported successfully")
        
        print("\n🎉 All imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_production_mode():
    """Test production mode configuration"""
    print("\nTesting production mode...")
    
    # Import main module
    import main
    
    # Check if DEV_MODE is False
    if hasattr(main, 'DEV_MODE'):
        if main.DEV_MODE == False:
            print("✅ DEV_MODE is correctly set to False for production")
            return True
        else:
            print("❌ DEV_MODE is not set to False")
            return False
    else:
        print("❌ DEV_MODE not found in main module")
        return False

def test_environment_variables():
    """Test environment variables"""
    print("\nTesting environment variables...")
    
    # Check if DEV_MODE environment variable is set
    dev_mode = os.getenv('DEV_MODE', 'Not Set')
    print(f"DEV_MODE environment variable: {dev_mode}")
    
    if dev_mode == 'False':
        print("✅ DEV_MODE environment variable correctly set to False")
        return True
    else:
        print("❌ DEV_MODE environment variable not set correctly")
        return False

if __name__ == "__main__":
    print("🚀 Testing GCU Management System for Production Deployment")
    print("=" * 60)
    
    # Run tests
    import_success = test_imports()
    production_success = test_production_mode()
    env_success = test_environment_variables()
    
    print("\n" + "=" * 60)
    print("📊 Test Results:")
    print(f"Imports: {'✅ PASS' if import_success else '❌ FAIL'}")
    print(f"Production Mode: {'✅ PASS' if production_success else '❌ FAIL'}")
    print(f"Environment Variables: {'✅ PASS' if env_success else '❌ FAIL'}")
    
    if all([import_success, production_success, env_success]):
        print("\n🎉 All tests passed! Ready for production deployment.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please fix issues before deployment.")
        sys.exit(1)
