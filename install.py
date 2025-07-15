#!/usr/bin/env python3
"""
Installation script for GitHub Issue Analyzer
Handles dependency installation with fallback options
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False

def install_core_dependencies():
    """Install core dependencies"""
    core_deps = [
        "fastapi>=0.104.0",
        "uvicorn>=0.24.0", 
        "openai>=1.3.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.5.0",
        "streamlit>=1.28.0",
        "requests>=2.31.0",
        "pandas>=2.1.0",
        "plotly>=5.17.0",
        "python-multipart>=0.0.6"
    ]
    
    for dep in core_deps:
        if not run_command(f"pip install {dep}", f"Installing {dep}"):
            return False
    return True

def install_optional_dependencies():
    """Install optional dependencies with fallback"""
    optional_deps = [
        ("composio>=1.0.0rc9", "Composio"),
        ("composio-openai>=1.0.0rc9", "Composio OpenAI"),
        ("langchain>=0.0.350", "LangChain"),
        ("langchain-openai>=0.0.2", "LangChain OpenAI")
    ]
    
    installed_count = 0
    for dep, name in optional_deps:
        if run_command(f"pip install {dep}", f"Installing {name}"):
            installed_count += 1
        else:
            print(f"⚠️ Warning: {name} installation failed, continuing without it")
    
    print(f"✅ Installed {installed_count}/{len(optional_deps)} optional dependencies")
    return installed_count > 0

def create_env_file():
    """Create .env file if it doesn't exist"""
    env_file = Path('.env')
    if not env_file.exists():
        print("📝 Creating .env file...")
        env_content = """# GitHub Issue Analyzer Configuration
# Add your API keys here

OPENAI_API_KEY=your_openai_api_key_here
COMPOSIO_API_KEY=your_composio_api_key_here

# Optional: Customize these settings
# API_HOST=0.0.0.0
# API_PORT=8000
# STREAMLIT_PORT=8501
"""
        with open(env_file, 'w') as f:
            f.write(env_content)
        print("✅ Created .env file")
        print("⚠️ Please edit .env file and add your API keys")
    else:
        print("✅ .env file already exists")

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python {version.major}.{version.minor} is not supported")
        print("Please use Python 3.8 or higher")
        return False
    
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
    return True

def main():
    """Main installation function"""
    print("🐙 GitHub Issue Analyzer Installation")
    print("=" * 40)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Install core dependencies
    print("\n📦 Installing core dependencies...")
    if not install_core_dependencies():
        print("❌ Core dependency installation failed")
        sys.exit(1)
    
    # Install optional dependencies
    print("\n📦 Installing optional dependencies...")
    install_optional_dependencies()
    
    # Create .env file
    print("\n📝 Setting up configuration...")
    create_env_file()
    
    print("\n🎉 Installation completed!")
    print("\n📋 Next steps:")
    print("1. Edit .env file and add your API keys")
    print("2. Run: python start_app.py")
    print("3. Or run manually:")
    print("   - Terminal 1: python src/main.py")
    print("   - Terminal 2: streamlit run streamlit_app.py")
    print("\n📚 Documentation: README.md")

if __name__ == "__main__":
    main() 