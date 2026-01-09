import json
from glob import glob

with open("issues/issues.json") as f:
    issues = json.load(f)

docs = []

for issue in issues:
    n = issue["number"]
    with open(f"issues/issue_{n}.details.json") as f:
        comments = json.load(f)["comments"]

    text = f"""
ISSUE #{n}
TITLE: {issue['title']}
AUTHOR: {issue['author']['login']}
CREATED: {issue['createdAt']}
UPDATED: {issue['updatedAt']}
CLOSED: {issue['closedAt']}

BODY:
{issue['body']}

COMMENTS:
{" ".join(c['body'] for c in comments)}
    """

    docs.append({
        "id": f"issue_{n}",
        "type": "issue",
        "text": text,
        "metadata": {
            "author": issue["author"]["login"],
            "labels": [l["name"] for l in issue["labels"]],
            "date": issue["createdAt"]
        }
    })

with open("rag_issues.json", "w") as f:
    json.dump(docs, f, indent=2)
