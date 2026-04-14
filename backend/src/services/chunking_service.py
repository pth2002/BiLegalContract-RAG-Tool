"""Chunking service.

Default behavior is still sliding-window chunking, but when structure-aware
document blocks are available we now chunk section-like merged content rather
than treating the whole document as one flat string.
"""

from __future__ import annotations 

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..config import get_chunk_overlap_chars, get_chunk_size_chars

if TYPE_CHECKING:
    from ..models import Document, DocumentBlock

# ---------------------------------------------------------------------------
# Chinese clause boundary patterns
# ---------------------------------------------------------------------------

_ZH_CLAUSE_RE = re.compile(
    r"第[一二三四五六七八九十百千零0-9]+(?:条|章|节)"
    r"|（[一二三四五六七八九十]+）"
    r"|(?<!\d)\d+\.\d+(?=[\s　])"
)


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    content: str
    start: int
    end: int


def _validate_chunk_params() -> tuple[int, int]:
    size = get_chunk_size_chars()
    overlap = get_chunk_overlap_chars()

    if size <= 0:
        raise ValueError("CHUNK_SIZE_CHARS must be > 0")
    if overlap < 0:
        raise ValueError("CHUNK_OVERLAP_CHARS must be >= 0")
    if overlap >= size:
        raise ValueError("CHUNK_OVERLAP_CHARS must be < CHUNK_SIZE_CHARS")
    return size, overlap


def _chunk_content(text: str, *, size: int, overlap: int, start_offset: int, start_index: int) -> list[TextChunk]:
    t = (text or "").strip()
    if not t:
        return []

    chunks: list[TextChunk] = []
    start = 0
    i = start_index

    while start < len(t):
        end = min(len(t), start + size)
        content = t[start:end].strip()
        if content:
            chunks.append(
                TextChunk(
                    chunk_id=f"chunk_{i:04d}",
                    content=content,
                    start=start_offset + start,
                    end=start_offset + end,
                )
            )
            i += 1
        if end >= len(t):
            break
        start = max(0, end - overlap)

    return chunks


def chunk_text(text: str) -> list[TextChunk]:
    size, overlap = _validate_chunk_params()
    return _chunk_content(text, size=size, overlap=overlap, start_offset=0, start_index=0)


# ---------------------------------------------------------------------------
# Language detection (local, avoids circular import with retrieval_service)
# ---------------------------------------------------------------------------

def _detect_doc_language(text: str) -> str:
    """Classify document language: 'zh', 'en', or 'mixed'.

    Uses the same thresholds as retrieval_service.detect_language but is
    defined here to avoid a circular import.
    """
    if not text:
        return "mixed"
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return "mixed"
    total = len(chars)
    cjk = sum(1 for c in chars if "\u4e00" <= c <= "\u9fff")
    if cjk / total >= 0.3:
        return "zh"
    latin = sum(1 for c in chars if c.isascii() and c.isalpha())
    if latin / total >= 0.7:
        return "en"
    return "mixed"


# ---------------------------------------------------------------------------
# Chinese-aware chunking
# ---------------------------------------------------------------------------

def _extract_zh_clause_title(text: str, pos: int) -> str:
    """Extract clause heading starting at *pos* (up to first newline, max 25 chars)."""
    snippet = text[pos: min(len(text), pos + 25)]
    nl = snippet.find("\n")
    if nl > 0:
        snippet = snippet[:nl]
    return snippet.strip()


