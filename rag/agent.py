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

root_agent = Agent(
    model='gemini-2.5-flash',
    name='ask_rag_agent',
    instruction=return_instructions_root(template_text=template_text),
    tools=tools,
)
