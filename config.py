"""
Configuration file for GitHub Issue Analyzer
Centralizes all application settings
"""

import os
from typing import Dict, Any

# API Configuration
API_HOST = "0.0.0.0"
API_PORT = 8000
API_BASE_URL = f"http://localhost:{API_PORT}"

# Streamlit Configuration
STREAMLIT_PORT = 8501
STREAMLIT_HOST = "localhost"

# OpenAI Configuration
OPENAI_MODEL = "gpt-4o"
OPENAI_MAX_TOKENS = 2000
OPENAI_TEMPERATURE = 0.2

# GitHub Configuration
GITHUB_USER_ID = "nks8839@nyu.edu"  # Default user ID for Composio

# Auto-fix Configuration
AUTO_FIX_TIMEOUT = 300  # 5 minutes
GIT_CLONE_TIMEOUT = 30  # 30 seconds
GITINGEST_TIMEOUT = 30  # 30 seconds

# UI Configuration
DEFAULT_ISSUE_LIMIT = 20
MAX_ISSUE_LIMIT = 100
DEFAULT_INCLUDE_CLOSED = False

# Chart Configuration
CHART_COLORS = {
    'High': '#ff4444',
    'Medium': '#ffaa00', 
    'Low': '#44ff44',
    'Complex': '#ff4444',
    'Simple': '#44ff44'
}

# Demo Configuration
DEMO_REPOSITORY = {
    'owner': 'octocat',
    'repo': 'Hello-World',
    'issue_number': 1
}

# Environment Variables
def get_env_config() -> Dict[str, Any]:
    """Get configuration from environment variables"""
    return {
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
        'COMPOSIO_API_KEY': os.getenv('COMPOSIO_API_KEY'),
        'GITHUB_USER_ID': os.getenv('GITHUB_USER_ID', GITHUB_USER_ID),
        'API_HOST': os.getenv('API_HOST', API_HOST),
        'API_PORT': int(os.getenv('API_PORT', API_PORT)),
        'STREAMLIT_PORT': int(os.getenv('STREAMLIT_PORT', STREAMLIT_PORT)),
        'OPENAI_MODEL': os.getenv('OPENAI_MODEL', OPENAI_MODEL),
        'OPENAI_MAX_TOKENS': int(os.getenv('OPENAI_MAX_TOKENS', OPENAI_MAX_TOKENS)),
        'OPENAI_TEMPERATURE': float(os.getenv('OPENAI_TEMPERATURE', OPENAI_TEMPERATURE))
    }

# Validation
def validate_config(config: Dict[str, Any]) -> bool:
    """Validate configuration"""
    required_keys = ['OPENAI_API_KEY', 'COMPOSIO_API_KEY']
    
    for key in required_keys:
        if not config.get(key):
            print(f"❌ Missing required configuration: {key}")
            return False
    
    return True

# Default configuration
DEFAULT_CONFIG = {
    'API_HOST': API_HOST,
    'API_PORT': API_PORT,
    'API_BASE_URL': API_BASE_URL,
    'STREAMLIT_PORT': STREAMLIT_PORT,
    'STREAMLIT_HOST': STREAMLIT_HOST,
    'OPENAI_MODEL': OPENAI_MODEL,
    'OPENAI_MAX_TOKENS': OPENAI_MAX_TOKENS,
    'OPENAI_TEMPERATURE': OPENAI_TEMPERATURE,
    'GITHUB_USER_ID': GITHUB_USER_ID,
    'AUTO_FIX_TIMEOUT': AUTO_FIX_TIMEOUT,
    'GIT_CLONE_TIMEOUT': GIT_CLONE_TIMEOUT,
    'GITINGEST_TIMEOUT': GITINGEST_TIMEOUT,
    'DEFAULT_ISSUE_LIMIT': DEFAULT_ISSUE_LIMIT,
    'MAX_ISSUE_LIMIT': MAX_ISSUE_LIMIT,
    'DEFAULT_INCLUDE_CLOSED': DEFAULT_INCLUDE_CLOSED,
    'CHART_COLORS': CHART_COLORS,
    'DEMO_REPOSITORY': DEMO_REPOSITORY
} 