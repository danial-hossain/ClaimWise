#!/usr/bin/env python3
"""Run the deterministic coverage extraction and evaluation benchmark."""

import argparse
import json
from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.benchmarks.coverage_evaluation_service import (
    coverage_evaluation_service,
    coverage_evaluation_to_markdown,
)


def main() -> int:
    repository_dir = backend_dir.parent
    parser = argparse.ArgumentParser(description="Run ClaimWise coverage evaluation fixtures.")
    parser.add_argument(
        "--out-json",
        type=Path,
        default=repository_dir / "docs" / "coverage_evaluation_results.json",
        help="JSON results path.",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=repository_dir / "docs" / "COVERAGE_EVALUATION_REPORT.md",
        help="Markdown report path.",
    )
    args = parser.parse_args()

    report = coverage_evaluation_service.run()
    from coverage_event_evaluation import run_event_evaluation
    report["event_evaluation"] = run_event_evaluation()
    report["all_passed"] = report["all_passed"] and report["event_evaluation"]["passed"] == report["event_evaluation"]["total"]
    json_text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    markdown_text = coverage_evaluation_to_markdown(report)
    events = report["event_evaluation"]
    markdown_text += "\n## Recorded Stage-2 event evaluation\n\n"
    markdown_text += "Offline recorded model output; this does not measure live LLM reasoning.\n\n"
    markdown_text += "| Metric | Accuracy |\n| --- | ---: |\n"
    for metric, value in events["metrics"].items():
        markdown_text += f"| {metric} | {value:.1%} |\n"
    markdown_text += "\n| Event | Error stage |\n| --- | --- |\n"
    for event in events["events"]:
        markdown_text += f"| {event['event']} | {event['error_stage'] or 'pass'} |\n"
    for path, content in ((args.out_json, json_text), (args.out_md, markdown_text)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    print(
        f"Coverage evaluation: {report['passed_cases']}/{report['case_count']} cases passed; "
        f"retrieval recall {report['retrieval_recall_pct']:.1f}%; "
        f"result={'PASS' if report['all_passed'] else 'FAIL'}."
    )
    events = report["event_evaluation"]
    print(f"Recorded Stage-2 events: {events['passed']}/{events['total']}; metrics={events['metrics']}")
    for event in events["events"]:
        if event["error_stage"]:
            print(f"FAIL {event['event']}: {event['error_stage']}; {event['details']}")
    print(f"JSON: {args.out_json}")
    print(f"Markdown: {args.out_md}")
    if not report["all_passed"]:
        print(coverage_evaluation_to_markdown(report))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())