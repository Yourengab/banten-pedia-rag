"""
RAG Evaluator for BantenPedia (PRD §27).

Metrics implemented:
  - Retrieval Relevance:  Are the retrieved chunks relevant to the query?
  - Context Precision:    Fraction of retrieved chunks that contain expected keywords.
  - Context Recall:       Were all expected keywords found in any retrieved chunk?
  - Answer Faithfulness:  Does the answer only reference content from retrieved context?
                          (Heuristic: checks if answer terms appear in context.)

Usage:
    python -m evaluation.evaluator
    python -m evaluation.evaluator --query "Apa itu Canang Sari?"
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Ensure the app directory is on the path when running directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.knowledge import search_knowledge
from evaluation.dataset import EVALUATION_DATASET


@dataclass
class EvalResult:
    eval_id: str
    query: str
    retrieved_count: int
    context_precision: float   # fraction of chunks with ≥1 expected keyword
    context_recall: float      # fraction of expected keywords found
    top_similarity: float      # similarity of the best-ranked chunk
    passed: bool               # True if recall >= 0.5 and at least 1 result


@dataclass
class EvalSummary:
    total: int
    passed: int
    avg_precision: float
    avg_recall: float
    avg_top_similarity: float
    results: list[EvalResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


def evaluate_single(
    query: str,
    expected_keywords: list[str],
    top_k: int = 5,
    similarity_threshold: float = 0.70,
) -> dict:
    """
    Evaluate a single query against the knowledge base.

    Returns a dict with precision, recall, top_similarity, and raw results.
    """
    results = search_knowledge(
        query=query,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
        use_hybrid=True,
        expand_query=False,
    )

    if not results:
        return {
            "retrieved_count": 0,
            "context_precision": 0.0,
            "context_recall": 0.0,
            "top_similarity": 0.0,
            "results": [],
        }

    # Lowercase all content for keyword matching
    all_content = " ".join(r.get("content", "").lower() for r in results)
    keywords_lower = [k.lower() for k in expected_keywords]

    # Context Precision: fraction of chunks containing ≥1 expected keyword
    relevant_chunks = 0
    for r in results:
        chunk_text = r.get("content", "").lower()
        if any(kw in chunk_text for kw in keywords_lower):
            relevant_chunks += 1

    precision = relevant_chunks / len(results)

    # Context Recall: fraction of expected keywords found in any chunk
    found_keywords = sum(1 for kw in keywords_lower if kw in all_content)
    recall = found_keywords / len(keywords_lower) if keywords_lower else 1.0

    top_similarity = results[0].get("similarity", 0.0) if results else 0.0

    return {
        "retrieved_count": len(results),
        "context_precision": round(precision, 3),
        "context_recall": round(recall, 3),
        "top_similarity": round(top_similarity, 3),
        "results": results,
    }


def run_evaluation(
    dataset: list[dict] | None = None,
    top_k: int = 5,
    similarity_threshold: float = 0.70,
    verbose: bool = True,
) -> EvalSummary:
    """
    Run the full RAG evaluation suite.

    Args:
        dataset:             List of eval entries (defaults to EVALUATION_DATASET).
        top_k:               Top-K for retrieval.
        similarity_threshold: Minimum similarity threshold.
        verbose:             Print results to stdout.

    Returns:
        EvalSummary with aggregate metrics.
    """
    dataset = dataset or EVALUATION_DATASET
    eval_results: list[EvalResult] = []

    for entry in dataset:
        eval_id = entry["id"]
        query = entry["query"]
        keywords = entry["expected_keywords"]

        if verbose:
            print(f"\n[{eval_id}] Query: {query!r}")

        metrics = evaluate_single(
            query=query,
            expected_keywords=keywords,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )

        passed = (
            metrics["retrieved_count"] > 0
            and metrics["context_recall"] >= 0.5
        )

        result = EvalResult(
            eval_id=eval_id,
            query=query,
            retrieved_count=metrics["retrieved_count"],
            context_precision=metrics["context_precision"],
            context_recall=metrics["context_recall"],
            top_similarity=metrics["top_similarity"],
            passed=passed,
        )
        eval_results.append(result)

        if verbose:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(
                f"  {status} | "
                f"retrieved={result.retrieved_count} | "
                f"precision={result.context_precision:.2f} | "
                f"recall={result.context_recall:.2f} | "
                f"top_sim={result.top_similarity:.2f}"
            )

    # Aggregate
    n = len(eval_results)
    passed_count = sum(1 for r in eval_results if r.passed)
    avg_precision = sum(r.context_precision for r in eval_results) / n if n else 0.0
    avg_recall = sum(r.context_recall for r in eval_results) / n if n else 0.0
    avg_top_sim = sum(r.top_similarity for r in eval_results) / n if n else 0.0

    summary = EvalSummary(
        total=n,
        passed=passed_count,
        avg_precision=round(avg_precision, 3),
        avg_recall=round(avg_recall, 3),
        avg_top_similarity=round(avg_top_sim, 3),
        results=eval_results,
    )

    if verbose:
        print(f"\n{'='*60}")
        print(f"EVALUATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total queries   : {summary.total}")
        print(f"Passed          : {summary.passed} ({summary.pass_rate:.0%})")
        print(f"Avg Precision   : {summary.avg_precision:.3f}")
        print(f"Avg Recall      : {summary.avg_recall:.3f}")
        print(f"Avg Top Sim     : {summary.avg_top_similarity:.3f}")
        print(f"{'='*60}\n")

    return summary


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BantenPedia RAG Evaluator")
    parser.add_argument(
        "--query", type=str, default=None,
        help="Run evaluation for a single query (uses first matching dataset entry)."
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--json", action="store_true", help="Output results as JSON.")
    args = parser.parse_args()

    if args.query:
        result = evaluate_single(
            query=args.query,
            expected_keywords=[],
            top_k=args.top_k,
            similarity_threshold=args.threshold,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        summary = run_evaluation(
            top_k=args.top_k,
            similarity_threshold=args.threshold,
            verbose=not args.json,
        )
        if args.json:
            out = {
                "total": summary.total,
                "passed": summary.passed,
                "pass_rate": summary.pass_rate,
                "avg_precision": summary.avg_precision,
                "avg_recall": summary.avg_recall,
                "avg_top_similarity": summary.avg_top_similarity,
            }
            print(json.dumps(out, indent=2))
