#!/usr/bin/env python3
"""
Startup script for GitHub Issue Analyzer
Launches both the API server and Streamlit app
"""

import subprocess
import sys
import time
import os
import signal
import threading
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = ['streamlit', 'fastapi', 'uvicorn', 'openai', 'requests']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        print("Please install dependencies with: pip install -r requirements.txt")
        return False
    
    return True

def check_env_file():
    """Check if .env file exists"""
    if not Path('.env').exists():
        print("⚠️  Warning: .env file not found")
        print("Please create a .env file with your API keys:")
        print("OPENAI_API_KEY=your_openai_api_key_here")
        print("COMPOSIO_API_KEY=your_composio_api_key_here")
        return False
    return True

def start_api_server():
    """Start the FastAPI server"""
    print("🚀 Starting API server...")
    try:
        # Start the API server
        api_process = subprocess.Popen(
            [sys.executable, "src/main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a moment for the server to start
        time.sleep(3)
        
        # Check if the server started successfully
        if api_process.poll() is None:
            print("✅ API server started successfully on http://localhost:8000")
            return api_process
        else:
            stdout, stderr = api_process.communicate()
            print(f"❌ Failed to start API server:")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Error starting API server: {e}")
        return None

def start_streamlit_app():
    """Start the Streamlit app"""
    print("🎨 Starting Streamlit app...")
    try:
        # Start the Streamlit app
        streamlit_process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "streamlit_app.py", "--server.port", "8501"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a moment for the app to start
        time.sleep(5)
        
        # Check if the app started successfully
        if streamlit_process.poll() is None:
            print("✅ Streamlit app started successfully on http://localhost:8501")
            return streamlit_process
        else:
            stdout, stderr = streamlit_process.communicate()
            print(f"❌ Failed to start Streamlit app:")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Error starting Streamlit app: {e}")
        return None

def monitor_processes(api_process, streamlit_process):
    """Monitor the running processes"""
    try:
        while True:
            # Check if processes are still running
            if api_process and api_process.poll() is not None:
                print("❌ API server stopped unexpectedly")
                break
                
            if streamlit_process and streamlit_process.poll() is not None:
                print("❌ Streamlit app stopped unexpectedly")
                break
                
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        if api_process:
            api_process.terminate()
        if streamlit_process:
            streamlit_process.terminate()
        print("✅ Shutdown complete")

def main():
    """Main function to start both services"""
    print("🐙 GitHub Issue Analyzer Startup")
    print("=" * 40)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check environment file
    check_env_file()
    
    print("\n📋 Starting services...")
    print("Note: You may need to authorize GitHub access on first run")
    print("=" * 40)
    
    # Start API server
    api_process = start_api_server()
    if not api_process:
        print("❌ Failed to start API server. Exiting.")
        sys.exit(1)
    
    # Start Streamlit app
    streamlit_process = start_streamlit_app()
    if not streamlit_process:
        print("❌ Failed to start Streamlit app. Exiting.")
        api_process.terminate()
        sys.exit(1)
    
    print("\n🎉 Both services are running!")
    print("📊 Streamlit App: http://localhost:8501")
    print("🔧 API Server: http://localhost:8000")
    print("📚 API Docs: http://localhost:8000/docs")
    print("\nPress Ctrl+C to stop all services")
    print("=" * 40)
    
    # Monitor processes
    try:
        monitor_processes(api_process, streamlit_process)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        if api_process:
            api_process.terminate()
        if streamlit_process:
            streamlit_process.terminate()
        print("✅ Shutdown complete")

if __name__ == "__main__":
    main() 