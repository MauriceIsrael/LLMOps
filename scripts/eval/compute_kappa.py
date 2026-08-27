"""Script to compute Cohen's kappa and 95% confidence interval on two separate annotation CSV files.

Per Workorder v2 §5.3 & User Instructions:
- Reads TWO distinct CSV files on disk (annotator1.csv and annotator2.csv / annotator1_retest.csv).
- Computes Cohen's kappa coefficient and 95% confidence interval.
- Rule: If 95% CI lower bound < 0.50, result is INCONCLUSIVE (neither success nor failure).
"""

import csv
import math
import sys
from pathlib import Path


def load_annotations(csv_path: Path) -> list[int]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Annotation file missing: {csv_path}")

    labels = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            val = row.get("is_decision_point", "").strip()
            if val == "":
                continue
            labels.append(1 if val in ("1", "true", "True", "YES", "yes") else 0)
    return labels


def compute_kappa_with_ci(anno1: list[int], anno2: list[int]) -> tuple[float, float, float]:
    if len(anno1) != len(anno2) or not anno1:
        raise ValueError("Annotation vectors must be non-empty and equal length.")

    n = len(anno1)
    po = sum(1 for a, b in zip(anno1, anno2) if a == b) / n

    p_a1 = sum(anno1) / n
    p_a0 = 1 - p_a1
    p_b1 = sum(anno2) / n
    p_b0 = 1 - p_b1

    pe = (p_a1 * p_b1) + (p_a0 * p_b0)

    if pe == 1.0:
        return 1.0, 1.0, 1.0

    kappa = (po - pe) / (1 - pe)

    # Standard error of kappa
    se = math.sqrt(max(0, (po * (1 - po)) / (n * ((1 - pe) ** 2))))
    ci_lower = kappa - 1.96 * se
    ci_upper = kappa + 1.96 * se

    return kappa, ci_lower, ci_upper


def main() -> None:
    project_root = Path(__file__).parent.parent.parent
    anno_dir = project_root / "annotation"

    file1 = anno_dir / "annotator1.csv"
    file2 = anno_dir / "annotator2.csv"
    file2_retest = anno_dir / "annotator1_retest.csv"

    target_file2 = file2 if file2.exists() else file2_retest
    is_test_retest = not file2.exists() and file2_retest.exists()

    if not file1.exists() or not target_file2.exists():
        print("⚠️ Annotation CSV files not found in annotation/")
        print("   Required: annotation/annotator1.csv AND (annotation/annotator2.csv OR annotation/annotator1_retest.csv)")
        print("   Execution stopped until human annotation is completed.")
        sys.exit(1)

    labels1 = load_annotations(file1)
    labels2 = load_annotations(target_file2)

    if not labels1 or not labels2:
        print("⚠️ Annotation files exist but contain no filled is_decision_point labels.")
        sys.exit(1)

    kappa, ci_lower, ci_upper = compute_kappa_with_ci(labels1, labels2)

    metric_name = "Stabilité intra-annotateur" if is_test_retest else "Accord inter-annotateurs"

    print(f"📊 {metric_name} (Cohen's Kappa): kappa = {kappa:.3f}")
    print(f"   95% Confidence Interval: [{ci_lower:.3f}, {ci_upper:.3f}]")

    if is_test_retest:
        print("ℹ️ Test-retest variant retained: Stop Criterion 1 marked 'NON ÉVALUABLE'.")
    elif ci_lower < 0.50:
        print("❌ RÉSULTAT NON CONCLUANT (ni succès ni échec): 95% CI lower bound < 0.50.")
    elif kappa < 0.60:
        print("❌ CRITÈRE D'ARRÊT 1 DÉCLENCHÉ: kappa < 0.60 (Tâche mal définie).")
    else:
        print("✅ CRITÈRE D'ARRÊT 1 VALIDÉ: kappa >= 0.60 et 95% CI lower bound >= 0.50.")


if __name__ == "__main__":
    main()
