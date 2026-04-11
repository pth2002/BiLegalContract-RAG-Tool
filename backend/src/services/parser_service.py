"""Document parsing service for PDF and DOCX files.

This module now follows a more structure-aware parsing approach inspired by
DeepDoc: instead of returning only a flat text string, it builds page-level and
block-level intermediate results, then derives a lightweight document profile
and parse summary from them.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Iterator, Tuple

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from docx.document import Document as DocxDocumentType
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from ..models import (
    DocumentBlock,
    DocumentPageSummary,
    DocumentParseSummary,
    DocumentProfile,
    FileType,
    ParsedDocumentResult,
)


class DocumentParseError(Exception):
    """Exception raised when document parsing fails."""

    def __init__(self, message: str, reason: str | None = None):
        self.message = message
        self.reason = reason
        super().__init__(self.message)


class FileValidationError(Exception):
    """Exception raised when file validation fails."""

    pass


def validate_file_type(filename: str) -> Tuple[FileType, str]:
    """Validate file extension and return FileType."""
    extension = Path(filename).suffix.lower()

    if extension == ".pdf":
        return FileType.PDF, ".pdf"
    if extension in (".docx", ".doc"):
        return FileType.DOCX, ".docx"
    raise FileValidationError(
        f"Invalid file type: {extension}. Only PDF and DOCX files are supported."
    )


def validate_file_size(file_type: FileType, file_size: int) -> None:
    """Validate file before parsing.

    The parser no longer blocks large files, but we still reject empty uploads.
    """
    if file_size <= 0:
        raise FileValidationError(f"{file_type.value.upper()} file is empty.")


def _clean_text(text: str) -> str:
    text = (text or "").replace("\x00", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _looks_like_toc(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if "table of contents" in t or t == "contents":
        return True
    if "目录" in t:
        return True
    if re.search(r"\.{4,}\s*\d+\s*$", t):
        return True
    return False


def _looks_like_table(text: str) -> bool:
    if not text:
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    pipe_lines = sum(1 for line in lines if "|" in line)
    spaced_columns = sum(1 for line in lines if re.search(r"\S+\s{2,}\S+", line))
    return pipe_lines >= 2 or spaced_columns >= 2


def _looks_like_title(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if len(t) > 120:
        return False
    if t.endswith((".", ",", ";", "。", "，", "；", ":", "：")):
        return False
    if re.match(r"^(\d+(\.\d+)*|第[一二三四五六七八九十百]+[章节条款部分])", t):
        return True
    upper_letters = sum(1 for ch in t if ch.isalpha() and ch.isupper())
    total_letters = sum(1 for ch in t if ch.isalpha())
    if total_letters >= 6 and upper_letters / max(total_letters, 1) > 0.8:
        return True
    return len(t.split()) <= 12 and len(t) <= 60


def _classify_pdf_block(
    text: str,
    y0: float,
    y1: float,
    page_height: float,
) -> str:
    if _looks_like_toc(text):
        return "toc"
    if _looks_like_table(text):
        return "table"

    short = len(text) <= 80
    top_band = y0 <= page_height * 0.09
    bottom_band = y1 >= page_height * 0.91
    if short and top_band:
        return "header"
    if short and bottom_band:
        return "footer"
    if _looks_like_title(text):
        return "title"
    return "text"


def _guess_language(text: str) -> str:
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text or ""))
    latin = len(re.findall(r"[A-Za-z]", text or ""))
    if cjk and not latin:
        return "zh"
    if latin and not cjk:
        return "en"
    if cjk and latin:
        return "mixed"
    return "unknown"


def _classify_length(char_count: int) -> str:
    if char_count < 5000:
        return "short"
    if char_count < 30000:
        return "medium"
    return "long"


def _classify_layout_complexity(
    *,
    page_count: int,
    block_count: int,
    table_count: int,
    toc_count: int,
) -> str:
    avg_blocks = block_count / max(page_count, 1)
    if table_count > 0 or toc_count > 0 or avg_blocks >= 18:
        return "high"
    if avg_blocks >= 8:
        return "medium"
    return "low"


def _compute_parse_quality(
    *,
    full_text: str,
    page_summaries: list[DocumentPageSummary],
    warnings: list[str],
) -> float:
    if not full_text.strip():
        return 0.0

    blank_pages = sum(1 for page in page_summaries if page.is_mostly_empty)
    blank_ratio = blank_pages / max(len(page_summaries), 1)
    score = 1.0
    score -= min(blank_ratio * 0.35, 0.35)
    if len(full_text) < 200:
        score -= 0.25
    if warnings:
        score -= min(0.1 * len(warnings), 0.3)
    return max(0.05, min(score, 1.0))


def _build_profile(
    *,
    text: str,
    page_count: int,
    blocks: list[DocumentBlock],
) -> DocumentProfile:
    table_count = sum(1 for block in blocks if block.block_type == "table")
    toc_count = sum(1 for block in blocks if block.block_type == "toc")
    return DocumentProfile(
        language=_guess_language(text),
        length_class=_classify_length(len(text)),
        layout_complexity=_classify_layout_complexity(
            page_count=page_count,
            block_count=len(blocks),
            table_count=table_count,
            toc_count=toc_count,
        ),
    )


def _build_parse_summary(
    *,
    source_type: str,
    text: str,
    page_summaries: list[DocumentPageSummary],
    flags: list[str],
    warnings: list[str],
) -> DocumentParseSummary:
    return DocumentParseSummary(
        source_type=source_type,
        char_count=len(text),
        parse_quality_score=_compute_parse_quality(
            full_text=text,
            page_summaries=page_summaries,
            warnings=warnings,
        ),
        warnings=warnings,
        flags=flags,
    )


def _iter_docx_blocks(document: DocxDocumentType) -> Iterator[Paragraph | Table]:
    """Yield paragraphs and tables in document order."""
    body = document._body
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, body)
        elif isinstance(child, CT_Tbl):
            yield Table(child, body)


def parse_pdf_result(file_content: bytes) -> ParsedDocumentResult:
    """Parse PDF and return a structure-aware result."""
    try:
        pdf_document = fitz.open(stream=file_content, filetype="pdf")
        total_pages = len(pdf_document)

        page_summaries: list[DocumentPageSummary] = []
        blocks: list[DocumentBlock] = []
        full_text_parts: list[str] = []
        warnings: list[str] = []
        flags: list[str] = []

        for page_number, page in enumerate(pdf_document, start=1):
            raw_blocks = page.get_text("blocks")
            page_blocks: list[DocumentBlock] = []
            page_text_parts: list[str] = []

            for local_idx, raw_block in enumerate(raw_blocks):
                x0, y0, x1, y1, text, *_ = raw_block
                cleaned = _clean_text(text)
                if not cleaned:
                    continue

                block_type = _classify_pdf_block(cleaned, float(y0), float(y1), float(page.rect.height))
                block = DocumentBlock(
                    block_id=f"p{page_number:04d}_b{local_idx:04d}",
                    page_number=page_number,
                    block_type=block_type,
                    text=cleaned,
                    char_count=len(cleaned),
                    source="pdf_text_block",
                    bbox=(float(x0), float(y0), float(x1), float(y1)),
                )
                page_blocks.append(block)
                blocks.append(block)

                if block_type not in {"header", "footer"}:
                    page_text_parts.append(cleaned)

            page_text = "\n\n".join(page_text_parts).strip()
            char_count = len(page_text)
            suspected_toc = any(block.block_type == "toc" for block in page_blocks)
            suspected_header_footer_noise = any(
                block.block_type in {"header", "footer"} for block in page_blocks
            )
            is_mostly_empty = char_count < 50

            page_summaries.append(
                DocumentPageSummary(
                    page_number=page_number,
                    char_count=char_count,
                    block_count=len(page_blocks),
                    is_mostly_empty=is_mostly_empty,
                    suspected_toc=suspected_toc,
                    suspected_header_footer_noise=suspected_header_footer_noise,
                )
            )
            if page_text:
                full_text_parts.append(page_text)

        pdf_document.close()

        if any(page.suspected_toc for page in page_summaries):
            flags.append("has_possible_toc")
        if any(page.suspected_header_footer_noise for page in page_summaries):
            flags.append("has_header_footer_noise")
        if any(page.is_mostly_empty for page in page_summaries):
            warnings.append("some_pages_have_little_or_no_extractable_text")

        full_text = "\n\n".join(part for part in full_text_parts if part.strip())
        profile = _build_profile(text=full_text, page_count=total_pages, blocks=blocks)
        summary = _build_parse_summary(
            source_type="pdf_text",
            text=full_text,
            page_summaries=page_summaries,
            flags=flags,
            warnings=warnings,
        )

        return ParsedDocumentResult(
            text_content=full_text,
            count=total_pages,
            file_type=FileType.PDF,
            page_summaries=page_summaries,
            content_blocks=blocks,
            parse_summary=summary,
            document_profile=profile,
        )
    except Exception as e:
        raise DocumentParseError(
            "Failed to parse PDF document",
            reason=str(e),
        ) from e


def parse_docx_result(file_content: bytes) -> ParsedDocumentResult:
    """Parse DOCX and return a structure-aware result."""
    try:
        docx_file = io.BytesIO(file_content)
        docx_document = DocxDocument(docx_file)

        blocks: list[DocumentBlock] = []
        page_text_parts: list[str] = []
        block_index = 0

        for item in _iter_docx_blocks(docx_document):
            if isinstance(item, Paragraph):
                cleaned = _clean_text(item.text)
                if not cleaned:
                    continue
                style_name = (item.style.name or "").lower() if item.style is not None else ""
                if "heading" in style_name or "title" in style_name:
                    block_type = "title"
                elif _looks_like_toc(cleaned):
                    block_type = "toc"
                elif _looks_like_title(cleaned):
                    block_type = "title"
                else:
                    block_type = "text"

                blocks.append(
                    DocumentBlock(
                        block_id=f"p0001_b{block_index:04d}",
                        page_number=1,
                        block_type=block_type,
                        text=cleaned,
                        char_count=len(cleaned),
                        source="docx_paragraph",
                    )
                )
                block_index += 1
                page_text_parts.append(cleaned)
            else:
                row_texts: list[str] = []
                for row in item.rows:
                    cells = [_clean_text(cell.text) for cell in row.cells]
                    cells = [cell for cell in cells if cell]
                    if cells:
                        row_texts.append(" | ".join(cells))
                cleaned = _clean_text("\n".join(row_texts))
                if not cleaned:
                    continue
                blocks.append(
                    DocumentBlock(
                        block_id=f"p0001_b{block_index:04d}",
                        page_number=1,
                        block_type="table",
                        text=cleaned,
                        char_count=len(cleaned),
                        source="docx_table",
                    )
                )
                block_index += 1
                page_text_parts.append(cleaned)

        full_text = "\n\n".join(page_text_parts).strip()
        page_summaries = [
            DocumentPageSummary(
                page_number=1,
                char_count=len(full_text),
                block_count=len(blocks),
                is_mostly_empty=len(full_text) < 50,
                suspected_toc=any(block.block_type == "toc" for block in blocks),
                suspected_header_footer_noise=False,
            )
        ]
        flags: list[str] = []
        warnings: list[str] = []
        if any(block.block_type == "table" for block in blocks):
            flags.append("has_tables")
        if any(block.block_type == "toc" for block in blocks):
            flags.append("has_possible_toc")
        if len(full_text) < 50:
            warnings.append("docx_contains_little_extractable_text")

        profile = _build_profile(text=full_text, page_count=1, blocks=blocks)
        summary = _build_parse_summary(
            source_type="docx_text",
            text=full_text,
            page_summaries=page_summaries,
            flags=flags,
            warnings=warnings,
        )

        return ParsedDocumentResult(
            text_content=full_text,
            count=max(1, len(blocks)),
            file_type=FileType.DOCX,
            page_summaries=page_summaries,
            content_blocks=blocks,
            parse_summary=summary,
            document_profile=profile,
        )
    except Exception as e:
        raise DocumentParseError(
            "Failed to parse DOCX document",
            reason=str(e),
        ) from e


def parse_pdf(file_content: bytes) -> Tuple[str, int]:
    """Legacy PDF parser wrapper kept for compatibility."""
    result = parse_pdf_result(file_content)
    return result.text_content, result.count


def parse_docx(file_content: bytes) -> Tuple[str, int]:
    """Legacy DOCX parser wrapper kept for compatibility."""
    result = parse_docx_result(file_content)
    return result.text_content, result.count


def parse_document_result(
    file_content: bytes,
    filename: str,
) -> ParsedDocumentResult:
    """Parse a document and return structure-aware output."""
    file_type, _ = validate_file_type(filename)
    validate_file_size(file_type, len(file_content))

    if file_type == FileType.PDF:
        return parse_pdf_result(file_content)
    return parse_docx_result(file_content)


def parse_document(
    file_content: bytes,
    filename: str,
) -> Tuple[str, int, FileType]:
    """Legacy parser wrapper kept for compatibility with existing call sites."""
    result = parse_document_result(file_content, filename)
    return result.text_content, result.count, result.file_type