def chunk_chinese_document(
    document: "Document",
    chunk_size: int = 500,
    overlap: int = 100,
) -> list[TextChunk]:
    """Chinese-aware chunking with clause boundary detection and title prefix injection.

    Algorithm
    ---------
    1. Locate clause boundaries (第N条/章/节, （N）, N.N).
    2. Merge sections shorter than *chunk_size* × 0.3 into their neighbour.
    3. Sections ≤ chunk_size × 1.5 become a single chunk; longer sections are
       split with sliding window.
    4. Each chunk is prefixed with the nearest enclosing clause heading
       (prefix counts toward chunk_size).
    """
    text = (getattr(document, "text_content", None) or "").strip()
    if not text:
        return []

    min_section_len = max(1, int(chunk_size * 0.3))
    max_single_len = int(chunk_size * 1.5)

    # ── 1. Locate clause boundaries ──────────────────────────────────────────
    boundaries: list[tuple[int, str]] = [
        (m.start(), _extract_zh_clause_title(text, m.start()))
        for m in _ZH_CLAUSE_RE.finditer(text)
    ]

    if not boundaries:
        # No clause structure detected — fall back to sliding window
        return _chunk_content(
            text, size=chunk_size, overlap=overlap, start_offset=0, start_index=0
        )

    # Build raw sections: (start, end, title)
    raw_sections: list[tuple[int, int, str]] = []
    if boundaries[0][0] > 0:
        preamble = text[: boundaries[0][0]].strip()
        if preamble:
            raw_sections.append((0, boundaries[0][0], ""))
    for idx, (pos, title) in enumerate(boundaries):
        end = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else len(text)
        raw_sections.append((pos, end, title))

    # ── 2. Merge short adjacent sections ─────────────────────────────────────
    merged: list[tuple[str, str]] = []   # (title, content)
    buf_title = ""
    buf_content = ""

    for start, end, title in raw_sections:
        content = text[start:end].strip()
        if not content:
            continue
        if not buf_content:
            buf_title, buf_content = title, content
        elif len(buf_content) < min_section_len:
            if not buf_title:
                buf_title = title
            buf_content += "\n\n" + content
        else:
            merged.append((buf_title, buf_content))
            buf_title, buf_content = title, content

    if buf_content:
        merged.append((buf_title, buf_content))

    # ── 3 & 4. Build TextChunks with title prefix ─────────────────────────────
    chunks: list[TextChunk] = []
    index = 0

    for title, content in merged:
        prefix = f"[{title}] " if title else ""
        effective_size = max(100, chunk_size - len(prefix))

        full_content = (prefix + content).strip()
        if len(full_content) <= max_single_len:
            chunks.append(
                TextChunk(
                    chunk_id=f"chunk_{index:04d}",
                    content=full_content,
                    start=0,
                    end=len(full_content),
                )
            )
            index += 1
        else:
            sub_chunks = _chunk_content(
                content,
                size=effective_size,
                overlap=overlap,
                start_offset=0,
                start_index=index,
            )
            for j, sc in enumerate(sub_chunks):
                p = prefix if j == 0 else (f"[{title} 续] " if title else "")
                chunks.append(
                    TextChunk(
                        chunk_id=sc.chunk_id,
                        content=(p + sc.content).strip(),
                        start=sc.start,
                        end=sc.end,
                    )
                )
            index += len(sub_chunks)

    return chunks


def _is_low_value_block_type(block_type: str) -> bool:
    return block_type in {"header", "footer", "toc"}


def _build_structured_segments(blocks: list["DocumentBlock"], size: int) -> list[str]:
    ordered_blocks = sorted(blocks, key=lambda block: (block.page_number, block.block_id))
    segments: list[str] = []
    buffer: list[str] = []
    pending_title: str | None = None

    def flush_buffer() -> None:
        nonlocal buffer
        merged = "\n\n".join(part for part in buffer if part.strip()).strip()
        if merged:
            segments.append(merged)
        buffer = []

    for block in ordered_blocks:
        text = (block.text or "").strip()
        if not text or _is_low_value_block_type(block.block_type):
            continue

        if block.block_type == "title":
            flush_buffer()
            pending_title = text
            continue

        if block.block_type == "table":
            flush_buffer()
            table_segment = f"{pending_title}\n\n{text}".strip() if pending_title else text
            pending_title = None
            segments.append(table_segment)
            continue

        if pending_title:
            buffer.append(pending_title)
            pending_title = None

        current_len = sum(len(item) for item in buffer)
        if current_len >= max(size * 2, size + 200):
            flush_buffer()

        buffer.append(text)

    if pending_title:
        buffer.append(pending_title)
    flush_buffer()

    return segments


def chunk_document(document: "Document") -> list[TextChunk]:
    # Chinese and bilingual documents use the clause-aware chunker with fixed
    # 500:100 parameters that better suit dense-only retrieval on bge-large-zh.
    lang = _detect_doc_language(getattr(document, "text_content", "") or "")
    if lang in {"zh", "mixed"}:
        return chunk_chinese_document(document)

    size, overlap = _validate_chunk_params()

    if not getattr(document, "content_blocks", None):
        return chunk_text(document.text_content)

    segments = _build_structured_segments(document.content_blocks, size)
    if not segments:
        return chunk_text(document.text_content)

    chunks: list[TextChunk] = []
    index = 0
    offset = 0
    for segment in segments:
        segment_chunks = _chunk_content(
            segment,
            size=size,
            overlap=overlap,
            start_offset=offset,
            start_index=index,
        )
        chunks.extend(segment_chunks)
        index += len(segment_chunks)
        offset += len(segment) + 2

    return chunks
