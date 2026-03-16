# Quick Start Guide

## Installation

1. Install the new dependency:
```bash
pip install html2text
```

Or update your environment from pyproject.toml:
```bash
pip install -e .
```

## Usage

Run the improved email processor:
```bash
python processEmails.py
```

## What's Different?

### Before
- One document per email
- HTML preferred over plain text
- No attachment processing
- Long emails caused embedding issues

### After
- Multiple documents per email (chunked bodies + attachments)
- Plain text preferred, HTML converted to Markdown
- Text attachments automatically extracted
- Optimal chunk sizes for embedding models

## Output Structure

Each email produces 1+ RAG documents in `rag_emails.json`:

```json
[
  {
    "id": "email_{msg_id}_body_0",
    "type": "email_body",
    "content": "First chunk of email...",
    "metadata": {
      "author": "...",
      "subject": "...",
      "chunk_index": 0,
      "total_chunks": 2,
      ...
    }
  },
  {
    "id": "email_{msg_id}_body_1",
    "type": "email_body",
    "content": "Second chunk with overlap...",
    "metadata": {...}
  },
  {
    "id": "email_{msg_id}_att_0",
    "type": "email_attachment",
    "content": "Extracted attachment text...",
    "metadata": {
      "attachment_filename": "code.py",
      ...
    }
  }
]
```

## Configuration

Adjust chunking parameters in `processEmails.py`:

```python
CHUNK_SIZE = 800  # Target tokens per chunk
CHUNK_OVERLAP = 100  # Overlap between chunks
```

Typical values:
- Small chunks (512 tokens): Better precision, more documents
- Medium chunks (800 tokens): Balanced (default)
- Large chunks (1000 tokens): More context, fewer documents

## Supported Attachment Types

Automatically extracts text from:
- `.txt`, `.log`, `.md` (text files)
- `.py`, `.js`, `.lisp`, `.java`, `.c`, `.cpp` (code)
- `.json`, `.xml`, `.csv` (data files)

Binary files get metadata-only documents.

## View Examples

```bash
python rag_structure_example.py
```

Shows example output structure for different email types.
