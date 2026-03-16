#!/usr/bin/env python3
"""
Process email messages from lispUsers folder to create RAG documents.

Filters:
- Only include messages sent in 2025
- Exclude automated GitHub notifications related to PRs or Issues

Features:
- Chunks long email bodies for optimal RAG retrieval (500-1000 tokens per chunk)
- Prefers plain text over HTML when both available
- Extracts and processes text from common attachment types
- Converts HTML to clean markdown when needed
- Preserves contextual metadata in each chunk

Output: rag_emails.json optimized for vector embedding and retrieval
"""

import json
import os
import re
import email
import base64
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser
import html2text


# Chunking configuration for RAG
CHUNK_SIZE = 800  # Target tokens per chunk (rough approximation: 1 token ≈ 4 chars)
CHUNK_OVERLAP = 100  # Overlap between chunks to preserve context
MAX_CHUNK_CHARS = CHUNK_SIZE * 4  # Approximate character limit
OVERLAP_CHARS = CHUNK_OVERLAP * 4


def chunk_text(text, max_chars=MAX_CHUNK_CHARS, overlap_chars=OVERLAP_CHARS):
    """
    Split text into chunks at paragraph boundaries, preserving semantic units.
    
    Args:
        text: Text to chunk
        max_chars: Maximum characters per chunk (approximate)
        overlap_chars: Character overlap between chunks
    
    Returns:
        List of text chunks
    """
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    paragraphs = text.split('\n\n')
    current_chunk = []
    current_size = 0
    
    for para in paragraphs:
        para_size = len(para)
        
        # If single paragraph exceeds max size, split it
        if para_size > max_chars:
            # Save current chunk if not empty
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
            
            # Split long paragraph at sentence boundaries
            sentences = re.split(r'(?<=[.!?])\s+', para)
            for sentence in sentences:
                if current_size + len(sentence) > max_chars and current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    # Keep overlap from end of previous chunk
                    if overlap_chars > 0:
                        overlap_text = '\n\n'.join(current_chunk)[-overlap_chars:]
                        current_chunk = [overlap_text, sentence]
                        current_size = len(overlap_text) + len(sentence)
                    else:
                        current_chunk = [sentence]
                        current_size = len(sentence)
                else:
                    current_chunk.append(sentence)
                    current_size += len(sentence)
        
        # Add paragraph to current chunk if it fits
        elif current_size + para_size <= max_chars:
            current_chunk.append(para)
            current_size += para_size + 2  # +2 for \n\n
        
        # Start new chunk
        else:
            chunks.append('\n\n'.join(current_chunk))
            # Include overlap from previous chunk
            if overlap_chars > 0 and chunks:
                overlap_text = chunks[-1][-overlap_chars:]
                current_chunk = [overlap_text, para]
                current_size = len(overlap_text) + para_size
            else:
                current_chunk = [para]
                current_size = para_size
    
    # Add final chunk
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    return chunks


