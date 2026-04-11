"""Services package: lazy exports to avoid loading heavy deps on submodule import."""

from __future__ import annotations

import importlib
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "get_perspective_prompt": ("prompt_service", "get_perspective_prompt"),
    "get_perspective_info": ("prompt_service", "get_perspective_info"),
    "PerspectiveType": ("prompt_service", "PerspectiveType"),
    "parse_document": ("parser_service", "parse_document"),
    "parse_document_result": ("parser_service", "parse_document_result"),
    "parse_pdf": ("parser_service", "parse_pdf"),
    "parse_pdf_result": ("parser_service", "parse_pdf_result"),
    "parse_docx": ("parser_service", "parse_docx"),
    "parse_docx_result": ("parser_service", "parse_docx_result"),
    "validate_file_type": ("parser_service", "validate_file_type"),
    "validate_file_size": ("parser_service", "validate_file_size"),
    "DocumentParseError": ("parser_service", "DocumentParseError"),
    "FileValidationError": ("parser_service", "FileValidationError"),
    "stream_analysis": ("ollama_service", "stream_analysis"),
    "generate_suggestion_refinement": ("ollama_service", "generate_suggestion_refinement"),
    "check_ollama_connection": ("ollama_service", "check_ollama_connection"),
    "get_ollama_client": ("ollama_service", "get_ollama_client"),
    "get_default_prompt": ("ollama_service", "get_default_prompt"),
    "OllamaError": ("ollama_service", "OllamaError"),
    "OllamaNotRunningError": ("ollama_service", "OllamaNotRunningError"),
    "analyze_document": ("analyzer_service", "analyze_document"),
    "parse_risk_json": ("analyzer_service", "parse_risk_json"),
    "create_risk_card": ("analyzer_service", "create_risk_card"),
    "AnalysisError": ("analyzer_service", "AnalysisError"),
    "event_generator": ("stream_service", "event_generator"),
    "format_sse_event": ("stream_service", "format_sse_event"),
    "StreamServiceError": ("stream_service", "StreamServiceError"),
    "generate_markdown_report": ("export_service", "generate_markdown_report"),
    "generate_markdown_download": ("export_service", "generate_markdown_download"),
    "generate_docx_report": ("export_service", "generate_docx_report"),
    "ExportError": ("export_service", "ExportError"),
}


def __getattr__(name: str) -> Any:
    if name == "StreamOllamaNotRunningError":
        from .stream_service import OllamaNotRunningError as StreamOllamaNotRunningError

        return StreamOllamaNotRunningError
    if name in _EXPORTS:
        mod_name, attr = _EXPORTS[name]
        mod = importlib.import_module(f".{mod_name}", package=__name__)
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "get_perspective_prompt",
    "get_perspective_info",
    "PerspectiveType",
    "parse_document",
    "parse_document_result",
    "parse_pdf",
    "parse_pdf_result",
    "parse_docx",
    "parse_docx_result",
    "validate_file_type",
    "validate_file_size",
    "DocumentParseError",
    "FileValidationError",
    "stream_analysis",
    "generate_suggestion_refinement",
    "check_ollama_connection",
    "get_ollama_client",
    "get_default_prompt",
    "OllamaError",
    "OllamaNotRunningError",
    "analyze_document",
    "parse_risk_json",
    "create_risk_card",
    "AnalysisError",
    "event_generator",
    "format_sse_event",
    "StreamServiceError",
    "StreamOllamaNotRunningError",
    "generate_markdown_report",
    "generate_markdown_download",
    "generate_docx_report",
    "ExportError",
]
