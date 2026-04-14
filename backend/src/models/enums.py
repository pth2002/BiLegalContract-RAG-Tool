"""Enum types for the contract review tool."""

from enum import Enum

 
class FileType(str, Enum):
    """Supported document file types."""

    PDF = "pdf"
    DOCX = "docx"


class Severity(str, Enum):
    """Risk severity levels."""

    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"


class RiskCategory(str, Enum):
    """Categories of contract risks."""

    ECONOMIC_BENEFIT = "经济利益"
    DELIVERY_RISK = "交付风险"
    OPERATIONAL_TRAP = "操作陷阱"


class PerspectiveType(str, Enum):
    """Analysis perspective types."""

    PARTY_A = "party_a"
    PARTY_B = "party_b"


class ExportFormat(str, Enum):
    """Export file formats."""

    DOCX = "docx"
    MARKDOWN = "markdown"
