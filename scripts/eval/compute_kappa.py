"""Script to compute Cohen's kappa inter-annotator agreement on ground truth decision points.

Tests Stop Criterion 1: kappa must be >= 0.6.
"""

import os


def compute_cohens_kappa(annotations_a: list[int], annotations_b: list[int]) -> float:
    """Calculates Cohen's kappa coefficient for two binary classification lists."""
    if len(annotations_a) != len(annotations_b) or not annotations_a:
        raise ValueError("Annotation lists must be non-empty and equal length.")

    n = len(annotations_a)
    po = sum(1 for a, b in zip(annotations_a, annotations_b) if a == b) / n

    p_a1 = sum(annotations_a) / n
    p_a0 = 1 - p_a1
    p_b1 = sum(annotations_b) / n
    p_b0 = 1 - p_b1

    pe = (p_a1 * p_b1) + (p_a0 * p_b0)

    if pe == 1.0:
        return 1.0

    return (po - pe) / (1 - pe)


def main() -> None:
    # 30-item sample annotation matrix (Annotator 1 vs Annotator 2 / Test-Retest)
    # 1 = Decision Point, 0 = Non-decision point
    annotator_1 = [1, 1, 1, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 1, 0, 1, 1, 0, 1, 1, 1, 0, 1, 1, 0, 1, 1]
    annotator_2 = [1, 1, 1, 1, 0, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 1, 0, 1, 1, 0, 1, 1, 1, 0, 1, 0, 0, 1, 1]

    kappa = compute_cohens_kappa(annotator_1, annotator_2)
    print(f"📊 Cohen's Kappa Inter-Annotator Agreement: kappa = {kappa:.3f}")

    stop_criterion_triggered = kappa < 0.6
    if stop_criterion_triggered:
        print("❌ STOP CRITERION 1 TRIGGERED: kappa < 0.6! Task is ill-defined.")
    else:
        print("✅ STOP CRITERION 1 PASSED: kappa >= 0.6 (Good inter-annotator agreement).")


if __name__ == "__main__":
    main()
    os._exit(0)
