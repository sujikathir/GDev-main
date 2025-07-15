from openai import OpenAI
from fastapi import FastAPI, Request, HTTPException, Query, Path, BackgroundTasks
from fastapi.responses import JSONResponse

# Try to import Composio and related packages
try:
    from composio import Composio
    from composio_openai import OpenAIProvider
    COMPOSIO_AVAILABLE = True
except ImportError:
    COMPOSIO_AVAILABLE = False
    print("⚠️ Warning: Composio not available, using fallback mode")
    
    # Mock classes for fallback
    class Composio:
        def __init__(self, provider=None, api_key=None):
            self.provider = provider
            self.api_key = api_key
        
        def toolkits(self):
            return self
        
        def authorize(self, user_id, toolkit):
            return self
        
        def tools(self):
            return self
        
        def get(self, user_id, toolkits):
            return []
        
        def wait_for_connection(self, timeout):
            pass
    
    class OpenAIProvider:
        def __init__(self):
            pass
        
        def handle_tool_calls(self, response, user_id):
            return []

# Try to import LangChain
try:
    from langchain.agents import create_openai_functions_agent, AgentExecutor
    from langchain import hub
    from langchain_openai import ChatOpenAI
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("⚠️ Warning: LangChain not available, using fallback mode")
import json
import os
import tempfile
import subprocess
import shutil
import uuid
from pathlib import Path as FilePath
from dotenv import load_dotenv
import asyncio
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
import requests

# Helper function to get the default branch of a repo

