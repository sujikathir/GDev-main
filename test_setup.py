#!/usr/bin/env python3
"""
Test script for GitHub Issue Analyzer
Verifies that all components are working correctly
"""

import sys
import os
import importlib
from pathlib import Path

def test_imports():
    """Test if all required modules can be imported"""
    print("🔍 Testing imports...")
    
    required_modules = [
        'fastapi',
        'uvicorn', 
        'openai',
        'streamlit',
        'requests',
        'pandas',
        'plotly',
        'pydantic',
        'dotenv'
    ]
    
    optional_modules = [
        'composio',
        'composio_openai',
        'langchain',
        'langchain_openai'
    ]
    
    # Test required modules
    failed_required = []
    for module in required_modules:
        try:
            importlib.import_module(module)
            print(f"✅ {module}")
        except ImportError:
            print(f"❌ {module}")
            failed_required.append(module)
    
    # Test optional modules
    available_optional = []
    for module in optional_modules:
        try:
            importlib.import_module(module)
            print(f"✅ {module} (optional)")
            available_optional.append(module)
        except ImportError:
            print(f"⚠️ {module} (optional, not available)")
    
    if failed_required:
        print(f"\n❌ Failed to import required modules: {', '.join(failed_required)}")
        return False
    
    print(f"\n✅ All required modules imported successfully")
    print(f"📦 Available optional modules: {', '.join(available_optional)}")
    return True

def test_env_file():
    """Test if .env file exists and has required keys"""
    print("\n🔍 Testing environment configuration...")
    
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ .env file not found")
        print("Please create a .env file with your API keys")
        return False
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    required_keys = ['OPENAI_API_KEY']
    optional_keys = ['COMPOSIO_API_KEY']
    
    missing_required = []
    for key in required_keys:
        if not os.getenv(key):
            missing_required.append(key)
        else:
            print(f"✅ {key}")
    
    if missing_required:
        print(f"❌ Missing required environment variables: {', '.join(missing_required)}")
        return False
    
    # Check optional keys
    for key in optional_keys:
        if os.getenv(key):
            print(f"✅ {key}")
        else:
            print(f"⚠️ {key} (optional, not set)")
    
    print("✅ Environment configuration looks good")
    return True

def test_api_imports():
    """Test if the API can be imported"""
    print("\n🔍 Testing API imports...")
    
    try:
        # Test importing the main API module
        sys.path.append('src')
        import main
        print("✅ API module imported successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import API module: {e}")
        return False

def test_streamlit_app():
    """Test if the Streamlit app can be imported"""
    print("\n🔍 Testing Streamlit app...")
    
    try:
        import streamlit_app
        print("✅ Streamlit app imported successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import Streamlit app: {e}")
        return False

def test_config():
    """Test if the config module works"""
    print("\n🔍 Testing configuration...")
    
    try:
        import config
        print("✅ Configuration module imported successfully")
        
        # Test config validation
        from config import get_env_config, validate_config
        config_data = get_env_config()
        
        if validate_config(config_data):
            print("✅ Configuration validation passed")
        else:
            print("⚠️ Configuration validation failed (missing optional keys)")
        
        return True
    except Exception as e:
        print(f"❌ Failed to import configuration: {e}")
        return False

def main():
    """Main test function"""
    print("🐙 GitHub Issue Analyzer - Setup Test")
    print("=" * 40)
    
    tests = [
        ("Module Imports", test_imports),
        ("Environment Configuration", test_env_file),
        ("API Module", test_api_imports),
        ("Streamlit App", test_streamlit_app),
        ("Configuration", test_config)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} failed")
    
    print(f"\n{'='*40}")
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your setup is ready.")
        print("\n📋 Next steps:")
        print("1. Run: python start_app.py")
        print("2. Or run manually:")
        print("   - Terminal 1: python src/main.py")
        print("   - Terminal 2: streamlit run streamlit_app.py")
    else:
        print("⚠️ Some tests failed. Please check the errors above.")
        print("\n💡 Troubleshooting:")
        print("1. Run: python install.py")
        print("2. Check your .env file")
        print("3. Ensure all dependencies are installed")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 