# Pipeline Experiment Summary

## What Changed

- Enlarged the first-stage coarse recall pool.
- Strengthened lexical scoring from simple overlap to a more BM25-like saturation score.
- Added lightweight candidate filtering for obvious low-value chunks such as TOC/title-style chunks.
- Reused the upgraded retrieval path inside the offline benchmark so evaluation and runtime retrieval stay aligned.

## Baseline vs Experiment

| Dataset | Baseline Chunk | Experiment Chunk | Baseline Best Method | Experiment Best Method | Baseline Recall@1 | Experiment Recall@1 | Baseline Recall@3 | Experiment Recall@3 | Baseline Recall@5 | Experiment Recall@5 |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|
| Chinese short contracts | 320 / 80 | 320 / 80 | lexical | lexical | 0.4000 | 0.4000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| English short contracts | 900 / 150 | 900 / 150 | lexical | lexical | 0.7500 | 0.7500 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| English long credit agreement | 480 / 120 | 480 / 120 | lexical | lexical | 0.3333 | 0.5000 | 0.5196 | 0.8529 | 0.5294 | 0.8627 |
| Chinese long credit agreement | 240 / 60 | 160 / 40 | hybrid | hybrid | 0.1958 | 0.1864 | 0.4208 | 0.4530 | 0.6786 | 0.6477 |

## Readout

- Short-contract datasets were already close to saturation, so the new pipeline did not materially change results.
- The upgraded pipeline helped the long English legal contract the most: lexical retrieval improved sharply under the larger coarse pool and filtering.
- The Chinese long legal contract showed a mixed result: Recall@3 improved, but Recall@1 and Recall@5 dipped slightly under the new setup.
- This suggests the stronger pipeline is clearly helpful for long English legal text, while the Chinese long-contract setup still needs another tuning round for chunking and hybrid fusion.

## Report Paths

- Chinese short baseline: `backend/data/eval/retrieval_benchmark_report.md`
- Chinese short experiment: `backend/data/eval_pipeline_experiments/short_contracts_zh/retrieval_benchmark_report.md`
- English short baseline: `backend/data/eval/en_short_contracts/retrieval_benchmark_report.md`
- English short experiment: `backend/data/eval_pipeline_experiments/short_contracts_en/retrieval_benchmark_report.md`
- English long baseline: `backend/data/eval/long_credit_agreement/retrieval_benchmark_report.md`
- English long experiment: `backend/data/eval_pipeline_experiments/long_credit_agreement/retrieval_benchmark_report.md`
- Chinese long baseline: `backend/data/eval/long_credit_agreement_zh/retrieval_benchmark_report.md`
- Chinese long experiment: `backend/data/eval_pipeline_experiments/long_credit_agreement_zh/retrieval_benchmark_report.md`