def get_default_branch(owner: str, repo: str) -> str:
    """Fetch the default branch name for a GitHub repo using the API. Fallback to 'main' then 'master'."""
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = {}
        github_token = os.getenv("GITHUB_TOKEN") or os.getenv("COMPOSIO_API_KEY")
        if github_token:
            headers["Authorization"] = f"token {github_token}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("default_branch", "main")
        else:
            print(f"⚠️ Could not fetch default branch, status {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"⚠️ Exception fetching default branch: {e}")
    return "main"  # fallback

# Read GitHub username from environment for multi-user support
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
if not GITHUB_USERNAME:
    print("⚠️ Warning: GITHUB_USERNAME not set in .env. Fork/PR logic may not work as expected.")

# Try to import gitingest, fallback to mock if not available
try:
    from gitingest import ingest
    GITINGEST_AVAILABLE = True
except ImportError:
    GITINGEST_AVAILABLE = False
    print("⚠️ Warning: gitingest not available, using fallback repository content")
    
    def ingest(github_url):
        """Fallback ingest function when gitingest is not available"""
        repo_name = github_url.replace("https://github.com/", "")
        return (
            f"Repository {repo_name} (fallback content)",
            {"files": ["README.md", "main.py"]},
            {"README.md": "# Repository Content\n\nThis is fallback content when gitingest is not available."}
        )


load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="GitHub Issue Analyzer", 
    description="Analyze GitHub issues and suggest solutions using AI", 
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Initialize clients
openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize Composio if available
if COMPOSIO_AVAILABLE:
    composio = Composio(provider=OpenAIProvider(), api_key=os.getenv("COMPOSIO_API_KEY"))
else:
    composio = Composio(provider=OpenAIProvider(), api_key=None)

# For multi-user: get user_id and github_username from request or session (for now, fallback to env)
def get_user_context(request: Optional[Request] = None):
    # In the future, extract from request/session/cookie
    user_id = os.getenv("USER_ID", "default_user@gdev.local")
    github_username = os.getenv("GITHUB_USERNAME", "")
    return user_id, github_username

# Pydantic models
class IssueAnalysis(BaseModel):
    issue_id: int
    title: str
    body: str
    analysis: str
    suggested_solution: str
    priority: str
    complexity: str

class RepositoryData(BaseModel):
    name: str
    description: str
    open_issues_count: int
    issues: List[Dict[str, Any]]
    
class AutoFixRequest(BaseModel):
    owner: str
    repo: str
    issue_number: int
    branch_name: Optional[str] = None
    commit_message: Optional[str] = None

class AutoFixStatus(BaseModel):
    task_id: str
    status: str
    repository: str
    issue_number: int
    branch_name: Optional[str] = None
    pr_url: Optional[str] = None
    error: Optional[str] = None
    
class AutoFixResult(BaseModel):
    success: bool
    pr_url: Optional[str] = None
    branch_name: str
    commit_message: str
    error: Optional[str] = None

# Global variables to store connection state
connection_initialized = False
github_tools = None

# Dictionary to track auto-fix tasks
auto_fix_tasks = {}

async def initialize_github_connection(user_id=None):
    """Initialize GitHub connection if not already done"""
    global connection_initialized, github_tools
    
    if not connection_initialized:
        if not COMPOSIO_AVAILABLE:
            print("⚠️ Composio not available, using fallback mode")
            connection_initialized = True
            github_tools = []
            return
        
        if not user_id:
            user_id, _ = get_user_context()
        
        try:
            connection_request = composio.toolkits.authorize(user_id=user_id, toolkit="github")
            print(f"🔗 Visit the URL to authorize:\n👉 {connection_request.redirect_url}")
            
            # Get tools - updated to use correct tool names
            github_tools = composio.tools.get(
                user_id=user_id, 
                toolkits=["github"]
            )
            
            # Debug: Print available tools
            print(f"🔍 Available GitHub tools: {len(github_tools) if github_tools else 0} tools")
            if github_tools:
                for i, tool in enumerate(github_tools):
                    print(f"  Tool {i+1}: {tool.get('function', {}).get('name', 'Unknown')}")
            
            # Try to wait for connection with timeout
            try:
                connection_request.wait_for_connection(timeout=30)  # 30 second timeout
                connection_initialized = True
                print("✅ GitHub connection initialized successfully")
            except Exception as connection_error:
                print(f"⚠️ Warning: GitHub connection timed out: {connection_error}")
                print("⚠️ Continuing with tools available but connection may be limited")
                connection_initialized = True  # Mark as initialized anyway
                
        except Exception as e:
            print(f"❌ Failed to initialize GitHub connection: {e}")
            print("⚠️ Continuing with fallback mode")
            connection_initialized = True  # Mark as initialized to prevent retries
            github_tools = []  # Empty tools list

async def get_repository_content(repo_name: str) -> Dict[str, Any]:
    """Get repository details and content"""
    await initialize_github_connection()
    
    try:
        # Convert repo_name to GitHub URL format
        github_url = f"https://github.com/{repo_name}"
        
        # Run the synchronous ingest function in a thread pool with timeout
        loop = asyncio.get_event_loop()
        try:
            summary, tree, content = await asyncio.wait_for(
                loop.run_in_executor(None, ingest, github_url),
                timeout=30.0  # 30 second timeout
            )
            
            return {
                "summary": summary,
                "tree": tree,
                "content": content,
                "repository_name": repo_name
            }
        except asyncio.TimeoutError:
            print(f"⚠️ Warning: gitingest timed out for {repo_name}")
            raise Exception("gitingest operation timed out")
        
    except Exception as e:
        print(f"⚠️ Warning: Could not fetch repository content with gitingest: {e}")
        print(f"⚠️ Falling back to basic repository info for {repo_name}")
        # Return basic repository info as fallback
        return {
            "summary": f"Repository {repo_name} (fallback mode)",
            "tree": {"files": ["README.md", "main.py"]},
            "content": {"README.md": f"# {repo_name}\n\nRepository content not available in fallback mode."},
            "repository_name": repo_name
        }

async def get_repository_issues(repo_name: str) -> Dict[str, Any]:
    """Get repository open issues (fetch all pages)"""
    await initialize_github_connection()
    user_id, _ = get_user_context()
    # If no tools available, return mock data immediately
    if not github_tools:
        print(f"⚠️ No GitHub tools available, using mock data for {repo_name}")
        return [{
            "successful": True,
            "data": {
                "details": [
                    {
                        "number": 1,
                        "title": "Sample Issue - Database Schema Update",
                        "body": "We need to update the database schema to include new fields for user preferences.",
                        "state": "open",
                        "labels": [{"name": "enhancement"}, {"name": "database"}],
                        "created_at": "2024-01-15T10:00:00Z",
                        "updated_at": "2024-01-15T10:00:00Z"
                    },
                    {
                        "number": 2,
                        "title": "Bug Fix - Authentication Error",
                        "body": "Users are experiencing authentication errors when logging in with OAuth providers.",
                        "state": "open",
                        "labels": [{"name": "bug"}, {"name": "high-priority"}],
                        "created_at": "2024-01-14T15:30:00Z",
                        "updated_at": "2024-01-14T16:45:00Z"
                    },
                    {
                        "number": 3,
                        "title": "Feature Request - API Rate Limiting",
                        "body": "Implement rate limiting for the REST API endpoints to prevent abuse.",
                        "state": "open",
                        "labels": [{"name": "feature"}, {"name": "api"}],
                        "created_at": "2024-01-13T09:15:00Z",
                        "updated_at": "2024-01-13T09:15:00Z"
                    }
                ]
            }
        }]
    # Try to fetch all pages of issues using the GitHub API directly
    try:
        import requests
        owner, repo = repo_name.split("/")
        issues = []
        page = 1
        per_page = 100
        github_token = os.getenv("GITHUB_TOKEN") or os.getenv("COMPOSIO_API_KEY")
        headers = {"Accept": "application/vnd.github+json"}
        if github_token:
            headers["Authorization"] = f"token {github_token}"
        while True:
            url = f"https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page={per_page}&page={page}"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"❌ Error fetching issues from GitHub API: {resp.status_code} {resp.text}")
                break
            page_issues = resp.json()
            if not page_issues:
                break
            issues.extend(page_issues)
            if len(page_issues) < per_page:
                break
            page += 1
        print(f"[DEBUG] Total issues fetched: {len(issues)}")
        print(f"[DEBUG] Issue numbers: {[i.get('number') for i in issues]}")
        return [{
            "successful": True,
            "data": {
                "details": issues
            }
        }]
    except Exception as e:
        print(f"❌ Error fetching repository issues (pagination): {e}")
        print(f"⚠️ Falling back to original OpenAI/Composio tools for issues.")
    # Fallback to original OpenAI/Composio tools if direct API fails
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            tools=github_tools,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant with access to GitHub tools. When asked about GitHub repositories, you MUST use the available tools to fetch real data. Use the appropriate GitHub tool to get repository issues."
                },
                {
                    "role": "user",
                    "content": f"Get the list of open issues for the public repository {repo_name}"
                },
            ],
            tool_choice="required"
        )
        result = composio.provider.handle_tool_calls(response=response, user_id=user_id)
        print(f"🔍 Raw issues from GitHub API: {json.dumps(result, indent=2)}")
        return result
    except Exception as e:
        print(f"❌ Error fetching repository issues: {e}")
        print(f"⚠️ Falling back to mock data for testing purposes")
        # Return mock data for testing
        return [{
            "successful": True,
            "data": {
                "details": [
                    {
                        "number": 1,
                        "title": "Sample Issue - Database Schema Update",
                        "body": "We need to update the database schema to include new fields for user preferences.",
                        "state": "open",
                        "labels": [{"name": "enhancement"}, {"name": "database"}],
                        "created_at": "2024-01-15T10:00:00Z",
                        "updated_at": "2024-01-15T10:00:00Z"
                    },
                    {
                        "number": 2,
                        "title": "Bug Fix - Authentication Error",
                        "body": "Users are experiencing authentication errors when logging in with OAuth providers.",
                        "state": "open",
                        "labels": [{"name": "bug"}, {"name": "high-priority"}],
                        "created_at": "2024-01-14T15:30:00Z",
                        "updated_at": "2024-01-14T16:45:00Z"
                    },
                    {
                        "number": 3,
                        "title": "Feature Request - API Rate Limiting",
                        "body": "Implement rate limiting for the REST API endpoints to prevent abuse.",
                        "state": "open",
                        "labels": [{"name": "feature"}, {"name": "api"}],
                        "created_at": "2024-01-13T09:15:00Z",
                        "updated_at": "2024-01-13T09:15:00Z"
                    }
                ]
            }
        }]

