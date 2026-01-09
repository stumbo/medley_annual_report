# Copilot Instructions for annual_report

## Project Overview

This project collects and processes GitHub issues, pull requests, and Google Groups messages from the **Interlisp** project ecosystem to generate RAG (Retrieval-Augmented Generation) documents for annual reporting.

### Data Pipeline Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Data Sources   │ --> │  Shell Scripts   │ --> │  Python Scripts │ --> RAG JSON
│  (GitHub, GG)   │     │  (gh CLI fetch)  │     │  (transform)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

**Two-phase workflow:**
1. **Fetch phase** — Shell scripts (`getIssues.sh`, `getPRs.sh`) use GitHub CLI to pull raw JSON
2. **Transform phase** — Python scripts (`processIssues.py`, `processPRs.py`) convert to RAG format

## Key Conventions

### RAG Document Schema
All processors must output documents following this structure (see [verify_rag_docs.py](verify_rag_docs.py)):
```python
{
    "id": "unique_identifier",
    "type": "issue" | "pr" | "message",
    "text": "combined searchable text content",
    "metadata": {
        "author": "login",
        "date": "ISO timestamp",
        "labels": [],
        # type-specific fields: repo, threadId, subject
    }
}
```

### Target Repositories
PRs are fetched from these Interlisp repos (defined in [processPRs.py](processPRs.py)):
- `Interlisp/medley`, `Interlisp/maiko`, `Interlisp/online`
- `Interlisp/gitbook`, `Interlisp/Interlisp.github.io`

Issues are fetched only from `Interlisp/medley`.

### File Organization
- `issues/` — Raw issue JSON: `issues.json` (list) + `issue_{N}.details.json` (comments)
- `PRs/` — Raw PR JSON: `{repo}_prs.json` (list) + `{repo}_prs_{N}.details.json`
- `rag_*.json` — Final RAG-ready output files

## Developer Workflows

### Refreshing GitHub Data
```bash
# Requires: gh auth login
./getIssues.sh   # Fetches 2025+ issues from medley repo
./getPRs.sh      # Fetches 2025+ PRs from all Interlisp repos
```

### Processing to RAG Format
```bash
python processIssues.py  # outputs rag_issues.json
python processPRs.py     # outputs rag_prs.json
```

### Validating Output
```bash
python verify_rag_docs.py rag_issues.json rag_prs.json
# Reports: doc counts, types, repos, top authors, missing fields
```

### Google Groups Scraping
Two approaches exist:
- [group_scrapper.py](group_scrapper.py) — Selenium-based web scraper for `groups.google.com/g/lispcore`
- [groups_to_rag.py](groups_to_rag.py) — Gmail API with service account (requires domain-wide delegation)

## Code Patterns

### Safe JSON Field Access
When accessing GitHub API responses, use `.get()` with defaults to handle missing fields:
```python
author = pr.get('author', {}).get('login', '')
comments_text = " ".join((c.get("body") or "") for c in details.get("comments", []))
```

### Date Filtering
Scripts filter by date at fetch time using `gh` CLI's `--search` or `--jq`:
```bash
--search "updated:>=2025-01-01"           # Issues
--jq '[.[] | select(.createdAt > "2025-01-01")]'  # PRs
```

## Dependencies
- **gh** (GitHub CLI) — authenticated with repo access
- **jq** — JSON processing in shell scripts
- **Python packages**: `requests`, `beautifulsoup4`, `selenium` (for web scraping), `google-api-python-client` (for Gmail API)
