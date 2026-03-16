# Email Processing Improvements for RAG

## Overview
Enhanced `processEmails.py` to optimize email processing for RAG (Retrieval-Augmented Generation) applications.

## Key Improvements

### 1. Text Chunking
- **Implementation**: Added `chunk_text()` function that intelligently splits long emails
- **Strategy**: Breaks at paragraph boundaries to preserve semantic units
- **Configuration**:
  - Target: 800 tokens per chunk (~3200 characters)
  - Overlap: 100 tokens (~400 characters) between chunks
- **Benefits**: Optimizes for embedding model input sizes while maintaining context

### 2. Plain Text Preference
- **Old Behavior**: Preferred HTML over plain text
- **New Behavior**: Prefers plain text over HTML for cleaner semantic content
- **HTML Handling**: When only HTML is available, converts to clean Markdown using `html2text`
- **Benefits**: 
  - Better embedding quality (no HTML tag noise)
  - Smaller token count
  - Preserved structure through Markdown

### 3. Attachment Processing
- **Text Extraction**: Automatically extracts text from common attachment types:
  - Plain text files (.txt, .log, .md)
  - Code files (.py, .js, .lisp, .c, .java, etc.)
  - Data files (.json, .xml, .csv)
- **Chunking**: Large attachments are chunked like email bodies
- **Binary Files**: Creates metadata-only documents for non-text attachments
- **Multi-encoding Support**: Tries UTF-8, Latin-1, and CP1252 encodings

### 4. Document Structure
Each email now produces multiple RAG documents:
```json
{
  "id": "email_{msg_id}_body_0",
  "type": "email_body",
  "content": "Chunked email content...",
  "metadata": {
    "author": "...",
    "subject": "...",
    "date": "...",
    "chunk_index": 0,
    "total_chunks": 3,
    "is_chunked": true,
    "has_attachments": true,
    "converted_from_html": false
  }
}
```

Attachment documents:
```json
{
  "id": "email_{msg_id}_att_0",
  "type": "email_attachment",
  "content": "Extracted attachment text...",
  "metadata": {
    "attachment_filename": "error.log",
    "attachment_content_type": "text/plain",
    "attachment_size": 2048,
    ...
  }
}
```

### 5. Enhanced Metadata
Each chunk includes:
- Full email metadata (author, subject, date, recipients)
- Chunk position information
- Attachment details
- HTML conversion flag
- Source file reference

### 6. Improved Statistics
New output includes:
- Total RAG documents created
- Body chunks count
- Attachment documents count
- Chunking statistics
- Average documents per email

## Dependencies Added
- `html2text>=2024.2.26` - For HTML to Markdown conversion

## Usage
```bash
python processEmails.py
```

Output: `rag_emails.json` with optimized RAG documents

## Benefits for RAG Applications
1. **Better Retrieval**: Smaller, focused chunks improve relevance matching
2. **Richer Context**: Each chunk is independently searchable with full metadata
3. **Attachment Support**: Code snippets and text attachments are now searchable
4. **Cleaner Text**: Markdown conversion preserves structure without HTML noise
5. **Scalability**: Chunking prevents token limits in embedding models
