"""
从 backend/data/contracts/ 下的每个 PDF 提取：
  - 前 3000 字符
  - 最后 1000 字符
  - 所有章节标题（匹配中英文常见模式）
输出到同目录下的 summaries/ 文件夹，每个 PDF 对应一个 .txt 文件。
"""

import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

CONTRACTS_DIR = Path(__file__).parent.parent
SUMMARIES_DIR = Path(__file__).parent

HEAD_CHARS = 3000
TAIL_CHARS = 1000

# 章节标题匹配模式（行级匹配）
HEADING_PATTERNS = [
    re.compile(r"第\s*[一二三四五六七八九十百\d]+\s*[章节条款项]"),   # 第X章 / 第X条 / 第X节
    re.compile(r"^[一二三四五六七八九十百]+[、．.]\s*[\u4e00-\u9fff]"),  # 一、前言 / 二、释义
    re.compile(r"Article\s+\d+", re.IGNORECASE),
    re.compile(r"Section\s+[\d\.]+", re.IGNORECASE),
    re.compile(r"^\s*\d+\.\s+[A-Z\u4e00-\u9fff]"),                  # 1. 大写或中文开头
    re.compile(r"ARTICLE\s+[IVXLCDM\d]+"),                           # ARTICLE IV 等罗马数字
    re.compile(r"附\s*[录件表]\s*[一二三四五六七八九十\d]*"),          # 附录 / 附件
]


def extract_text(pdf_path: Path) -> str:
    doc = fitz.open(str(pdf_path))
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


def find_headings(text: str) -> list[str]:
    seen: set[str] = set()
    headings: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) > 120:
            continue
        for pat in HEADING_PATTERNS:
            if pat.search(stripped):
                key = re.sub(r"\s+", " ", stripped)
                if key not in seen:
                    seen.add(key)
                    headings.append(stripped)
                break
    return headings


def summarize(pdf_path: Path) -> str:
    text = extract_text(pdf_path)
    total = len(text)

    head = text[:HEAD_CHARS]
    tail = text[max(0, total - TAIL_CHARS):]
    headings = find_headings(text)

    lines = [
        f"{'=' * 72}",
        f"文件: {pdf_path.name}",
        f"总字符数: {total:,}",
        f"{'=' * 72}",
        "",
        f"── 前 {HEAD_CHARS} 字符 ──────────────────────────────────────────────",
        head,
        "",
        f"── 最后 {TAIL_CHARS} 字符 ───────────────────────────────────────────",
        tail,
        "",
        f"── 章节标题（共 {len(headings)} 条）────────────────────────────────",
    ]
    if headings:
        for i, h in enumerate(headings, 1):
            lines.append(f"  {i:>3}. {h}")
    else:
        lines.append("  （未检测到匹配的章节标题）")
    lines.append("")
    return "\n".join(lines)


def main():
    pdfs = sorted(CONTRACTS_DIR.glob("*.pdf"))
    if not pdfs:
        print("未找到 PDF 文件。")
        sys.exit(0)

    SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)

    for pdf_path in pdfs:
        print(f"处理: {pdf_path.name} ...", end=" ", flush=True)
        try:
            content = summarize(pdf_path)
            out_name = pdf_path.stem + "_summary.txt"
            out_path = SUMMARIES_DIR / out_name
            out_path.write_text(content, encoding="utf-8")
            print(f"→ {out_name}")
        except Exception as e:
            print(f"失败: {e}")

    print(f"\n完成，共处理 {len(pdfs)} 个文件，输出目录: {SUMMARIES_DIR}")


if __name__ == "__main__":
    main()
