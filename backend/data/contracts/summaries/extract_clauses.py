"""
从 backend/data/contracts/ 下的每个 PDF 提取关键条款章节。
对每个匹配的章节输出：标题 + 正文前 800 字符。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NamedTuple

import fitz  # PyMuPDF

CONTRACTS_DIR = Path(__file__).parent.parent
SUMMARIES_DIR = Path(__file__).parent
BODY_CHARS = 800

# ──────────────────────────────────────────────
# 1. 标题检测正则（行级）
# ──────────────────────────────────────────────
_HEADING_PATTERNS: list[re.Pattern] = [
    # 第X章 / 第X条 / 第X节 / 第X款
    re.compile(r"^第\s*[一二三四五六七八九十百\d]+\s*[章节条款项]"),
    # 一、前言  二、释义  十一、基金费用  （含多字数字如"十七"）
    re.compile(r"^[一二三四五六七八九十][十一二三四五六七八九]*[、．.]\s*[\u4e00-\u9fff]"),
    # Article N  /  ARTICLE IV
    re.compile(r"^Article\s+[\dIVXLC]+", re.IGNORECASE),
    # Section N  /  SECTION 10  /  Section 1.1
    re.compile(r"^SECTION\s+[\d\.]+", re.IGNORECASE),
    # 数字 + 空格 + 中文或大写（GSK 双语：1 定义 DEFINITIONS）
    re.compile(r"^\d{1,2}[\s　]+[\u4e00-\u9fffA-Z]"),
    # REPRESENTATIONS AND WARRANTIES（全大写段落标题）
    re.compile(r"^[A-Z][A-Z\s\-]{8,}$"),
]

MAX_HEADING_LEN = 150  # 超过此长度的行不视为标题

# 目录行特征：含 5 个以上连续点号，末尾跟随页码数字
_TOC_RE = re.compile(r"\.{5,}[\s\u3000]*\d+\s*$")


def _is_toc_line(s: str) -> bool:
    """目录行过滤：含大量点号 + 末尾页码，不作为正文标题。"""
    return bool(_TOC_RE.search(s))


def _is_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > MAX_HEADING_LEN:
        return False
    if _is_toc_line(s):
        return False
    for pat in _HEADING_PATTERNS:
        if pat.match(s):
            return True
    return False


# ──────────────────────────────────────────────
# 2. 关键词列表（每组至少命中一个即匹配）
# ──────────────────────────────────────────────
_KEYWORD_GROUPS: list[list[str]] = [
    # 中文
    ["基金费用", "费用", "付款", "支付", "报酬"],
    ["违约责任", "责任划分", "赔偿"],
    ["终止", "解除", "变更", "清算"],
    ["争议解决", "仲裁", "适用法律"],
    ["禁止行为", "限制"],
    ["保管", "托管", "监督", "核查"],
    ["指令的发送", "确认及执行"],
    ["收益分配"],
    # 英文
    ["Indemnification", "Indemnity", "Liability"],
    ["Termination", "Default", "Events of Default"],
    ["Purchase Price", "Payment", "Fees", "Consideration"],
    ["Representations and Warranties"],
    ["Non-Competition", "Non-Solicitation"],
    ["Governing Law", "Dispute Resolution", "Jurisdiction"],
    ["Confidentiality"],
    ["Closing", "Conditions to Closing"],
    # 双语 GSK
    ["付款条件", "Payment Terms"],
    ["质量", "Quality", "Specifications"],
    ["知识产权", "Intellectual Property"],
    ["赔偿责任"],
    ["终止解除"],
    ["反贿赂", "Anti-Corruption", "Anti-Bribery"],
    ["不良事件", "Adverse Events"],
]

# 将所有关键词压平，转小写备用
_ALL_KEYWORDS_LOWER: list[str] = [
    kw.lower() for group in _KEYWORD_GROUPS for kw in group
]


def _heading_matches(heading: str) -> bool:
    h_lower = heading.lower()
    return any(kw in h_lower for kw in _ALL_KEYWORDS_LOWER)


# ──────────────────────────────────────────────
# 3. 数据结构
# ──────────────────────────────────────────────
class Section(NamedTuple):
    heading: str
    body: str  # 完整正文（后续截取前 BODY_CHARS）


# ──────────────────────────────────────────────
# 4. PDF → 章节列表
# ──────────────────────────────────────────────
def extract_text(pdf_path: Path) -> str:
    doc = fitz.open(str(pdf_path))
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages)


def split_sections(text: str) -> list[Section]:
    """按标题行切分，返回 (标题, 正文) 列表。"""
    lines = text.splitlines()
    sections: list[Section] = []
    current_heading: str | None = None
    body_lines: list[str] = []

    for line in lines:
        if _is_heading(line):
            # 保存上一节
            if current_heading is not None:
                sections.append(Section(
                    heading=current_heading,
                    body="\n".join(body_lines).strip(),
                ))
            current_heading = line.strip()
            body_lines = []
        else:
            if current_heading is not None:
                body_lines.append(line)

    # 最后一节
    if current_heading is not None:
        sections.append(Section(
            heading=current_heading,
            body="\n".join(body_lines).strip(),
        ))

    return sections


# ──────────────────────────────────────────────
# 5. 格式化输出
# ──────────────────────────────────────────────
def format_section(sec: Section) -> str:
    body_preview = sec.body[:BODY_CHARS]
    # 若截断，加省略号
    if len(sec.body) > BODY_CHARS:
        body_preview += "\n…（正文已截断）"
    return f"=== {sec.heading} ===\n{body_preview}\n---\n"


# ──────────────────────────────────────────────
# 6. 主流程
# ──────────────────────────────────────────────
def process_pdf(pdf_path: Path) -> str:
    text = extract_text(pdf_path)
    sections = split_sections(text)
    matched = [s for s in sections if _heading_matches(s.heading)]

    if not matched:
        return f"（未检测到匹配关键条款，共解析到 {len(sections)} 个章节）\n"

    header = (
        f"文件: {pdf_path.name}\n"
        f"总章节数: {len(sections)}  命中关键条款: {len(matched)}\n"
        f"{'=' * 72}\n\n"
    )
    body = "\n".join(format_section(s) for s in matched)
    return header + body


def main() -> None:
    pdfs = sorted(CONTRACTS_DIR.glob("*.pdf"))
    if not pdfs:
        print("未找到 PDF 文件。")
        sys.exit(0)

    SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)

    for pdf_path in pdfs:
        print(f"处理: {pdf_path.name} ...", end=" ", flush=True)
        try:
            content = process_pdf(pdf_path)
            out_path = SUMMARIES_DIR / (pdf_path.stem + "_clauses.txt")
            out_path.write_text(content, encoding="utf-8")
            # 统计命中数（content 里数 === 的个数）
            hits = content.count("\n=== ")
            print(f"命中 {hits} 条 → {out_path.name}")
        except Exception as e:
            print(f"失败: {e}")

    print(f"\n完成，共处理 {len(pdfs)} 个文件。")


if __name__ == "__main__":
    main()
