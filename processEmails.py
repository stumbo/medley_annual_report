#!/usr/bin/env python3
"""
Process email messages from lispUsers folder to create RAG documents.

Filters:
- Only include messages sent in 2025
- Exclude automated GitHub notifications related to PRs or Issues

Output: rag_emails.json in the same format as rag_issues.json and rag_prs.json
"""

import json
import os
import re
import email
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path
from datetime import datetime


def is_github_notification(msg):
    """
    Check if the message is an automated GitHub notification for PRs/Issues.
    
    These typically have:
    - From address containing 'notifications@github.com'
    - Subject containing patterns like '(Issue #', '(PR #', '(Discussion #'
    - Return-Path containing 'noreply@github.com'
    """
    from_addr = msg.get('From', '')
    subject = msg.get('Subject', '')
    return_path = msg.get('Return-Path', '')
    
    # Check if it's from GitHub notifications
    if 'notifications@github.com' in from_addr:
        return True
    
    if 'noreply@github.com' in return_path:
        return True
    
    # Check subject patterns for GitHub-related notifications
    github_patterns = [
        r'\(Issue #\d+\)',
        r'\(PR #\d+\)',
        r'\(Discussion #\d+\)',
        r'\[Interlisp[/_]\w+\]',  # GitHub repo notification prefix
    ]
    
    for pattern in github_patterns:
        if re.search(pattern, subject):
            return True
    
    return False


def is_from_2025(msg):
    """Check if the message was sent in 2025."""
    date_str = msg.get('Date', '')
    if not date_str:
        return False
    
    try:
        date_obj = parsedate_to_datetime(date_str)
        return date_obj.year == 2025
    except (ValueError, TypeError):
        # Try to parse date from filename as fallback
        return False


def extract_text_body(msg):
    """Extract the plain text body from an email message."""
    body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            
            # Skip attachments
            if "attachment" in content_disposition:
                continue
            
            if content_type == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, errors='replace')
                        break
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                body = payload.decode(charset, errors='replace')
        except Exception:
            pass
    
    return body.strip()


def extract_author(msg):
    """Extract author name and email from the From field."""
    from_addr = msg.get('From', '')
    
    # Parse "Name <email>" format
    match = re.match(r'^([^<]+)\s*<([^>]+)>', from_addr)
    if match:
        name = match.group(1).strip().strip("'\"")
        email_addr = match.group(2).strip()
        return name, email_addr
    
    # Just email address
    return from_addr, from_addr


def parse_email_file(filepath):
    """Parse a single .eml file and return an email message object."""
    try:
        with open(filepath, 'rb') as f:
            msg = BytesParser(policy=policy.default).parse(f)
        return msg
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")
        return None


def create_rag_document(msg, filepath):
    """Create a RAG document from an email message."""
    author_name, author_email = extract_author(msg)
    date_str = msg.get('Date', '')
    subject = msg.get('Subject', '')
    body = extract_text_body(msg)
    message_id = msg.get('Message-ID', filepath.stem)
    
    # Try to parse date
    try:
        date_obj = parsedate_to_datetime(date_str)
        iso_date = date_obj.isoformat()
    except (ValueError, TypeError):
        iso_date = date_str
    
    # Create combined text for RAG
    text = f"""
EMAIL MESSAGE
SUBJECT: {subject}
FROM: {author_name} <{author_email}>
DATE: {iso_date}

BODY:
{body}
    """.strip()
    
    # Create unique ID from message-id or filename
    clean_id = re.sub(r'[<>@\s]', '_', message_id)
    doc_id = f"email_{clean_id}"
    
    return {
        "id": doc_id,
        "type": "message",
        "text": text,
        "metadata": {
            "author": author_name,
            "email": author_email,
            "subject": subject,
            "date": iso_date,
            "source_file": filepath.name
        }
    }


def main():
    lispusers_dir = Path("lispUsers")
    
    if not lispusers_dir.exists():
        print(f"Error: {lispusers_dir} directory not found")
        return
    
    eml_files = list(lispusers_dir.glob("*.eml"))
    print(f"Found {len(eml_files)} .eml files in {lispusers_dir}")
    
    docs = []
    skipped_non_2025 = 0
    skipped_github = 0
    processed = 0
    errors = 0
    
    for filepath in eml_files:
        msg = parse_email_file(filepath)
        if msg is None:
            errors += 1
            continue
        
        # Filter: only 2025 messages
        if not is_from_2025(msg):
            skipped_non_2025 += 1
            continue
        
        # Filter: exclude GitHub notifications
        if is_github_notification(msg):
            skipped_github += 1
            continue
        
        # Create RAG document
        doc = create_rag_document(msg, filepath)
        docs.append(doc)
        processed += 1
    
    # Write output
    output_file = Path("rag_emails.json")
    with open(output_file, 'w') as f:
        json.dump(docs, f, indent=2)
    
    # Print summary
    print(f"\nProcessing Summary:")
    print(f"  Total files: {len(eml_files)}")
    print(f"  Processed: {processed}")
    print(f"  Skipped (not 2025): {skipped_non_2025}")
    print(f"  Skipped (GitHub notifications): {skipped_github}")
    print(f"  Errors: {errors}")
    print(f"\nOutput written to: {output_file}")
    
    # Print author summary
    if docs:
        authors = {}
        for doc in docs:
            author = doc["metadata"]["author"]
            authors[author] = authors.get(author, 0) + 1
        
        print(f"\nTop authors:")
        for author, count in sorted(authors.items(), key=lambda x: -x[1])[:10]:
            print(f"  {author}: {count}")


if __name__ == "__main__":
    main()
