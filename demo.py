#!/usr/bin/env python3
"""
Demo script for GitHub Issue Analyzer API
Shows how to use the API programmatically
"""

import requests
import json
import time
from typing import Dict, Any

# Configuration
API_BASE_URL = "http://localhost:8000"

def check_api_health():
    """Check if the API is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API is healthy!")
            return response.json()
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to API: {e}")
        return None

def demo_repository_analysis(owner: str, repo: str):
    """Demo repository analysis"""
    print(f"\n🔍 Analyzing repository: {owner}/{repo}")
    
    # Get repository statistics
    print("📊 Getting repository statistics...")
    stats_response = requests.get(f"{API_BASE_URL}/repository/{owner}/{repo}/issues/stats")
    
    if stats_response.status_code == 200:
        stats = stats_response.json()
        print(f"✅ Repository stats:")
        print(f"   - Total issues: {stats.get('total_issues', 0)}")
        print(f"   - Open issues: {stats.get('open_issues', 0)}")
        print(f"   - Closed issues: {stats.get('closed_issues', 0)}")
    else:
        print(f"❌ Failed to get stats: {stats_response.status_code}")
    
    # Get analyzed issues
    print("\n🔍 Getting analyzed issues...")
    issues_response = requests.get(
        f"{API_BASE_URL}/repository/{owner}/{repo}/issues",
        params={"limit": 5, "include_closed": False}
    )
    
    if issues_response.status_code == 200:
        issues = issues_response.json()
        print(f"✅ Found {len(issues)} issues")
        
        for i, issue in enumerate(issues[:3]):  # Show first 3 issues
            print(f"\n📋 Issue #{issue.get('issue_id')}: {issue.get('title')}")
            print(f"   Priority: {issue.get('priority')}")
            print(f"   Complexity: {issue.get('complexity')}")
            print(f"   Analysis: {issue.get('analysis', 'No analysis')[:100]}...")
    else:
        print(f"❌ Failed to get issues: {issues_response.status_code}")

def demo_specific_issue(owner: str, repo: str, issue_number: int):
    """Demo specific issue analysis"""
    print(f"\n🎯 Analyzing specific issue #{issue_number}")
    
    response = requests.get(f"{API_BASE_URL}/repository/{owner}/{repo}/issues/{issue_number}")
    
    if response.status_code == 200:
        issue = response.json()
        print(f"✅ Issue analysis:")
        print(f"   Title: {issue.get('title')}")
        print(f"   Priority: {issue.get('priority')}")
        print(f"   Complexity: {issue.get('complexity')}")
        print(f"   Analysis: {issue.get('analysis', 'No analysis')[:200]}...")
        print(f"   Solution: {issue.get('suggested_solution', 'No solution')[:200]}...")
    else:
        print(f"❌ Failed to analyze issue: {response.status_code}")

def demo_auto_fix(owner: str, repo: str, issue_number: int):
    """Demo auto-fix functionality"""
    print(f"\n🚀 Starting auto-fix for issue #{issue_number}")
    
    # Start auto-fix
    response = requests.post(
        f"{API_BASE_URL}/repository/{owner}/{repo}/issues/{issue_number}/auto-fix",
        json={"branch_name": f"demo-fix-{issue_number}"}
    )
    
    if response.status_code == 200:
        result = response.json()
        task_id = result.get('task_id')
        print(f"✅ Auto-fix started! Task ID: {task_id}")
        
        # Monitor the task
        print("📊 Monitoring auto-fix progress...")
        for i in range(10):  # Check for 10 iterations
            time.sleep(2)
            
            status_response = requests.get(f"{API_BASE_URL}/auto-fix/{task_id}")
            if status_response.status_code == 200:
                status = status_response.json()
                current_status = status.get('status', 'unknown')
                print(f"   Status: {current_status}")
                
                if current_status in ['completed', 'failed', 'partial_success']:
                    if status.get('pr_url'):
                        print(f"   ✅ PR created: {status['pr_url']}")
                    if status.get('error'):
                        print(f"   ❌ Error: {status['error']}")
                    break
            else:
                print(f"   ❌ Failed to get status: {status_response.status_code}")
    else:
        print(f"❌ Failed to start auto-fix: {response.status_code}")

def main():
    """Main demo function"""
    print("🐙 GitHub Issue Analyzer Demo")
    print("=" * 40)
    
    # Check API health
    health_data = check_api_health()
    if not health_data:
        print("❌ Cannot proceed without API connection")
        return
    
    # Demo configuration
    demo_owner = "octocat"
    demo_repo = "Hello-World"
    demo_issue = 1
    
    print(f"\n🎯 Demo Configuration:")
    print(f"   Repository: {demo_owner}/{demo_repo}")
    print(f"   Issue: #{demo_issue}")
    print("=" * 40)
    
    # Run demos
    try:
        # Demo 1: Repository analysis
        demo_repository_analysis(demo_owner, demo_repo)
        
        # Demo 2: Specific issue analysis
        demo_specific_issue(demo_owner, demo_repo, demo_issue)
        
        # Demo 3: Auto-fix (optional - can be slow)
        print(f"\n🚀 Auto-fix demo (this may take several minutes)...")
        user_input = input("Do you want to run the auto-fix demo? (y/n): ")
        if user_input.lower() == 'y':
            demo_auto_fix(demo_owner, demo_repo, demo_issue)
        else:
            print("⏭️  Skipping auto-fix demo")
        
        print("\n✅ Demo completed!")
        
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")

if __name__ == "__main__":
    main() 