def html_to_markdown(html_content):
    """Convert HTML to clean markdown for better RAG embedding."""
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.ignore_emphasis = False
    h.body_width = 0  # Don't wrap lines
    h.ignore_tables = False
    
    markdown = h.handle(html_content)
    
    # Clean up excessive newlines
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    
    return markdown.strip()


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
    Extract text body from an email message, preferring plain text over HTML.
    
    When only HTML is available, converts to markdown for cleaner RAG content.
    Returns tuple: (body_content, content_type, was_converted_from_html)
    """
    plain_body = ""
    html_body = ""
    
    if msg.is_multipart():
        # First pass: look for plain text
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition:
                continue
                
            if part.get_content_type() == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        plain_body = payload.decode(charset, errors='replace')
                        break
                except Exception:
                    pass
        
        # Second pass: look for HTML if no plain text found
        if not plain_body:
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition", ""))
                if "attachment" in content_disposition:
                    continue
                    
                if part.get_content_type() == "text/html":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            html_body = payload.decode(charset, errors='replace')
                            break
                    except Exception:
                        pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                content_type = msg.get_content_type()
                
                if content_type == "text/plain":
                    plain_body = payload.decode(charset, errors='replace')
                elif content_type == "text/html":
                    html_body = payload.decode(charset, errors='replace')
        except Exception:
            pass
    
    # Prefer plain text, convert HTML to markdown if needed
    if plain_body:
        return plain_body.strip(), "text/plain", False
    elif html_body:
        markdown_body = html_to_markdown(html_body)
        return markdown_body, "text/html", True
    
    return "", "text/plain", False


def extract_attachment_text(part):
    """
    Extract text content from email attachments when possible.
    
    Supports:
    - Plain text files (.txt, .log, .md, etc.)
    - Code files (.py, .js, .lisp, etc.)
    
    Returns tuple: (content, content_type, success)
    """
    content_type = part.get_content_type()
    filename = part.get_filename() or "unknown"
    
    # Handle text-based attachments
    text_types = [
        "text/plain",
        "text/x-python",
        "text/x-python-script", 
        "text/x-log",
        "text/markdown",
        "application/x-python",
        "application/x-sh",
    ]
    
    # Also check file extension
    text_extensions = ['.txt', '.log', '.py', '.js', '.lisp', '.lsp', 
                      '.md', '.sh', '.bash', '.json', '.xml', '.csv',
                      '.c', '.h', '.cpp', '.java', '.rs']
    
    is_text = (content_type in text_types or 
               any(filename.lower().endswith(ext) for ext in text_extensions))
    
    if is_text:
        try:
            payload = part.get_payload(decode=True)
            if payload:
                # Try multiple encodings
                for encoding in ['utf-8', 'latin-1', 'cp1252']:
                    try:
                        text = payload.decode(encoding, errors='strict')
                        return text.strip(), content_type, True
                    except UnicodeDecodeError:
                        continue
                
                # Fallback: decode with replacement
                text = payload.decode('utf-8', errors='replace')
                return text.strip(), content_type, True
        except Exception as e:
            return f"[Error extracting attachment: {e}]", content_type, False
    
    # Non-text attachments - just return metadata
    return f"[Binary attachment: {filename}, type: {content_type}]", content_type, False


def process_attachments(msg):
    """
    Process all attachments in an email message.
    
    Returns list of attachment documents with extracted content.
    """
    attachments = []
    
    if not msg.is_multipart():
        return attachments
    
    for part in msg.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        
        if "attachment" not in content_disposition:
            continue
        
        filename = part.get_filename() or "unknown_attachment"
        content_type = part.get_content_type()
        
        # Try to extract text content
        content, detected_type, success = extract_attachment_text(part)
        
        # Get file size if possible
        payload = part.get_payload(decode=True)
        size = len(payload) if payload else 0
        
        attachment_doc = {
            "filename": filename,
            "content_type": content_type,
            "size": size,
            "text_extracted": success,
            "content": content if success else None,
        }
        
        attachments.append(attachment_doc)
    
    return attachments


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


def create_rag_documents(msg, filepath):
    """
    Create RAG documents from an email message with chunking and attachment handling.
    
    Returns a list of documents:
    - One or more documents for chunked email body
    - Additional documents for text-extractable attachments
    
    Each chunk includes full metadata for independent retrieval.
    """
    author_name, author_email = extract_author(msg)
    date_str = msg.get('Date', '')
    subject = msg.get('Subject', '')
    body, content_type, was_html = extract_text_body(msg)
    message_id = msg.get('Message-ID', filepath.stem)
    
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
    
    # Create base ID from message-id or filename
    clean_id = re.sub(r'[<>@\s]', '_', message_id)
    base_doc_id = f"email_{clean_id}"
    
    # Common metadata for all chunks. Use canonical fields: `author` as email,
    # and keep a human-readable `author_name`.
    common_metadata = {
        "author": author_email,
        "author_name": author_name,
        "subject": subject,
        "date": iso_date,
        "to": to_addresses,
        "cc": cc_addresses,
        "in_reply_to": in_reply_to,
        "content_type": content_type,
        "converted_from_html": was_html,
        "source_file": filepath.name,
        "message_id": message_id,
    }
    
    documents = []
    
    # Chunk the email body. Use canonical `type` = "message" and `text` field.
    if body:
        chunks = chunk_text(body)

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{base_doc_id}_body_{idx}" if len(chunks) > 1 else f"{base_doc_id}_body"

            doc = {
                "id": chunk_id,
                "type": "message",
                "text": chunk,
                "metadata": {
                    **common_metadata,
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                    "is_chunked": len(chunks) > 1,
                    "is_attachment": False,
                }
            }
            documents.append(doc)
    
    # Process attachments
    attachments = process_attachments(msg)
    
    for att_idx, attachment in enumerate(attachments):
        # Only create documents for successfully extracted text attachments
        if attachment.get("text_extracted") and attachment.get("content"):
            att_content = attachment["content"]

            # Chunk large attachments
            att_chunks = chunk_text(att_content)

            for chunk_idx, chunk in enumerate(att_chunks):
                att_doc_id = f"{base_doc_id}_att_{att_idx}_{chunk_idx}" if len(att_chunks) > 1 else f"{base_doc_id}_att_{att_idx}"

                doc = {
                    "id": att_doc_id,
                    "type": "message",
                    "text": chunk,
                    "metadata": {
                        **common_metadata,
                        "is_attachment": True,
                        "attachment_filename": attachment["filename"],
                        "attachment_content_type": attachment["content_type"],
                        "attachment_size": attachment["size"],
                        "chunk_index": chunk_idx,
                        "total_chunks": len(att_chunks),
                        "is_chunked": len(att_chunks) > 1,
                    }
                }
                documents.append(doc)
        else:
            # For non-text attachments, create a metadata-only document with a short text description
            att_doc_id = f"{base_doc_id}_att_{att_idx}_meta"
            summary_text = f"Attachment: {attachment['filename']} (type: {attachment['content_type']}, size: {attachment['size']} bytes)"
            doc = {
                "id": att_doc_id,
                "type": "message",
                "text": summary_text,
                "metadata": {
                    **common_metadata,
                    "is_attachment": True,
                    "attachment_filename": attachment['filename'],
                    "attachment_content_type": attachment['content_type'],
                    "attachment_size": attachment['size'],
                    "text_extractable": False,
                }
            }
            documents.append(doc)
    
    # Add summary metadata to first document
    if documents:
        documents[0]["metadata"]["has_attachments"] = len(attachments) > 0
        documents[0]["metadata"]["attachment_count"] = len(attachments)
        documents[0]["metadata"]["total_documents"] = len(documents)
    
    return documents


def main():
    lispusers_dir = Path("lispUsers")
    
    if not lispusers_dir.exists():
        print(f"Error: {lispusers_dir} directory not found")
        return
    
    eml_files = list(lispusers_dir.glob("*.eml"))
    print(f"Found {len(eml_files)} .eml files in {lispusers_dir}")
    
    all_docs = []
    skipped_non_2025 = 0
    skipped_github = 0
    processed_emails = 0
    total_docs = 0
    total_chunks = 0
    total_attachments = 0
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
        
        # Create RAG documents (returns list of docs including chunks and attachments)
        docs = create_rag_documents(msg, filepath)
        all_docs.extend(docs)
        
        processed_emails += 1
        total_docs += len(docs)
        
        # Count chunks and attachments using canonical `type: "message"`
        for doc in docs:
            if doc.get("type") == "message":
                # attachments are flagged in metadata
                if doc.get("metadata", {}).get("is_attachment", False):
                    total_attachments += 1
                else:
                    total_chunks += 1
    
    # Write output
    output_file = Path("rag_emails.json")
    with open(output_file, 'w') as f:
        json.dump(all_docs, f, indent=2)
    
    # Print summary
    print(f"\nProcessing Summary:")
    print(f"  Total email files: {len(eml_files)}")
    print(f"  Processed emails: {processed_emails}")
    print(f"  Total RAG documents: {total_docs}")
    print(f"  Body chunks: {total_chunks}")
    print(f"  Attachment documents: {total_attachments}")
    print(f"  Skipped (not 2025): {skipped_non_2025}")
    print(f"  Skipped (GitHub notifications): {skipped_github}")
    print(f"  Errors: {errors}")
    print(f"\nOutput written to: {output_file}")
    
    # Print author summary
    if all_docs:
        authors = {}
        for doc in all_docs:
            # Count only primary email bodies (first chunk of a non-attachment message)
            if doc.get("type") == "message" and not doc.get("metadata", {}).get("is_attachment", False):
                if doc.get("metadata", {}).get("chunk_index", 0) == 0:
                    author = doc["metadata"].get("author")
                    authors[author] = authors.get(author, 0) + 1

        print(f"\nTop authors:")
        for author, count in sorted(authors.items(), key=lambda x: -x[1])[:10]:
            print(f"  {author}: {count}")

    # Print chunking statistics
    # Count unique emails that required chunking by looking at first (chunk_index == 0) non-attachment docs
    chunked_emails = sum(1 for doc in all_docs
                        if doc.get("type") == "message"
                        and not doc.get("metadata", {}).get("is_attachment", False)
                        and doc.get("metadata", {}).get("chunk_index", 0) == 0
                        and doc.get("metadata", {}).get("is_chunked", False))

    print(f"\nChunking Statistics:")
    print(f"  Emails requiring chunking: {chunked_emails}")
    if processed_emails:
        print(f"  Average documents per email: {total_docs / processed_emails:.2f}")
    else:
        print(f"  Average documents per email: N/A (no processed emails)")


if __name__ == "__main__":
    main()