async def get_repository_data(repo_name: str) -> Dict[str, Any]:
    """Get repository details and issues (legacy function)"""
    await initialize_github_connection()
    user_id, _ = get_user_context()
    # This function is kept for backward compatibility
    
    # If no tools available, return mock data immediately
    if not github_tools:
        print(f"⚠️ No GitHub tools available, using mock data for {repo_name}")
        return [{
            "successful": True,
            "data": {
                "name": repo_name.split('/')[-1],
                "full_name": repo_name,
                "description": f"Repository {repo_name}",
                "details": [
                    {
                        "number": 1,
                        "title": "Sample Issue - Database Schema Update",
                        "body": "We need to update the database schema to include new fields for user preferences.",
                        "state": "open",
                        "labels": [{"name": "enhancement"}, {"name": "database"}],
                        "created_at": "2024-01-15T10:00:00Z",
                        "updated_at": "2024-01-15T10:00:00Z"
                    },
                    {
                        "number": 2,
                        "title": "Bug Fix - Authentication Error",
                        "body": "Users are experiencing authentication errors when logging in with OAuth providers.",
                        "state": "open",
                        "labels": [{"name": "bug"}, {"name": "high-priority"}],
                        "created_at": "2024-01-14T15:30:00Z",
                        "updated_at": "2024-01-14T16:45:00Z"
                    },
                    {
                        "number": 3,
                        "title": "Feature Request - API Rate Limiting",
                        "body": "Implement rate limiting for the REST API endpoints to prevent abuse.",
                        "state": "open",
                        "labels": [{"name": "feature"}, {"name": "api"}],
                        "created_at": "2024-01-13T09:15:00Z",
                        "updated_at": "2024-01-13T09:15:00Z"
                    }
                ]
            }
        }]
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            tools=github_tools,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant with access to GitHub tools. When asked about GitHub repositories, you MUST use the available tools to fetch real data. Use the appropriate GitHub tools to get repository information and issues."
                },
                {
                    "role": "user",
                    "content": f"Get repository information and list of open issues for the public repository {repo_name}"
                },
            ],
            tool_choice="required"
        )
        
        result = composio.provider.handle_tool_calls(response=response, user_id=user_id)
        print(f"🔍 Raw result from GitHub API: {json.dumps(result, indent=2)}")
        return result
        
    except Exception as e:
        print(f"❌ Error fetching repository data: {e}")
        print(f"⚠️ Falling back to mock data for {repo_name}")
        
        # Return mock data for testing
        return [{
            "successful": True,
            "data": {
                "name": repo_name.split('/')[-1],
                "full_name": repo_name,
                "description": f"Repository {repo_name}",
                "details": [
                    {
                        "number": 1,
                        "title": "Sample Issue - Database Schema Update",
                        "body": "We need to update the database schema to include new fields for user preferences.",
                        "state": "open",
                        "labels": [{"name": "enhancement"}, {"name": "database"}],
                        "created_at": "2024-01-15T10:00:00Z",
                        "updated_at": "2024-01-15T10:00:00Z"
                    },
                    {
                        "number": 2,
                        "title": "Bug Fix - Authentication Error",
                        "body": "Users are experiencing authentication errors when logging in with OAuth providers.",
                        "state": "open",
                        "labels": [{"name": "bug"}, {"name": "high-priority"}],
                        "created_at": "2024-01-14T15:30:00Z",
                        "updated_at": "2024-01-14T16:45:00Z"
                    },
                    {
                        "number": 3,
                        "title": "Feature Request - API Rate Limiting",
                        "body": "Implement rate limiting for the REST API endpoints to prevent abuse.",
                        "state": "open",
                        "labels": [{"name": "feature"}, {"name": "api"}],
                        "created_at": "2024-01-13T09:15:00Z",
                        "updated_at": "2024-01-13T09:15:00Z"
                    }
                ]
            }
        }]

async def get_specific_issue(owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
    """Get a specific issue by number"""
    await initialize_github_connection()
    user_id, _ = get_user_context()
    
    # If no tools available, return mock data immediately
    if not github_tools:
        print(f"⚠️ No GitHub tools available, using mock data for issue #{issue_number}")
        return [{
            "successful": True,
            "data": {
                "number": issue_number,
                "title": f"Sample Issue #{issue_number} - Mock Data",
                "body": f"This is mock data for issue #{issue_number} since GitHub tools are not available.",
                "state": "open",
                "labels": [{"name": "mock"}, {"name": "sample"}],
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T10:00:00Z"
            }
        }]
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            tools=github_tools,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant with access to GitHub tools. When asked about a specific GitHub issue, you MUST use the available tools to fetch real data."
                },
                {
                    "role": "user",
                    "content": f"Get the details for issue #{issue_number} in the repository {owner}/{repo}"
                },
            ],
            tool_choice="required"
        )
        
        result = composio.provider.handle_tool_calls(response=response, user_id=user_id)
        print(f"🔍 Raw result for specific issue: {json.dumps(result, indent=2)}")
        return result
        
    except Exception as e:
        print(f"❌ Error fetching specific issue: {e}")
        print(f"⚠️ Falling back to mock data for issue #{issue_number}")
        
        # Return mock data for testing
        return [{
            "successful": True,
            "data": {
                "number": issue_number,
                "title": f"Sample Issue #{issue_number} - Mock Data",
                "body": f"This is mock data for issue #{issue_number} since GitHub tools failed.",
                "state": "open",
                "labels": [{"name": "mock"}, {"name": "sample"}],
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T10:00:00Z"
            }
        }]

