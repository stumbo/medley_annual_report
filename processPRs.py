import json
from pathlib import Path

REPOS = [
    ("medley", "Interlisp/medley"),
    ("maiko", "Interlisp/maiko"),
    ("Interlisp.github.io", "Interlisp/Interlisp.github.io"),
    ("online", "Interlisp/online"),
    ("gitbook", "Interlisp/gitbook"),
]

def load_repo_prs(repo_key: str):
    base = Path("PRs")
    list_path = base / f"{repo_key}_prs.json"
    if not list_path.exists():
        return []
    with open(list_path) as f:
        return json.load(f)

def load_details(repo_key: str, number: int):
    base = Path("PRs")
    details_path = base / f"{repo_key}_prs_{number}.details.json"
    if not details_path.exists():
        return {"comments": [], "reviews": [], "files": []}
    with open(details_path) as f:
        return json.load(f)

docs = []

for repo_key, _ in REPOS:
    prs = load_repo_prs(repo_key)
    for pr in prs:
        pr_id = pr.get("number")
        title = pr.get("title", "")
        author_login = pr.get("author", {}).get("login", "")
        details = load_details(repo_key, pr_id)

        comments_text = " ".join((c.get("body") or "") for c in details.get("comments", []))
        reviews_text = " ".join((r.get("body") or "") for r in details.get("reviews", []))
        file_paths = [f.get("path") for f in details.get("files", []) if f.get("path")]

        full_text = f"""
{pr.get('body','')}

COMMENTS:
{comments_text}

REVIEWS:
{reviews_text}
        """

        docs.append({
            "id": f"{repo_key}_pr_{pr_id}",
            "type": "pr",
            "text": full_text,
            "metadata": {
                "repo": repo_key,
                "author": author_login,
                "date": pr.get('createdAt', ''),
                "merged": pr.get('mergedAt', ''),
                "labels": [l.get('name') for l in pr.get('labels', [])],
                "subject": title,
                "files": file_paths,
            }
        })

with open("rag_prs.json", "w") as f:
    json.dump(docs, f, indent=2)
