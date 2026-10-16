#!/usr/bin/env python3
"""CLI Runner for ClaimWise F1 Evidence-Grounded Q&A 40-Question Systematic Benchmark.

Usage:
    # Run fast deterministic benchmark:
    python backend/scripts/run_qa_benchmark.py

    # Run live Gemini API benchmark:
    python backend/scripts/run_qa_benchmark.py --live

    # Run quick smoke test on first 5 questions:
    python backend/scripts/run_qa_benchmark.py --max 5

"Evidence first. If no proof, no answer."
"""

import argparse
import json
import os
import sys
import time

# Ensure backend root is on sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(script_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.benchmarks.qa_benchmark_service import qa_benchmark_service


def main():
    parser = argparse.ArgumentParser(
        description="Run ClaimWise Systematic 40-Question Evidence Q&A Benchmark."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute against live Google Gemini API (requires GEMINI_API_KEY in environment).",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="Maximum number of questions to evaluate (default: all 40).",
    )
    parser.add_argument(
        "--out-md",
        type=str,
        default=None,
        help="Path to write Markdown evaluation report (default: docs/QA_40_BENCHMARK_REPORT.md).",
    )
    parser.add_argument(
        "--out-json",
        type=str,
        default=None,
        help="Path to write JSON evaluation metrics (default: docs/qa_benchmark_results.json).",
    )

    args = parser.parse_args()

    repo_root = os.path.dirname(backend_dir)
    docs_dir = os.path.join(repo_root, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    out_md = args.out_md or os.path.join(docs_dir, "QA_40_BENCHMARK_REPORT.md")
    out_json = args.out_json or os.path.join(docs_dir, "qa_benchmark_results.json")

    mode_label = "LIVE GOOGLE GEMINI API" if args.live else "DETERMINISTIC VERIFIED MOCK"
    print("=" * 78)
    print(" CLAIMWISE — F1 EVIDENCE-GROUNDED Q&A SYSTEMATIC BENCHMARK")
    print(" Tagline: 'Evidence first. If no proof, no answer.'")
    print(f" Execution Mode: {mode_label}")
    print("=" * 78)

    print("\n[1/3] Hydrating test policies (Sample Policy A & B)...")
    hydration = qa_benchmark_service.hydrate_test_policies()
    print(f"      Policy A: {hydration['policy_a_clauses']} clauses indexed.")
    print(f"      Policy B: {hydration['policy_b_clauses']} clauses indexed.")

    print(f"\n[2/3] Evaluating benchmark questions (max={args.max or 40})...")
    start_time = time.perf_counter()
    report = qa_benchmark_service.run_benchmark(use_live_llm=args.live, max_questions=args.max)
    total_elapsed = time.perf_counter() - start_time

    summary = report.summary

    print(f"\n[3/3] Evaluation complete in {total_elapsed:.2f}s!")
    print("\n" + "=" * 78)
    print(" BENCHMARK PERFORMANCE AUDIT SUMMARY")
    print("=" * 78)
    print(f" Total Questions Evaluated:  {summary.total_questions:2d} (Answerable: {summary.answerable_count}, Unanswerable: {summary.unanswerable_count})")
    print(f" Overall Decision Accuracy:   {summary.decision_accuracy_pct:6.1f}%  (Standard: 100.0%)")
    print(f" Evidence Groundedness Rate:  {summary.groundedness_pct:6.1f}%  (Standard: 100.0%)")
    print(f" Citation Accuracy Rate:      {summary.citation_accuracy_pct:6.1f}%  (Standard: 100.0%)")
    print(f" Honest Abstention Rate:      {summary.honest_abstention_pct:6.1f}%  (Standard: 100.0%)")
    print(f" Hallucination Rate:          {summary.hallucination_rate_pct:6.1f}%  (Standard:   0.0%)")
    print(f" Adversarial Defense Rate:    {summary.adversarial_defense_pct:6.1f}%  (Standard: 100.0%)")
    print(f" Retrieval Top-K Recall:      {summary.retrieval_top_k_recall_pct:6.1f}%  (Standard: >= 95.0%)")
    print(f" Average Latency per Query:   {summary.avg_latency_ms:6.1f} ms")
    print(f" Final Benchmark Verdict:     {'>>> PASSED ALL STANDARDS <<<' if summary.all_passed else '>>> SOME STANDARDS FAILED <<<'}")
    print("=" * 78)

    # Save Markdown Report
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(report.to_markdown_table())
    print(f"\nSaved Markdown Report to: {out_md}")

    # Save JSON Results
    with open(out_json, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
    print(f"Saved JSON Raw Data to:    {out_json}")

    return 0 if summary.all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
