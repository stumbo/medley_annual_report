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
from html.parser import HTMLParser


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


def extract_body_text_without_tables(html_content):
    """
    Extract text from HTML body section, excluding any content within table tags.
    """
    class BodyTextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_body = False
            self.in_table = 0
            self.text_parts = []
        
        def handle_starttag(self, tag, attrs):
            if tag == 'body':
                self.in_body = True
            elif tag == 'table':
                self.in_table += 1
        
        def handle_endtag(self, tag):
            if tag == 'body':
                self.in_body = False
            elif tag == 'table':
                self.in_table = max(0, self.in_table - 1)
        
        def handle_data(self, data):
            if self.in_body and self.in_table == 0:
                self.text_parts.append(data)
    
    parser = BodyTextExtractor()
    parser.feed(html_content)
    
    # Join text parts and clean up whitespace
    text = ' '.join(parser.text_parts)
    # Collapse multiple whitespaces/newlines
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_text_body(msg):
    """
    Extract text body from an email message.
    
    For multipart/alternative messages, prefer HTML content over plain text.
    For other multipart messages, extract plain text if available.
    
    Special handling for "Recap of your meeting with Interlisp" emails:
    - Extract only body section content
    - Remove all table elements
    - Return only text content
    """
    body = ""
    html_body = ""
    new_content_type = ""
    
    # Check if this is a "Recap of your meeting with Interlisp" email
    subject = msg.get('Subject', '')
    is_recap_email = "Recap of your meeting with Interlisp" in subject
    
    if msg.is_multipart():
        content_type = msg.get_content_type()
        
        # For multipart/alternative, prefer HTML over plain text
        if content_type == "multipart/alternative":
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    try:
                        payload = part.get_payload(decode=True)
                        new_content_type = part.get_content_type()
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            html_body = payload.decode(charset, errors='replace')
                            break
                    except Exception:
                        pass
            
            # If no HTML found, fall back to plain text
            if not html_body:
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            payload = part.get_payload(decode=True)
                            new_content_type = part.get_content_type()
                            if payload:
                                charset = part.get_content_charset() or 'utf-8'
                                body = payload.decode(charset, errors='replace')
                                break
                        except Exception:
                            pass
            else:
                body = html_body
                # Apply special processing for recap emails
                if is_recap_email:
                    body = extract_body_text_without_tables(html_body)
        else:
            # For other multipart messages, look for text/plain
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition", ""))
                
                # Skip attachments
                if "attachment" in content_disposition:
                    continue
                
                if part.get_content_type() == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        new_content_type = part.get_content_type()
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
                new_content_type = msg.get_content_type()
                
                # Apply special processing for recap emails with HTML content
                if is_recap_email and msg.get_content_type() == "text/html":
                    body = extract_body_text_without_tables(body)
        except Exception:
            pass
    
    return body.strip(), new_content_type


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


def extract_email_addresses(field_value):
    """Extract email addresses from a field value (can be comma-separated)."""
    if not field_value:
        return []
    
    addresses = []
    # Split by comma and extract email addresses
    for item in field_value.split(','):
        item = item.strip()
        # Parse "Name <email>" format
        match = re.search(r'<([^>]+)>', item)
        if match:
            addresses.append(match.group(1).strip())
        elif '@' in item:
            addresses.append(item)
    
    return addresses


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
    body, new_content_type = extract_text_body(msg)
    message_id = msg.get('Message-ID', filepath.stem)
    if new_content_type != "":
        content_type = new_content_type
    else:
        content_type = msg.get('Content-Type', '')
    
    # Extract TO, CC, and In-Reply-To fields
    to_addresses = extract_email_addresses(msg.get('To', ''))
    cc_addresses = extract_email_addresses(msg.get('Cc', ''))
    in_reply_to = msg.get('In-Reply-To', '')
    
    # Try to parse date
    try:
        date_obj = parsedate_to_datetime(date_str)
        iso_date = date_obj.isoformat()
    except (ValueError, TypeError):
        iso_date = date_str
    
    # Create unique ID from message-id or filename
    clean_id = re.sub(r'[<>@\s]', '_', message_id)
    doc_id = f"email_{clean_id}"
    
    return {
        "id": doc_id,
        "type": "message",
        "body": body,
        "metadata": {
            "author": author_name,
            "email": author_email,
            "subject": subject,
            "date": iso_date,
            "to": to_addresses,
            "cc": cc_addresses,
            "in_reply_to": in_reply_to,
            "content_type": content_type,
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
