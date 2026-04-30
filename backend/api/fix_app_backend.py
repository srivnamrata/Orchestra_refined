import re
with open('/Users/Shared/Orchestra_refined/backend/api/app.py', 'r') as f:
    content = f.read()

bottlenecks_endpoint = """
@app.get("/api/mock/bottlenecks")
async def get_mock_bottlenecks():
    return {
        "bottlenecks": [
            {
                "id": "bn_git_01",
                "source": "github",
                "title": "PR Review Pending",
                "detail": "PR #142 'Update API Auth' has been waiting for review for 3 days.",
                "action_text": "Review PR"
            },
            {
                "id": "bn_slack_01",
                "source": "slack",
                "title": "Unanswered Question",
                "detail": "David asked a question about deployment in #engineering 4 hours ago.",
                "action_text": "Reply in Slack"
            },
            {
                "id": "bn_email_01",
                "source": "email",
                "title": "High Priority Email",
                "detail": "Client requested an urgent update on the Q3 roadmap.",
                "action_text": "Draft Reply"
            }
        ]
    }
"""

if "/api/mock/bottlenecks" not in content:
    content += bottlenecks_endpoint
    with open('/Users/Shared/Orchestra_refined/backend/api/app.py', 'w') as f:
        f.write(content)
