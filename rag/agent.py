# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from typing import Optional

from google.adk.agents import Agent
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from vertexai.preview import rag
from .search import LocalKeywordRetrieval

from dotenv import load_dotenv
from .prompts import return_instructions_root

def _load_template_from_env() -> Optional[str]:
    """Load report template from environment variables.

    Supports either `REPORT_TEMPLATE_TEXT` for inline text, or
    `REPORT_TEMPLATE_FILE` pointing to a .txt or .docx file.
    """
    inline = os.environ.get("REPORT_TEMPLATE_TEXT")
    if inline:
        return inline

    path = os.environ.get("REPORT_TEMPLATE_FILE")
    if not path:
        return None

    if not os.path.exists(path):
        raise FileNotFoundError(f"REPORT_TEMPLATE_FILE not found: {path}")

    # .docx template support using python-docx if available; fallback to txt
    _, ext = os.path.splitext(path)
    ext = ext.lower()
    if ext == ".docx":
        try:
            from docx import Document  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "Reading .docx requires python-docx. Please install it in your venv: 'pip install python-docx'"
            ) from e
        doc = Document(path)
        # Concatenate paragraphs preserving blank lines
        paragraphs = [p.text for p in doc.paragraphs]
        return "\n".join(paragraphs).strip()

    # Treat as plain text for other extensions (e.g., .txt, .md)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

load_dotenv()

# Build tools list conditionally based on RAG_CORPUS availability
tools = []
rag_corpus = os.environ.get("RAG_CORPUS")

# Optional local keyword/hybrid retrieval using a built sqlite FTS index.
use_keyword = os.environ.get("USE_KEYWORD_RETRIEVAL")
rag_index_path = os.environ.get("RAG_INDEX_PATH", "rag/rag_index.db")

if rag_corpus:
    ask_vertex_retrieval = VertexAiRagRetrieval(
        name='retrieve_rag_documentation',
        description=(
            'Use this tool to retrieve documentation and reference materials for the question from the RAG corpus,'
        ),
        rag_resources=[
            rag.RagResource(
                # please fill in your own rag corpus
                # here is a sample rag corpus for testing purpose
                # e.g. projects/123/locations/us-central1/ragCorpora/456
                rag_corpus=rag_corpus
            )
        ],
        similarity_top_k=10,
        vector_distance_threshold=0.6,
    )
    tools.append(ask_vertex_retrieval)


template_text = _load_template_from_env()

# Register local keyword/hybrid retrieval if requested (independent of RAG_CORPUS)
if use_keyword:
    # Parse HYBRID_WEIGHTS for agent creation; fallback handled inside search module
    raw_weights = os.environ.get("HYBRID_WEIGHTS")
    weights = None
    if raw_weights:
        try:
            parts = [float(p.strip()) for p in raw_weights.split(',') if p.strip()]
            if len(parts) == 1:
                v = parts[0]
                weights = (v, max(0.0, 1.0 - v))
            elif len(parts) >= 2:
                v, k = parts[0], parts[1]
                s = v + k or 1.0
                weights = (v / s, k / s)
        except Exception:
            weights = None

    local_kw = LocalKeywordRetrieval(
        name='local_keyword_retrieval',
        description='Local hybrid keyword+vector retrieval (hybrid) using local index',
        db_path=rag_index_path,
    )
    # Attach optional weights attribute for runtime use
    if weights:
        setattr(local_kw, 'weights', weights)
    tools.append(local_kw)

root_agent = Agent(
    model='gemini-2.5-flash',
    name='ask_rag_agent',
    instruction=return_instructions_root(template_text=template_text),
    tools=tools,
)
