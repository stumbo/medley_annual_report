#!/bin/bash

set -e
echo "Retrieving issue information"
gh issue list \
  --repo Interlisp/medley \
  --state all \
  --limit 2000 \
  --search "updated:>=2025-01-01" \
  --json number,title,author,createdAt,updatedAt,closedAt,body,labels \
  > issues/issues.json

echo "Done getting issues"

echo "Get comments related to each issue"
for issue in $(jq '.[].number' issues/issues.json); do
  gh issue view $issue --repo Interlisp/medley --json comments > issues/issue_$issue.details.json
done
