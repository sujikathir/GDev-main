import streamlit as st
import requests
import json
import time
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Any, Optional
import threading

# Configuration
from config import API_BASE_URL, DEFAULT_ISSUE_LIMIT, MAX_ISSUE_LIMIT, DEFAULT_INCLUDE_CLOSED, CHART_COLORS

def poll_github_connection():
    """Poll /health every 3 seconds until github_connected is True, then rerun Streamlit"""
    for _ in range(40):  # Poll for up to 2 minutes
        try:
            resp = requests.get(f"{API_BASE_URL}/health", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("github_connected"):
                    st.experimental_rerun()
                    return
        except Exception:
            pass
        time.sleep(3)
    st.warning("GitHub connection not detected after 2 minutes. Please try again.")

def show_github_auth_ui(health_data):
    st.warning("GitHub is not connected. Please authorize via Composio to enable all features.")
    composio_auth_url = health_data.get("composio_auth_url")
    if composio_auth_url:
        st.markdown(
            f'<a href="{composio_auth_url}" target="_blank">'
            f'<button style="background-color:#ff4b4b;color:white;padding:0.5em 1.5em;border:none;border-radius:4px;font-size:1em;cursor:pointer;">'
            'Connect GitHub via Composio'
            '</button></a>',
            unsafe_allow_html=True
        )
        st.info("Waiting for GitHub connection...")
        poll_github_connection()
    else:
        st.info("No authorization URL available. Please restart the backend if you just authorized.")

def check_api_health():
    """Check if the API is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200, response.json()
    except requests.exceptions.RequestException:
        return False, None

def get_repository_issues(owner: str, repo: str, include_closed: bool = False, limit: int = 50):
    """Get analyzed issues from the API"""
    try:
        params = {
            "include_closed": include_closed,
            "limit": limit
        }
        response = requests.get(
            f"{API_BASE_URL}/repository/{owner}/{repo}/issues",
            params=params,
            timeout=120
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error fetching issues: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return None

def get_repository_stats(owner: str, repo: str):
    """Get repository issue statistics"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/repository/{owner}/{repo}/issues/stats",
            timeout=120
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error fetching stats: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return None

def get_raw_issues(owner: str, repo: str, include_closed: bool = False, limit: int = 50):
    """Get raw issues data"""
    try:
        params = {
            "include_closed": include_closed,
            "limit": limit
        }
        response = requests.get(
            f"{API_BASE_URL}/repository/{owner}/{repo}/issues/raw",
            params=params,
            timeout=120
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error fetching raw issues: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return None

def analyze_specific_issue(owner: str, repo: str, issue_number: int):
    """Analyze a specific issue"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/repository/{owner}/{repo}/issues/{issue_number}",
            timeout=120
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error analyzing issue: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return None

def start_auto_fix(owner: str, repo: str, issue_number: int, branch_name: str = None, commit_message: str = None):
    """Start auto-fix process for an issue"""
    try:
        data = {
            "owner": owner,
            "repo": repo,
            "issue_number": issue_number
        }
        if branch_name:
            data["branch_name"] = branch_name
        if commit_message:
            data["commit_message"] = commit_message
        
        response = requests.post(
            f"{API_BASE_URL}/repository/{owner}/{repo}/issues/{issue_number}/auto-fix",
            json=data,
            timeout=120
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error starting auto-fix: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return None

def get_auto_fix_status(task_id: str):
    """Get status of auto-fix task"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/auto-fix/{task_id}",
            timeout=60
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error getting auto-fix status: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return None

def create_issue_analysis_chart(issues: List[Dict]):
    """Create charts for issue analysis"""
    if not issues:
        return None, None, None
    
    # Priority distribution
    priority_counts = {}
    complexity_counts = {}
    
    for issue in issues:
        priority = issue.get('priority', 'Medium')
        complexity = issue.get('complexity', 'Medium')
        
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
        complexity_counts[complexity] = complexity_counts.get(complexity, 0) + 1
    
    # Create priority chart
    priority_df = pd.DataFrame(list(priority_counts.items()), columns=['Priority', 'Count'])
    priority_fig = px.pie(
        priority_df, 
        values='Count', 
        names='Priority',
        title='Issue Priority Distribution',
        color_discrete_map=CHART_COLORS
    )
    
    # Create complexity chart
    complexity_df = pd.DataFrame(list(complexity_counts.items()), columns=['Complexity', 'Count'])
    complexity_fig = px.pie(
        complexity_df, 
        values='Count', 
        names='Complexity',
        title='Issue Complexity Distribution',
        color_discrete_map=CHART_COLORS
    )
    
    # Create issue timeline
    issue_data = []
    for issue in issues:
        issue_data.append({
            'Issue #': issue.get('issue_id', 0),
            'Title': issue.get('title', 'No title'),
            'Priority': issue.get('priority', 'Medium'),
            'Complexity': issue.get('complexity', 'Medium')
        })
    
    issues_df = pd.DataFrame(issue_data)
    
    return priority_fig, complexity_fig, issues_df

def display_issue_analysis(issue: Dict):
    """Display detailed analysis of a single issue"""
    st.subheader(f"Issue #{issue.get('issue_id')}: {issue.get('title')}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Priority", issue.get('priority', 'Medium'))
    
    with col2:
        st.metric("Complexity", issue.get('complexity', 'Medium'))
    
    st.markdown("### Issue Description")
    st.text_area("Body", issue.get('body', 'No description'), height=100, disabled=True)
    
    st.markdown("### Analysis")
    st.markdown(issue.get('analysis', 'No analysis available'))
    
    st.markdown("### Suggested Solution")
    st.markdown(issue.get('suggested_solution', 'No solution suggested'))

def main():
    st.set_page_config(
        page_title="GitHub Issue Analyzer",
        page_icon="🐙",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🐙 GitHub Issue Analyzer")
    st.markdown("Analyze GitHub issues and get AI-powered solutions")
    
    # Check API health
    api_healthy, health_data = check_api_health()
    
    if not api_healthy:
        st.error("❌ API is not running. Please start the API server first.")
        st.info("To start the API server, run: `python src/main.py`")
        return
    
    # Show Composio GitHub authorization UI if not connected
    if not health_data.get("github_connected"):
        show_github_auth_ui(health_data)
        return
    
    st.success("✅ API is running and healthy!")
    
    # Display API health info
    if health_data:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("GitHub Connected", "✅" if health_data.get('github_connected') else "❌")
        with col2:
            st.metric("GitHub Tools", health_data.get('github_tools_available', 0))
        with col3:
            st.metric("Auto-fix Tasks", health_data.get('auto_fix_tasks', 0))
        with col4:
            st.metric("Status", health_data.get('status', 'Unknown'))
    
    st.divider()
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page",
        ["Repository Analysis", "Issue Analysis", "Auto-fix Issues", "API Health"]
    )
    
    if page == "Repository Analysis":
        show_repository_analysis()
    elif page == "Issue Analysis":
        show_issue_analysis()
    elif page == "Auto-fix Issues":
        show_auto_fix()
    elif page == "API Health":
        show_api_health(health_data)

def show_repository_analysis():
    st.header("📊 Repository Analysis")
    
    # Repository input
    col1, col2 = st.columns(2)
    with col1:
        owner = st.text_input("Repository Owner", placeholder="e.g., octocat")
    with col2:
        repo = st.text_input("Repository Name", placeholder="e.g., Hello-World")
    
    include_closed = st.checkbox("Include closed issues", value=DEFAULT_INCLUDE_CLOSED)
    limit = st.slider("Maximum issues to analyze", min_value=1, max_value=MAX_ISSUE_LIMIT, value=DEFAULT_ISSUE_LIMIT)
    
    if st.button("🔍 Analyze Repository", type="primary"):
        if not owner or not repo:
            st.error("Please enter both owner and repository name")
            return
        
        with st.spinner("Analyzing repository issues..."):
            # Get repository statistics
            stats = get_repository_stats(owner, repo)
            
            if stats:
                st.subheader("📈 Repository Statistics")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Issues", stats.get('total_issues', 0))
                with col2:
                    st.metric("Open Issues", stats.get('open_issues', 0))
                with col3:
                    st.metric("Closed Issues", stats.get('closed_issues', 0))
                with col4:
                    st.metric("Repository", f"{owner}/{repo}")
                
                # Priority and complexity charts
                if stats.get('issues_by_priority') or stats.get('issues_by_complexity'):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if stats.get('issues_by_priority'):
                            priority_data = stats['issues_by_priority']
                            priority_fig = px.pie(
                                values=list(priority_data.values()),
                                names=list(priority_data.keys()),
                                title="Issues by Priority"
                            )
                            st.plotly_chart(priority_fig, use_container_width=True)
                    
                    with col2:
                        if stats.get('issues_by_complexity'):
                            complexity_data = stats['issues_by_complexity']
                            complexity_fig = px.pie(
                                values=list(complexity_data.values()),
                                names=list(complexity_data.keys()),
                                title="Issues by Complexity"
                            )
                            st.plotly_chart(complexity_fig, use_container_width=True)
            
            # Get analyzed issues
            issues = get_repository_issues(owner, repo, include_closed, limit)
            
            if issues:
                st.subheader(f"🔍 Analyzed Issues ({len(issues)} found)")
                
                # Create charts
                priority_fig, complexity_fig, issues_df = create_issue_analysis_chart(issues)
                
                if priority_fig and complexity_fig:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.plotly_chart(priority_fig, use_container_width=True)
                    with col2:
                        st.plotly_chart(complexity_fig, use_container_width=True)
                
                # Display issues in an expandable table
                if not issues_df.empty:
                    st.subheader("📋 Issues List")
                    
                    # Add search functionality
                    search_term = st.text_input("🔍 Search issues by title", placeholder="Enter search term...")
                    
                    if search_term:
                        filtered_df = issues_df[issues_df['Title'].str.contains(search_term, case=False, na=False)]
                    else:
                        filtered_df = issues_df
                    
                    # Display issues with expandable details
                    for idx, row in filtered_df.iterrows():
                        issue = issues[idx]
                        
                        with st.expander(f"#{issue['issue_id']}: {issue['title']}"):
                            display_issue_analysis(issue)
                            
                            # Add auto-fix button
                            if st.button(f"🚀 Auto-fix Issue #{issue['issue_id']}", key=f"fix_{issue['issue_id']}"):
                                st.info("Auto-fix feature will be available in the 'Auto-fix Issues' page")

def show_issue_analysis():
    st.header("🔍 Individual Issue Analysis")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        owner = st.text_input("Repository Owner", key="issue_owner", placeholder="e.g., octocat")
    with col2:
        repo = st.text_input("Repository Name", key="issue_repo", placeholder="e.g., Hello-World")
    with col3:
        issue_number = st.number_input("Issue Number", min_value=1, value=1, key="issue_number")
    
    if st.button("🔍 Analyze Issue", type="primary"):
        if not owner or not repo:
            st.error("Please enter both owner and repository name")
            return
        
        with st.spinner("Analyzing issue..."):
            issue_analysis = analyze_specific_issue(owner, repo, issue_number)
            
            if issue_analysis:
                display_issue_analysis(issue_analysis)
                
                # Add auto-fix section
                st.divider()
                st.subheader("🚀 Auto-fix This Issue")
                
                col1, col2 = st.columns(2)
                with col1:
                    branch_name = st.text_input("Branch Name (optional)", 
                                              placeholder=f"fix/issue-{issue_number}")
                with col2:
                    commit_message = st.text_input("Commit Message (optional)", 
                                                placeholder=f"Fix issue #{issue_number}")
                
                if st.button("🚀 Start Auto-fix", type="primary"):
                    with st.spinner("Starting auto-fix process..."):
                        result = start_auto_fix(owner, repo, issue_number, branch_name, commit_message)
                        
                        if result:
                            st.success("✅ Auto-fix process started!")
                            st.json(result)
                            
                            # Store task ID in session state for monitoring
                            if 'auto_fix_tasks' not in st.session_state:
                                st.session_state.auto_fix_tasks = []
                            st.session_state.auto_fix_tasks.append(result['task_id'])

def show_auto_fix():
    st.header("🚀 Auto-fix Issues")
    
    # Manual auto-fix
    st.subheader("Start New Auto-fix")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        owner = st.text_input("Repository Owner", key="autofix_owner", placeholder="e.g., octocat")
    with col2:
        repo = st.text_input("Repository Name", key="autofix_repo", placeholder="e.g., Hello-World")
    with col3:
        issue_number = st.number_input("Issue Number", min_value=1, value=1, key="autofix_issue")
    
    col1, col2 = st.columns(2)
    with col1:
        branch_name = st.text_input("Branch Name (optional)", key="autofix_branch", 
                                  placeholder=f"fix/issue-{issue_number}")
    with col2:
        commit_message = st.text_input("Commit Message (optional)", key="autofix_commit", 
                                    placeholder=f"Fix issue #{issue_number}")
    
    if st.button("🚀 Start Auto-fix", type="primary"):
        if not owner or not repo:
            st.error("Please enter both owner and repository name")
            return
        
        with st.spinner("Starting auto-fix process..."):
            result = start_auto_fix(owner, repo, issue_number, branch_name, commit_message)
            
            if result:
                st.success("✅ Auto-fix process started!")
                st.json(result)
                
                # Store task ID in session state
                if 'auto_fix_tasks' not in st.session_state:
                    st.session_state.auto_fix_tasks = []
                st.session_state.auto_fix_tasks.append(result['task_id'])
    
    # Monitor existing tasks
    st.divider()
    st.subheader("📊 Monitor Auto-fix Tasks")
    
    if 'auto_fix_tasks' in st.session_state and st.session_state.auto_fix_tasks:
        st.info(f"Monitoring {len(st.session_state.auto_fix_tasks)} auto-fix tasks")
        
        # Auto-refresh status
        if st.button("🔄 Refresh Status"):
            pass  # This will trigger a rerun
        
        for task_id in st.session_state.auto_fix_tasks:
            with st.expander(f"Task: {task_id[:8]}..."):
                status = get_auto_fix_status(task_id)
                
                if status:
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        status_color = {
                            "pending": "🟡",
                            "analyzing": "🟡",
                            "cloning": "🟡",
                            "fixing": "🟡",
                            "creating_pr": "🟡",
                            "completed": "🟢",
                            "failed": "🔴",
                            "partial_success": "🟠"
                        }.get(status.get('status', 'unknown'), "⚪")
                        
                        st.metric("Status", f"{status_color} {status.get('status', 'unknown')}")
                    
                    with col2:
                        st.metric("Repository", status.get('repository', 'Unknown'))
                    
                    with col3:
                        st.metric("Issue #", status.get('issue_number', 0))
                    
                    if status.get('branch_name'):
                        st.info(f"Branch: {status['branch_name']}")
                    
                    if status.get('pr_url'):
                        st.success(f"PR Created: {status['pr_url']}")
                    
                    if status.get('error'):
                        st.error(f"Error: {status['error']}")
                    
                    # Progress bar for ongoing tasks
                    if status.get('status') in ['pending', 'analyzing', 'cloning', 'fixing', 'creating_pr']:
                        progress = {
                            'pending': 0.1,
                            'analyzing': 0.3,
                            'cloning': 0.5,
                            'fixing': 0.7,
                            'creating_pr': 0.9
                        }.get(status.get('status'), 0.5)
                        
                        st.progress(progress)
                        st.info("Task in progress... This may take several minutes.")
    else:
        st.info("No auto-fix tasks to monitor. Start a new auto-fix to see tasks here.")

def show_api_health(health_data):
    st.header("🏥 API Health Status")
    
    if health_data:
        st.json(health_data)
        
        # GitHub connection status
        st.subheader("🔗 GitHub Connection")
        if health_data.get('github_connected'):
            st.success("✅ GitHub connection is active")
        else:
            st.warning("⚠️ GitHub connection is not active")
        
        # Available tools
        st.subheader("🛠️ Available Tools")
        tools = health_data.get('available_tools', [])
        if tools:
            for tool in tools:
                st.write(f"• {tool}")
        else:
            st.info("No tools available")
        
        # Auto-fix tasks
        st.subheader("🚀 Auto-fix Tasks")
        task_count = health_data.get('auto_fix_tasks', 0)
        st.metric("Active Tasks", task_count)
        
        if task_count > 0:
            st.info("There are active auto-fix tasks running")
    else:
        st.error("Unable to retrieve health data")

if __name__ == "__main__":
    main() 