async def analyze_issue_with_llm(issue: Dict[str, Any], repo_context: Dict[str, Any]) -> IssueAnalysis:
    """Analyze an issue using LLM and suggest solutions based on repository context"""
    try:
        # Extract issue details
        issue_title = issue.get('title', 'No title')
        issue_body = issue.get('body') or "No description provided"  # Handle null body
        issue_id = issue.get('number', 0)
        
        # Extract repository content details
        repo_name = repo_context.get('name', 'Unknown')
        repo_description = repo_context.get('description', 'No description')
        repo_content = repo_context.get('content', {})
        repo_tree = repo_context.get('tree', {})
        
        # Prepare relevant code snippets based on the issue title/body
        relevant_files = []
        relevant_code_snippets = []
        
        # Extract keywords from issue title and body for searching relevant files
        keywords = set()
        for text in [issue_title, issue_body]:
            if text and isinstance(text, str):  # Ensure text is not None and is string
                # Extract potential code-related terms
                words = text.lower().replace('-', ' ').replace('_', ' ').split()
                keywords.update([w for w in words if len(w) > 3])
        
        # Find relevant files and code snippets from repository content
        if repo_content and isinstance(repo_content, dict):  # Ensure repo_content is a dict
            # Look for files that might be related to the issue
            for file_path, content in repo_content.items():
                if not isinstance(file_path, str) or not isinstance(content, str):
                    continue  # Skip non-string values
                    
                file_relevance = 0
                # Check if file name or content contains keywords from issue
                for keyword in keywords:
                    if keyword in file_path.lower():
                        file_relevance += 3
                    if keyword in content.lower():
                        file_relevance += 1
                
                # If file seems relevant, add it to the list
                if file_relevance > 0:
                    # Truncate content if too large
                    if len(content) > 1000:
                        content = content[:1000] + "... [truncated]"
                    relevant_files.append({
                        "path": file_path,
                        "relevance": file_relevance,
                        "content": content
                    })
        
        # Sort by relevance and take top 3 most relevant files
        relevant_files.sort(key=lambda x: x["relevance"], reverse=True)
        top_relevant_files = relevant_files[:3]
        
        # Extract code snippets from relevant files
        for file_info in top_relevant_files:
            if isinstance(file_info["content"], str):
                relevant_code_snippets.append(f"File: {file_info['path']}\n```\n{file_info['content']}\n```")
        
        # Create enhanced analysis prompt with repository context
        analysis_prompt = f"""
        Analyze this GitHub issue and provide specific, actionable solutions based on the repository context:
        
        Repository: {repo_name}
        Repository Description: {repo_description}
        
        Issue #{issue_id}: {issue_title}
        Description: {issue_body}
        
        Repository Structure Overview:
        {json.dumps(repo_tree, indent=2)[:1000] if repo_tree and isinstance(repo_tree, dict) else "No structure information available"}
        
        Relevant Files (based on issue keywords):
        {"\n\n".join(relevant_code_snippets) if relevant_code_snippets else "No specific code files identified as relevant to this issue."}
        
        Please provide:
        1. A detailed analysis of the issue that references specific parts of the codebase
        2. Specific, actionable solution steps with code examples where appropriate
        3. Priority level (High/Medium/Low) with justification
        4. Complexity level (Simple/Medium/Complex) with justification
        
        Your analysis should be technical, specific to this codebase, and provide clear steps to resolve the issue.
        """
        
        # Make LLM call for analysis with enhanced context
        analysis_response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a senior software engineer analyzing GitHub issues. You have access to the repository's code and structure. Provide detailed technical analysis with specific references to the codebase and actionable solutions with code examples where appropriate."
                },
                {
                    "role": "user",
                    "content": analysis_prompt
                }
            ],
            max_tokens=2000,
            temperature=0.2
        )
        
        analysis_text = analysis_response.choices[0].message.content
        
        # Parse the analysis to extract components
        lines = analysis_text.split('\n')
        analysis_parts = {
            'analysis': '',
            'solution': '',
            'priority': 'Medium',
            'complexity': 'Medium'
        }
        
        current_section = 'analysis'
        for line in lines:
            line = line.strip()
            if 'suggested solution' in line.lower() or 'solution steps' in line.lower() or 'solution:' in line.lower():
                current_section = 'solution'
            elif 'priority' in line.lower() and (':' in line or 'level' in line):
                if 'high' in line.lower():
                    analysis_parts['priority'] = 'High'
                elif 'low' in line.lower():
                    analysis_parts['priority'] = 'Low'
                else:
                    analysis_parts['priority'] = 'Medium'
            elif 'complexity' in line.lower() and (':' in line or 'level' in line):
                if 'complex' in line.lower():
                    analysis_parts['complexity'] = 'Complex'
                elif 'simple' in line.lower():
                    analysis_parts['complexity'] = 'Simple'
                else:
                    analysis_parts['complexity'] = 'Medium'
            elif line and not line.startswith('##'):
                analysis_parts[current_section] += line + ' '
        
        return IssueAnalysis(
            issue_id=issue_id,
            title=issue_title,
            body=issue_body,
            analysis=analysis_parts['analysis'].strip() or analysis_text,
            suggested_solution=analysis_parts['solution'].strip() or "Solution analysis included in main analysis",
            priority=analysis_parts['priority'],
            complexity=analysis_parts['complexity']
        )
        
    except Exception as e:
        print(f"❌ Error analyzing issue: {e}")
        # Return basic analysis if LLM call fails
        return IssueAnalysis(
            issue_id=issue.get('number', 0),
            title=issue.get('title', 'No title'),
            body=issue.get('body') or "No description provided",
            analysis=f"Error analyzing issue: {str(e)}",
            suggested_solution="Manual analysis required",
            priority="Medium",
            complexity="Medium"
        )

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "GitHub Issue Analyzer API", "status": "running"}

