"""
Document ingestion: walks a directory of runbooks/playbooks (Markdown and PDF),
extracts plain text, and splits it into overlapping chunks ready for embedding.

Design notes
------------
- Markdown is read as-is (already plain text with light formatting).
- PDF text extraction uses pypdf, which is dependency-light and pure Python.
  For scanned/image PDFs you would add OCR (see pdf-reading skill patterns) —
  flagged as a known limitation in docs/ARCHITECTURE.md.
- Chunking is word-count based with overlap, which keeps context coherent
  across chunk boundaries without needing a tokenizer at ingestion time.
"""
import os
import re
import hashlib
from dataclasses import dataclass, field
from typing import List

from config import DOCS_DIR, CHUNK_SIZE_WORDS, CHUNK_OVERLAP_WORDS

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None


@dataclass
class Chunk:
    chunk_id: str
    source_path: str
    source_title: str
    section: str
    text: str


def _extract_markdown(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _extract_pdf(path: str) -> str:
    if PdfReader is None:
        raise RuntimeError("pypdf is required to ingest PDF runbooks (pip install pypdf)")
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _split_into_sections(text: str):
    """
    Split a markdown document on '## ' headings so each chunk can carry a
    meaningful section label for citation purposes. Falls back to a single
    'Document' section for non-markdown or unstructured text.
    """
    parts = re.split(r"(?m)^#{1,6}\s+(.*)$", text)
    if len(parts) <= 1:
        return [("Document", text)]

    sections = []
    # parts alternates: [preamble, heading1, body1, heading2, body2, ...]
    preamble = parts[0].strip()
    if preamble:
        sections.append(("Introduction", preamble))
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections.append((heading, body.strip()))
    return sections


def _chunk_words(text: str, size: int, overlap: int) -> List[str]:
    words = text.split()
    if not words:
        return []
    chunks = []
    step = max(size - overlap, 1)
    for start in range(0, len(words), step):
        piece = words[start:start + size]
        if not piece:
            break
        chunks.append(" ".join(piece))
        if start + size >= len(words):
            break
    return chunks


def load_and_chunk_documents(docs_dir: str = DOCS_DIR) -> List[Chunk]:
    """
    Walk docs_dir, extract text from each supported file, split into
    sections and then word-count chunks. Returns a flat list of Chunk.
    """
    all_chunks: List[Chunk] = []
    if not os.path.isdir(docs_dir):
        return all_chunks

    for root, _, files in os.walk(docs_dir):
        for fname in sorted(files):
            path = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()
            try:
                if ext in (".md", ".markdown", ".txt"):
                    text = _extract_markdown(path)
                elif ext == ".pdf":
                    text = _extract_pdf(path)
                else:
                    continue
            except Exception as e:  # noqa: BLE001 - log & skip bad files, don't crash ingestion
                print(f"[ingestion] Failed to read {path}: {e}")
                continue

            title = os.path.splitext(fname)[0].replace("-", " ").replace("_", " ").title()
            for section, body in _split_into_sections(text):
                for idx, chunk_text in enumerate(_chunk_words(body, CHUNK_SIZE_WORDS, CHUNK_OVERLAP_WORDS)):
                    raw_id = f"{path}:{section}:{idx}"
                    chunk_id = hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:12]
                    all_chunks.append(Chunk(
                        chunk_id=chunk_id,
                        source_path=path,
                        source_title=title,
                        section=section,
                        text=chunk_text,
                    ))
    return all_chunks


if __name__ == "__main__":
    chunks = load_and_chunk_documents()
    print(f"Loaded {len(chunks)} chunks from {DOCS_DIR}")
    for c in chunks[:3]:
        print(f"- [{c.source_title} / {c.section}] {c.text[:80]}...")
