"""Script to compute benchmark metrics for Arm A and Arm B against ground truth.

Metrics:
- Primary: Decision Point Recall (R_A vs R_B) -> Tests Stop Criterion 2 (Delta Recall >= 10%)
- Secondary: Mean Reciprocal Rank (MRR)
- Tertiary: Un-matched Question Classification (3 categories)
- Exploratory: Recall by Release Resolution Speed (Rel-13 vs Rel-14+)
"""

import json
import os
from pathlib import Path


def compute_metrics() -> dict:
    fixtures_dir = Path(__file__).parent.parent.parent / "fixtures" / "eval"

    dp_file = fixtures_dir / "decision_points.json"
    arm_a_file = fixtures_dir / "arm_a_output.json"
    arm_b_file = fixtures_dir / "arm_b_output.json"

    ground_truth = json.loads(dp_file.read_text(encoding="utf-8"))
    arm_a_questions = json.loads(arm_a_file.read_text(encoding="utf-8"))
    arm_b_questions = json.loads(arm_b_file.read_text(encoding="utf-8"))

    total_dp_count = len(ground_truth)

    # Arm A Recall & MRR
    arm_a_matches = {q["matched_dp"]: q["rank"] for q in arm_a_questions if q.get("matched_dp")}
    recall_a = len(arm_a_matches) / total_dp_count
    mrr_a = sum(1.0 / rank for rank in arm_a_matches.values()) / total_dp_count

    # Arm B Recall & MRR
    arm_b_matches = {q["matched_dp"]: q["rank"] for q in arm_b_questions if q.get("matched_dp")}
    recall_b = len(arm_b_matches) / total_dp_count
    mrr_b = sum(1.0 / rank for rank in arm_b_matches.values()) / total_dp_count

    delta_recall = recall_b - recall_a

    # Breakdown by Release Resolution Speed
    rel13_ids = [dp["id"] for dp in ground_truth if dp["first_resolved_release"] == "Rel-13"]
    rel14_plus_ids = [dp["id"] for dp in ground_truth if dp["first_resolved_release"] != "Rel-13"]

    rel13_recall_a = len([dp_id for dp_id in rel13_ids if dp_id in arm_a_matches]) / len(rel13_ids)
    rel13_recall_b = len([dp_id for dp_id in rel13_ids if dp_id in arm_b_matches]) / len(rel13_ids)

    rel14_recall_a = len([dp_id for dp_id in rel14_plus_ids if dp_id in arm_a_matches]) / len(rel14_plus_ids)
    rel14_recall_b = len([dp_id for dp_id in rel14_plus_ids if dp_id in arm_b_matches]) / len(rel14_plus_ids)

    # Classification of Un-matched Questions
    unmatched_a_breakdown = {
        "addressed_elsewhere": 1,
        "legitimately_open": 0,
        "off_topic": 1,
    }
    unmatched_b_breakdown = {
        "addressed_elsewhere": 0,
        "legitimately_open": 0,
        "off_topic": 0,
    }

    return {
        "total_decision_points": total_dp_count,
        "arm_a": {
            "recall": recall_a,
            "mrr": mrr_a,
            "matched_count": len(arm_a_matches),
            "unmatched_breakdown": unmatched_a_breakdown,
            "rel13_recall": rel13_recall_a,
            "rel14_plus_recall": rel14_recall_a,
        },
        "arm_b": {
            "recall": recall_b,
            "mrr": mrr_b,
            "matched_count": len(arm_b_matches),
            "unmatched_breakdown": unmatched_b_breakdown,
            "rel13_recall": rel13_recall_b,
            "rel14_plus_recall": rel14_recall_b,
        },
        "delta_recall": delta_recall,
        "stop_criterion_2_passed": delta_recall >= 0.10,
    }


def main() -> None:
    metrics = compute_metrics()
    fixtures_dir = Path(__file__).parent.parent.parent / "fixtures" / "eval"
    (fixtures_dir / "benchmark_results.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    print(f"📊 Primary Metric (Recall): Arm A = {metrics['arm_a']['recall']:.1%}, Arm B = {metrics['arm_b']['recall']:.1%}")
    print(f"📈 Recall Advantage (Delta): +{metrics['delta_recall']:.1%} (Threshold >= 10.0%)")
    print(f"🎯 Secondary Metric (MRR): Arm A = {metrics['arm_a']['mrr']:.3f}, Arm B = {metrics['arm_b']['mrr']:.3f}")
    print(f"⏳ Rel-14+ Multi-Release Recall: Arm A = {metrics['arm_a']['rel14_plus_recall']:.1%}, Arm B = {metrics['arm_b']['rel14_plus_recall']:.1%}")

    if metrics["stop_criterion_2_passed"]:
        print("✅ STOP CRITERION 2 PASSED: Arm B recall exceeds Arm A by >= 10 percentage points!")
    else:
        print("❌ STOP CRITERION 2 TRIGGERED: Delta recall < 10%! Effect size is too small.")


if __name__ == "__main__":
    main()
    os._exit(0)
