#!/bin/bash

# Fail fast; treat unset vars as errors; propagate pipeline failures
set -euo pipefail

echo "Fetching PRs for annual report..."

echo "  - Medley"
gh pr list \
  --repo Interlisp/medley \
  --state all \
  --limit 1000 \
  --json number,title,author,createdAt,mergedAt,body,labels \
  --jq '[.[] | select(.createdAt > "2025-01-01")]' \
  > PRs/medley_prs.json

for pr in $(jq -r '.[].number' PRs/medley_prs.json); do
  gh pr view $pr \
    --repo Interlisp/medley \
    --json comments,reviews,files \
    > PRs/medley_prs_$pr.details.json
done

echo "  - Maiko"
gh pr list \
  --repo Interlisp/maiko \
  --state all \
  --limit 1000 \
  --json number,title,author,createdAt,mergedAt,body,labels \
  --jq '[.[] | select(.createdAt > "2025-01-01")]' \
  > PRs/maiko_prs.json 

for pr in $(jq -r '.[].number' PRs/maiko_prs.json); do
  gh pr view $pr \
    --repo Interlisp/maiko \
    --json comments,reviews,files \
    > PRs/maiko_prs_$pr.details.json
done

echo "  - Interlisp.github.io"
gh pr list \
  --repo Interlisp/Interlisp.github.io \
  --state all \
  --limit 1000 \
  --json number,title,author,createdAt,mergedAt,body,labels \
  --jq '[.[] | select(.createdAt > "2025-01-01")]' \
  > PRs/Interlisp.github.io_prs.json

for pr in $(jq -r '.[].number' PRs/Interlisp.github.io_prs.json); do
  gh pr view $pr \
    --repo Interlisp/Interlisp.github.io \
    --json comments,reviews,files \
    > PRs/Interlisp.github.io_prs_$pr.details.json
done

echo "  - online"
gh pr list \
  --repo Interlisp/online \
  --state all \
  --limit 1000 \
  --json number,title,author,createdAt,mergedAt,body,labels \
  --jq '[.[] | select(.createdAt > "2025-01-01")]' \
  > PRs/online_prs.json

for pr in $(jq -r '.[].number' PRs/online_prs.json); do
  gh pr view $pr \
    --repo Interlisp/online \
    --json comments,reviews,files \
    > PRs/online_prs_$pr.details.json
done

echo "  - gitbook"
gh pr list \
  --repo Interlisp/gitbook \
  --state all \
  --limit 1000 \
  --json number,title,author,createdAt,mergedAt,body,labels \
  --jq '[.[] | select(.createdAt > "2025-01-01")]' \
  > PRs/gitbook_prs.json

for pr in $(jq -r '.[].number' PRs/gitbook_prs.json); do
  gh pr view $pr \
    --repo Interlisp/gitbook \
    --json comments,reviews,files \
    > PRs/gitbook_prs_$pr.details.json
done