@app.get("/repository/{owner}/{repo}/issues", response_model=List[IssueAnalysis])
async def analyze_repository_issues(
    owner: str, 
    repo: str, 
    include_closed: bool = Query(False, description="Include closed issues"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of issues to analyze")
):
    """Get and analyze all issues for a repository"""
    repo_name = f"{owner}/{repo}"
    
    try:
        # Get repository content and issues separately
        repo_content = await get_repository_content(repo_name)
        repo_issues = await get_repository_issues(repo_name)
        
        # Extract repository info and issues
        repository_info = {
            'name': repo,
            'full_name': repo_name,
            'description': repo_content.get('summary', f'Repository {repo_name}'),
            "content": repo_content.get('content', {})
        }
        issues_data = []
        
        print(f"🔍 Processing repository data for {repo_name}")
        
        if isinstance(repo_issues, list):
            for item in repo_issues:
                print(f"🔍 Processing item: {item.get('successful')} - {list(item.get('data', {}).keys()) if item.get('data') else 'No data'}")
                if item.get('successful') and item.get('data'):
                    data = item['data']
                    if 'details' in data:  # This is issues data
                        issues_data = data['details']
                        print(f"✅ Found {len(issues_data)} issues")
                    elif isinstance(data, list):  # Direct list of issues
                        issues_data = data
                        print(f"✅ Found {len(issues_data)} issues (direct list)")
        
        if not issues_data:
            raise HTTPException(status_code=404, detail="No issues found in repository")
        
        print(f"🔍 Found {len(issues_data)} total issues")
        
        # Filter and limit issues
        filtered_issues = []
        for issue in issues_data:
            if include_closed or issue.get('state') == 'open':
                filtered_issues.append(issue)
                if len(filtered_issues) >= limit:
                    break
        
        print(f"🔍 Processing {len(filtered_issues)} issues (include_closed={include_closed}, limit={limit})")
        
        # Analyze each issue
        analyzed_issues = []
        for i, issue in enumerate(filtered_issues):
            print(f"🔍 Processing issue {i+1}/{len(filtered_issues)}: {issue.get('title', 'No title')}")
            analysis = await analyze_issue_with_llm(issue, repository_info)
            analyzed_issues.append(analysis)
            print(f"✅ Analyzed issue #{issue.get('number')}: {issue.get('title')}")
        
        print(f"✅ Successfully analyzed {len(analyzed_issues)} issues")
        return analyzed_issues
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in analyze_repository_issues: {e}")
        raise HTTPException(status_code=500, detail=f"Error analyzing repository issues: {str(e)}")

@app.get("/repository/{owner}/{repo}/issues/raw")
async def get_repository_issues_raw(
    owner: str, 
    repo: str, 
    include_closed: bool = Query(False, description="Include closed issues"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of issues to return")
):
    """Get raw issues data without analysis"""
    repo_name = f"{owner}/{repo}"
    
    try:
        # Get repository issues
        repo_issues = await get_repository_issues(repo_name)
        
        # Extract issues data
        issues_data = []
        
        if isinstance(repo_issues, list):
            for item in repo_issues:
                if item.get('successful') and item.get('data'):
                    data = item['data']
                    if 'details' in data:  # This is issues data
                        issues_data = data['details']
                    elif isinstance(data, list):  # Direct list of issues
                        issues_data = data
        
        if not issues_data:
            raise HTTPException(status_code=404, detail="No issues found in repository")
        
        # Filter and limit issues
        filtered_issues = []
        for issue in issues_data:
            if include_closed or issue.get('state') == 'open':
                filtered_issues.append(issue)
                if len(filtered_issues) >= limit:
                    break
        
        return {
            "repository": repo_name,
            "total_issues": len(issues_data),
            "filtered_issues": len(filtered_issues),
            "include_closed": include_closed,
            "limit": limit,
            "issues": filtered_issues
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting raw issues: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching issues: {str(e)}")

@app.get("/repository/{owner}/{repo}/info")
async def get_repository_info(owner: str, repo: str):
    """Get basic repository information"""
    repo_name = f"{owner}/{repo}"
    
    try:
        # Get repository content
        repo_content = await get_repository_content(repo_name)
        
        return {
            "name": repo,
            "full_name": repo_name,
            "description": repo_content.get('summary', f'Repository {repo_name}'),
            "language": "Unknown",  # Could be extracted from content if needed
            "open_issues_count": 0,  # Would need separate call to get this
            "stargazers_count": 0,   # Would need separate call to get this
            "created_at": None,      # Would need separate call to get this
            "updated_at": None       # Would need separate call to get this
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching repository info: {str(e)}")

@app.get("/repository/{owner}/{repo}/issues/stats")
async def get_issue_statistics(owner: str, repo: str):
    """Get issue statistics for a repository"""
    repo_name = f"{owner}/{repo}"
    
    try:
        # Get repository issues
        repo_issues = await get_repository_issues(repo_name)
        
        # Extract issues data
        issues_data = []
        
        if isinstance(repo_issues, list):
            for item in repo_issues:
                if item.get('successful') and item.get('data'):
                    data = item['data']
                    if 'details' in data:  # This is issues data
                        issues_data = data['details']
                    elif isinstance(data, list):  # Direct list of issues
                        issues_data = data
        
        if not issues_data:
            return {
                "repository": repo_name,
                "total_issues": 0,
                "open_issues": 0,
                "closed_issues": 0,
                "issues_by_priority": {"High": 0, "Medium": 0, "Low": 0},
                "issues_by_complexity": {"Simple": 0, "Medium": 0, "Complex": 0}
            }
        
        # Calculate statistics
        open_issues = [issue for issue in issues_data if issue.get('state') == 'open']
        closed_issues = [issue for issue in issues_data if issue.get('state') == 'closed']
        
        # Count by labels (if available)
        priority_counts = {"High": 0, "Medium": 0, "Low": 0}
        complexity_counts = {"Simple": 0, "Medium": 0, "Complex": 0}
        
        for issue in issues_data:
            labels = issue.get('labels', [])
            for label in labels:
                label_name = label.get('name', '').lower()
                if 'priority' in label_name:
                    if 'high' in label_name:
                        priority_counts["High"] += 1
                    elif 'low' in label_name:
                        priority_counts["Low"] += 1
                    else:
                        priority_counts["Medium"] += 1
                elif 'complexity' in label_name:
                    if 'complex' in label_name:
                        complexity_counts["Complex"] += 1
                    elif 'simple' in label_name:
                        complexity_counts["Simple"] += 1
                    else:
                        complexity_counts["Medium"] += 1
        
        return {
            "repository": repo_name,
            "total_issues": len(issues_data),
            "open_issues": len(open_issues),
            "closed_issues": len(closed_issues),
            "issues_by_priority": priority_counts,
            "issues_by_complexity": complexity_counts,
            "recent_issues": len([issue for issue in issues_data if issue.get('created_at')]),
            "last_updated": max([issue.get('updated_at', '') for issue in issues_data], default='')
        }
        
    except Exception as e:
        print(f"❌ Error getting issue statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching issue statistics: {str(e)}")

@app.get("/repository/{owner}/{repo}/issues/{issue_number}", response_model=IssueAnalysis)
async def analyze_specific_issue(
    owner: str, 
    repo: str, 
    issue_number: int = Path(..., gt=0, description="Issue number to analyze")
):
    """Get and analyze a specific issue by number"""
    repo_name = f"{owner}/{repo}"
    
    try:
        # Get repository content and issues
        repo_content = await get_repository_content(repo_name)
        repo_issues = await get_repository_issues(repo_name)
        
        repository_info = {
            'name': repo,
            'full_name': repo_name,
            'description': repo_content.get('summary', f'Repository {repo_name}'),
            'content': repo_content.get('content', {})
        }
        
        # Extract issue data
        issue = None
        issues_data = []
        
        if isinstance(repo_issues, list):
            for item in repo_issues:
                if item.get('successful') and item.get('data'):
                    data = item['data']
                    if 'details' in data:  # This is issues data
                        issues_data = data['details']
                    elif isinstance(data, list):  # Direct list of issues
                        issues_data = data
        
        # Find the specific issue
        for issue_item in issues_data:
            if issue_item.get('number') == issue_number:
                issue = issue_item
                break
        
        if not issue:
            raise HTTPException(status_code=404, detail=f"Issue #{issue_number} not found in repository {repo_name}")
        
        # Analyze the issue
        analysis = await analyze_issue_with_llm(issue, repository_info)
        return analysis
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error analyzing specific issue: {e}")
        raise HTTPException(status_code=500, detail=f"Error analyzing issue: {str(e)}")

async def run_custom_code_fix(repo_path: str, issue_analysis: IssueAnalysis, branch_name: str) -> Dict[str, Any]:
    """Run custom code fix using LLM to generate and apply fixes"""
    try:
        # Prepare fix prompt based on issue analysis
        issue_title = issue_analysis.title
        issue_id = issue_analysis.issue_id
        suggested_solution = issue_analysis.suggested_solution
        
        # Create fix prompt
        fix_prompt = f"""
        You are a senior software engineer fixing a GitHub issue. 
        
        Issue #{issue_id}: {issue_title}
        Analysis: {suggested_solution}
        
        Please provide the exact code changes needed to fix this issue. 
        Return your response in the following format:
        
        ```bash
        # Git commands to execute
        git checkout -b {branch_name}
        ```
        
        ```file:path/to/file
        # File changes (if any)
        ```
        
        ```bash
        # Additional git commands
        git add -A
        git commit -m "Fix issue #{issue_id}: {issue_title.replace('"', '\\"')}"
        git push -u origin {branch_name}
        ```
        
        IMPORTANT: For git commit messages, use proper quoting and escape any quotes in the issue title.
        Only include the actual commands and code changes needed. Be specific and actionable.
        """
        
        print(f"🤖 Generating fix with LLM for issue #{issue_id}")
        
        # Generate fix using LLM
        fix_response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a senior software engineer. Provide exact, actionable code changes and git commands to fix issues."
                },
                {
                    "role": "user",
                    "content": fix_prompt
                }
            ],
            max_tokens=2000,
            temperature=0.1
        )
        
        fix_instructions = fix_response.choices[0].message.content
        print(f"✅ Generated fix instructions:\n{fix_instructions}")
        
        # Parse the instructions to extract commands and file changes
        lines = fix_instructions.split('\n')
        git_commands = []
        file_changes = {}
        current_file = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('```bash'):
                # Start of git commands
                continue
            elif line.startswith('```file:'):
                # Start of file changes
                current_file = line.replace('```file:', '').strip()
                current_content = []
                continue
            elif line.startswith('```') and current_file:
                # End of file changes
                file_changes[current_file] = '\n'.join(current_content)
                current_file = None
                current_content = []
                continue
            elif current_file:
                # Collecting file content
                current_content.append(line)
            elif line and not line.startswith('```'):
                # Git command
                git_commands.append(line)
        
        # Apply file changes first
        for file_path, content in file_changes.items():
            full_path = os.path.join(repo_path, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, 'w') as f:
                f.write(content)
            print(f"📝 Updated file: {file_path}")
        
        # Execute git commands
        current_dir = os.getcwd()
        os.chdir(repo_path)
        
        for command in git_commands:
            if command.startswith('git'):
                print(f"🔄 Executing: {command}")
                
                # Handle git commit command specially to avoid space issues
                if command.startswith('git commit'):
                    # Extract the commit message from the command
                    if '-m' in command:
                        # Find the position of -m and extract everything after it
                        m_index = command.find(' -m ')
                        if m_index != -1:
                            git_cmd = command[:m_index].split()
                            commit_msg = command[m_index + 4:].strip()
                            # Remove surrounding quotes if present
                            if (commit_msg.startswith('"') and commit_msg.endswith('"')) or \
                               (commit_msg.startswith("'") and commit_msg.endswith("'")):
                                commit_msg = commit_msg[1:-1]
                            
                            result = subprocess.run(
                                git_cmd + ['-m', commit_msg],
                                capture_output=True,
                                text=True,
                                check=False
                            )
                        else:
                            result = subprocess.run(
                                command.split(),
                                capture_output=True,
                                text=True,
                                check=False
                            )
                    else:
                        result = subprocess.run(
                            command.split(),
                            capture_output=True,
                            text=True,
                            check=False
                        )
                else:
                    result = subprocess.run(
                        command.split(),
                        capture_output=True,
                        text=True,
                        check=False
                    )
                
                if result.returncode != 0:
                    print(f"⚠️ Command failed: {result.stderr}")
                    
                    # Special handling for commit failures - try with a simpler message
                    if command.startswith('git commit') and 'error: pathspec' in result.stderr:
                        print("🔄 Trying with simplified commit message...")
                        simple_commit_msg = f"Fix issue #{issue_id}"
                        result = subprocess.run(
                            ['git', 'commit', '-m', simple_commit_msg],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        if result.returncode == 0:
                            print(f"✅ Commit succeeded with simplified message: {result.stdout}")
                        else:
                            print(f"⚠️ Simplified commit also failed: {result.stderr}")
                    # Continue with other commands
                else:
                    print(f"✅ Command succeeded: {result.stdout}")
        
        os.chdir(current_dir)
        
        # Try to extract PR URL from git remote
        try:
            os.chdir(repo_path)
            remote_result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True
            )
            remote_url = remote_result.stdout.strip()
            
            # Convert SSH to HTTPS if needed
            if remote_url.startswith('git@'):
                remote_url = remote_url.replace('git@github.com:', 'https://github.com/').replace('.git', '')
            
            pr_url = f"{remote_url}/compare/main...{branch_name}"
            
            os.chdir(current_dir)
            
            return {
                "success": True,
                "output": fix_instructions,
                "pr_url": pr_url
            }
            
        except Exception as e:
            print(f"⚠️ Could not generate PR URL: {e}")
            os.chdir(current_dir)
            
            return {
                "success": True,
                "output": fix_instructions,
                "pr_url": None
            }
        
    except Exception as e:
        print(f"❌ Error running custom code fix: {e}")
        return {
            "success": False,
            "error": f"Error running custom code fix: {str(e)}"
        }

async def create_pr_with_composio(owner: str, repo: str, branch_name: str, issue_id: int, issue_title: str) -> Dict[str, Any]:
    """Create a PR using Composio GitHub tools"""
    await initialize_github_connection()
    user_id, github_username = get_user_context()
    try:
        if not github_tools:
            return {
                "success": False,
                "error": "GitHub tools not available"
            }
        # Dynamically determine the default branch of the upstream repo
        base_branch = get_default_branch(owner, repo)
        if not base_branch:
            base_branch = "main"
        # Create PR title and body
        pr_title = f"Fix issue #{issue_id}: {issue_title}"
        pr_body = f"This PR addresses issue #{issue_id}\n\nAutomatic fix generated by GDev."
        # Explicitly specify head and base
        head = f"{github_username}:{branch_name}"
        base = base_branch
        # Debug logging for PR creation
        print(f"[DEBUG] Creating PR with values:")
        print(f"  owner: {owner}")
        print(f"  repo: {repo}")
        print(f"  head: {head}")
        print(f"  base: {base}")
        print(f"  title: {pr_title}")
        print(f"  body: {pr_body}")
        # Try to use structured tool input if possible
        response = openai.chat.completions.create(
            model="gpt-4o",
            tools=github_tools,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant with access to GitHub tools. Create a pull request for the specified branch using the provided fields."
                },
                {
                    "role": "user",
                    "content": f"Create a pull request in repository '{owner}/{repo}' with:\n- title: '{pr_title}'\n- body: '{pr_body}'\n- head: '{head}'\n- base: '{base}'"
                },
            ],
            tool_choice="required"
        )
        result = composio.provider.handle_tool_calls(response=response, user_id=user_id)
        print(f"🔍 PR creation result: {json.dumps(result, indent=2)}")
        # Extract PR URL from result
        pr_url = None
        if isinstance(result, list):
            for item in result:
                if item.get('successful') and item.get('data'):
                    data = item['data']
                    if 'html_url' in data:
                        pr_url = data['html_url']
                        break
        if pr_url:
            return {
                "success": True,
                "pr_url": pr_url
            }
        else:
            return {
                "success": False,
                "error": "Failed to extract PR URL from response",
                "raw_response": result
            }
    except Exception as e:
        print(f"❌ Error creating PR with Composio: {e}")
        return {
            "success": False,
            "error": f"Error creating PR: {str(e)}"
        }

