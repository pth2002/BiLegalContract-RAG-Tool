"""Offline RAG retrieval evaluation: Recall@K / Hit@K vs gold chunk_ids.

Usage (from backend/):
  python -m src.tooling.run_retrieval_eval --gold data/retrieval_eval_gold.example.json
  python -m src.tooling.run_retrieval_eval --dump-chunks path/to/contract.docx
  python -m src.tooling.run_retrieval_eval --dump-inline-file data/retrieval_eval_gold.example.json --case-id inline_minimal

Requires: DATABASE_URL 可达、embedding 依赖已安装（与主应用相同）。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from ..models import Document, FileType, PerspectiveType
from ..services.parser_service import parse_document
from ..services.retrieval_eval_service import evaluate_retrieval_case

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_case_document(case: dict[str, Any], repo_root: Path, default_session: str) -> Document:
    session_id = case.get("session_id") or default_session
    doc_uuid = UUID(case["document_id"])
    if "inline_text" in case:
        text = (case.get("inline_text") or "").strip()
        if not text:
            raise ValueError(f"case {case.get('id')}: inline_text is empty")
        return Document(
            id=doc_uuid,
            filename=case.get("filename") or "inline.txt",
            file_type=FileType.DOCX,
            file_size=len(text.encode("utf-8")),
            page_count=1,
            text_content=text,
            session_id=session_id,
        )

    rel = case.get("file")
    if not rel:
        raise ValueError(f"case {case.get('id')}: need 'file' or 'inline_text'")
    path = (repo_root / rel).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    raw = path.read_bytes()
    text, count, ft = parse_document(raw, path.name)
    return Document(
        id=doc_uuid,
        filename=path.name,
        file_type=ft,
        file_size=len(raw),
        page_count=count,
        text_content=text,
        session_id=session_id,
    )


def _dump_chunks_for_text(text: str) -> None:
    from ..services.chunking_service import chunk_text

    chunks = chunk_text(text)
    print(f"chunks_total={len(chunks)}")
    for c in chunks:
        preview = c.content.replace("\n", " ")[:120]
        print(f"{c.chunk_id}\tchars={len(c.content)}\t{preview}")


async def _run_gold_file(gold_path: Path, repo_root: Path) -> int:
    data = json.loads(gold_path.read_text(encoding="utf-8"))
    defaults = data.get("defaults") or {}
    ks = defaults.get("top_ks") or [5, 8]
    session = defaults.get("session_id") or "retrieval_eval_session"
    final_top_k = defaults.get("final_top_k")
    cases = data.get("cases") or []
    if not cases:
        print("No cases in gold file.", file=sys.stderr)
        return 1

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    macro_recall: dict[str, list[float]] = {str(k): [] for k in ks}
    macro_hit: dict[str, list[float]] = {str(k): [] for k in ks}

    for case in cases:
        cid = case.get("id", "?")
        doc = _load_case_document(case, repo_root, session)
        perspective = PerspectiveType(case["perspective"])
        options = case.get("options")
        relevant = set(case.get("relevant_chunk_ids") or [])
        if not relevant:
            print(f"[WARN] case {cid}: empty relevant_chunk_ids (Recall 定义为 vacuous 1.0)", file=sys.stderr)

        out = await evaluate_retrieval_case(
            document=doc,
            perspective=perspective,
            options=options,
            relevant_chunk_ids=relevant,
            ks=[int(k) for k in ks],
            final_top_k=int(final_top_k) if final_top_k is not None else None,
            reindex=True,
        )
        print(f"\n=== case={cid} document_id={out['document_id']} ===")
        print(f"relevant={sorted(relevant)}")
        print(f"retrieved_top={out['retrieved_ids']}")
        for k_str, m in out["per_k"].items():
            print(f"  @{k_str}: recall={m['recall']:.4f} hit={m['hit']:.0f}")
            macro_recall[k_str].append(float(m["recall"]))
            macro_hit[k_str].append(float(m["hit"]))

    print("\n=== macro average ===")
    for k_str in macro_recall:
        rs = macro_recall[k_str]
        hs = macro_hit[k_str]
        if rs:
            print(
                f"  @{k_str}: mean_recall={sum(rs)/len(rs):.4f} "
                f"mean_hit={sum(hs)/len(hs):.4f} (n={len(rs)})"
            )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG retrieval Recall@K / Hit@K evaluation")
    parser.add_argument(
        "--gold",
        type=Path,
        help="Gold JSON path (see data/retrieval_eval_gold.example.json)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (default: backend parent = contract/)",
    )
    parser.add_argument(
        "--dump-chunks",
        type=Path,
        metavar="FILE",
        help="Print chunk_id previews for a PDF/DOCX (no DB)",
    )
    parser.add_argument(
        "--dump-inline-file",
        type=Path,
        help="Gold JSON path; use with --case-id to dump chunks for that case's inline_text",
    )
    parser.add_argument("--case-id", type=str, default=None, help="Case id inside gold JSON")
    args = parser.parse_args()
    repo = args.repo_root or _repo_root().parent

    if args.dump_chunks:
        path = args.dump_chunks
        raw = path.read_bytes()
        text, _, _ = parse_document(raw, path.name)
        _dump_chunks_for_text(text)
        return

    if args.dump_inline_file:
        data = json.loads(args.dump_inline_file.read_text(encoding="utf-8"))
        cid = args.case_id
        case = next((c for c in data.get("cases", []) if c.get("id") == cid), None)
        if not case or "inline_text" not in case:
            print("Case not found or has no inline_text.", file=sys.stderr)
            sys.exit(1)
        _dump_chunks_for_text(case["inline_text"])
        return

    if args.gold:
        rc = asyncio.run(_run_gold_file(args.gold.resolve(), repo.resolve()))
        raise SystemExit(rc)

    parser.print_help()
    raise SystemExit(1)


if __name__ == "__main__":
    main()