async def auto_fix_background_task(task_id: str, owner: str, repo: str, issue_number: int, branch_name: str, commit_message: str):
    """Background task to auto-fix an issue with fork-and-PR logic"""
    repo_name = f"{owner}/{repo}"
    temp_dir = None
    forked = False
    fork_owner = owner
    fork_repo = repo
    user_id, github_username = get_user_context()
    try:
        # Update task status
        auto_fix_tasks[task_id] = {
            "status": "analyzing",
            "repository": repo_name,
            "issue_number": issue_number,
            "branch_name": branch_name
        }
        # Get repository content and issue details
        repo_content = await get_repository_content(repo_name)
        repo_issues = await get_repository_issues(repo_name)
        # Find the specific issue
        issue = None
        issues_data = []
        if isinstance(repo_issues, list):
            for item in repo_issues:
                if item.get('successful') and item.get('data'):
                    data = item['data']
                    if 'details' in data:
                        issues_data = data['details']
                    elif isinstance(data, list):
                        issues_data = data
        for issue_item in issues_data:
            if issue_item.get('number') == issue_number:
                issue = issue_item
                break
        if not issue:
            auto_fix_tasks[task_id]["status"] = "failed"
            auto_fix_tasks[task_id]["error"] = f"Issue #{issue_number} not found in repository {repo_name}"
            return
        # Create repository context
        repository_info = {
            'name': repo,
            'full_name': repo_name,
            'description': repo_content.get('summary', f'Repository {repo_name}'),
            'content': repo_content.get('content', {})
        }
        # Analyze issue with LLM
        auto_fix_tasks[task_id]["status"] = "analyzing"
        issue_analysis = await analyze_issue_with_llm(issue, repository_info)
        # Determine if user is the owner (use github_username from env)
        if github_username and owner.lower() != github_username.lower():
            # Use Composio to fork the repo
            auto_fix_tasks[task_id]["status"] = "forking"
            print(f"🔄 Forking repository {owner}/{repo} for user {user_id} ({github_username})")
            try:
                response = openai.chat.completions.create(
                    model="gpt-4o",
                    tools=github_tools,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant with access to GitHub tools. Fork the repository if not already forked."},
                        {"role": "user", "content": f"Fork the repository {owner}/{repo} to my account."},
                    ],
                    tool_choice="required"
                )
                result = composio.provider.handle_tool_calls(response=response, user_id=user_id)
                print(f"🔍 Fork result: {json.dumps(result, indent=2)}")
                # Always use the current user's GitHub username for fork_owner
                fork_owner = github_username
                # Try to get the fork repo name from the result, fallback to original repo name
                if isinstance(result, list):
                    for item in result:
                        if item.get('successful') and item.get('data'):
                            data = item['data']
                            fork_repo = data.get('name', fork_repo)
                            forked = True
                            break
            except Exception as e:
                print(f"❌ Error forking repo: {e}")
                auto_fix_tasks[task_id]["status"] = "failed"
                auto_fix_tasks[task_id]["error"] = f"Failed to fork repository: {e}"
                return
        else:
            fork_owner = owner
            fork_repo = repo
        # Create temporary directory for cloning
        temp_dir = tempfile.mkdtemp(prefix="gdev_autofix_")
        repo_path = os.path.join(temp_dir, fork_repo)
        auto_fix_tasks[task_id]["status"] = "cloning"
        # Always clone from the fork (user's repo)
        clone_url = f"https://github.com/{fork_owner}/{fork_repo}.git"
        print(f"🔄 Cloning repository {clone_url} to {repo_path}")
        clone_result = subprocess.run(
            ["git", "clone", clone_url, repo_path],
            capture_output=True,
            text=True,
            check=False
        )
        if clone_result.returncode != 0:
            auto_fix_tasks[task_id]["status"] = "failed"
            auto_fix_tasks[task_id]["error"] = f"Failed to clone repository: {clone_result.stderr}"
            return
        # Ensure remote origin is set to the fork before pushing
        os.chdir(repo_path)
        subprocess.run(["git", "remote", "set-url", "origin", clone_url], capture_output=True, text=True)
        os.chdir(temp_dir)
        # Generate branch name if not provided
        if not branch_name:
            branch_name = f"fix/issue-{issue_number}-{uuid.uuid4().hex[:8]}"
        auto_fix_tasks[task_id]["branch_name"] = branch_name
        auto_fix_tasks[task_id]["status"] = "fixing"
        # Run custom code fix to fix the issue
        fix_result = await run_custom_code_fix(repo_path, issue_analysis, branch_name)
        if not fix_result["success"]:
            auto_fix_tasks[task_id]["status"] = "failed"
            auto_fix_tasks[task_id]["error"] = fix_result["error"]
            return
        # Create a PR from fork/branch to upstream
        auto_fix_tasks[task_id]["status"] = "creating_pr"
        pr_result = await create_pr_with_composio(owner, repo, branch_name, issue_number, issue_analysis.title)
        if pr_result["success"]:
            pr_url = pr_result["pr_url"]
            auto_fix_tasks[task_id]["status"] = "completed"
            auto_fix_tasks[task_id]["pr_url"] = pr_url
        else:
            auto_fix_tasks[task_id]["status"] = "partial_success"
            auto_fix_tasks[task_id]["error"] = f"Fixed issue but failed to create PR: {pr_result.get('error')}"
            return
    except Exception as e:
        print(f"❌ Error in auto-fix background task: {e}")
        auto_fix_tasks[task_id]["status"] = "failed"
        auto_fix_tasks[task_id]["error"] = str(e)
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                print(f"🧹 Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                print(f"⚠️ Warning: Failed to clean up temporary directory: {e}")

@app.post("/repository/{owner}/{repo}/issues/{issue_number}/auto-fix", response_model=AutoFixStatus)
async def auto_fix_issue(owner: str, repo: str, issue_number: int, request: AutoFixRequest, background_tasks: BackgroundTasks):
    """Auto-fix an issue using Claude Code and create a PR"""
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Get branch name and commit message from request or generate defaults
    branch_name = request.branch_name or f"fix/issue-{issue_number}-{uuid.uuid4().hex[:8]}"
    commit_message = request.commit_message or f"Fix issue #{issue_number}"
    
    # Initialize task status
    auto_fix_tasks[task_id] = {
        "status": "pending",
        "repository": f"{owner}/{repo}",
        "issue_number": issue_number,
        "branch_name": branch_name
    }
    
    # Start background task
    background_tasks.add_task(
        auto_fix_background_task,
        task_id,
        owner,
        repo,
        issue_number,
        branch_name,
        commit_message
    )
    
    return AutoFixStatus(
        task_id=task_id,
        status="pending",
        repository=f"{owner}/{repo}",
        issue_number=issue_number,
        branch_name=branch_name
    )

@app.get("/auto-fix/{task_id}", response_model=AutoFixStatus)
async def get_auto_fix_status(task_id: str):
    """Get the status of an auto-fix task"""
    if task_id not in auto_fix_tasks:
        raise HTTPException(status_code=404, detail="Auto-fix task not found")
    
    task_info = auto_fix_tasks[task_id]
    
    return AutoFixStatus(
        task_id=task_id,
        status=task_info.get("status", "unknown"),
        repository=task_info.get("repository", ""),
        issue_number=task_info.get("issue_number", 0),
        branch_name=task_info.get("branch_name"),
        pr_url=task_info.get("pr_url"),
        error=task_info.get("error")
    )

@app.post("/repository/{owner}/{repo}/issues/{issue_number}/auto-fix/vaultsense", response_model=AutoFixStatus)
async def auto_fix_vaultsense_issue(owner: str, repo: str, issue_number: int, request: AutoFixRequest, background_tasks: BackgroundTasks):
    """Auto-fix an issue in the VaultSense repository using Claude Code and create a PR"""
    # Override the repository to always be VaultSense
    owner = "Fre-dev"
    repo = "VaultSense"
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Get branch name and commit message from request or generate defaults
    branch_name = request.branch_name or f"fix/issue-{issue_number}-{uuid.uuid4().hex[:8]}"
    commit_message = request.commit_message or f"Fix issue #{issue_number}"
    
    # Initialize task status
    auto_fix_tasks[task_id] = {
        "status": "pending",
        "repository": f"{owner}/{repo}",
        "issue_number": issue_number,
        "branch_name": branch_name
    }
    
    # Start background task
    background_tasks.add_task(
        auto_fix_background_task,
        task_id,
        owner,
        repo,
        issue_number,
        branch_name,
        commit_message
    )
    
    return AutoFixStatus(
        task_id=task_id,
        status="pending",
        repository=f"{owner}/{repo}",
        issue_number=issue_number,
        branch_name=branch_name
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Dynamically check GitHub connection status
    composio_auth_url = None
    await initialize_github_connection()
    user_id, _ = get_user_context()
    github_connected = github_tools is not None and len(github_tools) > 0
    if not github_connected:
        try:
            connection_request = composio.toolkits.authorize(user_id=user_id, toolkit="github")
            composio_auth_url = getattr(connection_request, 'redirect_url', None)
        except Exception as e:
            composio_auth_url = None
    return {
        "status": "healthy", 
        "github_connected": github_connected,
        "github_tools_available": len(github_tools) if github_tools else 0,
        "available_tools": [tool.get('function', {}).get('name', 'Unknown') for tool in github_tools] if github_tools else [],
        "auto_fix_tasks": len(auto_fix_tasks),
        "composio_auth_url": composio_auth_url
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)



