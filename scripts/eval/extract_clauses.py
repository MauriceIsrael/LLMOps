"""Script to extract candidate specification clauses and generate annotation/candidates.csv.

Per Workorder v2 §5.2:
- Generates annotation/candidates.csv with clause references and THREE EMPTY COLUMNS:
  is_decision_point, question, verbatim.
- The agent DOES NOT fill any of these three columns (even as suggestions).
"""

import csv
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "eval_config.json"


def main() -> None:
    project_root = Path(__file__).parent.parent.parent
    extracted_dir = project_root / "data" / "eval" / "extracted"

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    csv_path = project_root / "annotation" / "candidates.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["clause_id", "doc_id", "title", "snippet_text", "is_decision_point", "question", "verbatim"]

    candidate_rows = []

    for spec in config.get("target_specifications", []):
        doc_id = spec["doc_id"]
        txt_path = extracted_dir / f"{doc_id.replace(' ', '_')}.txt"

        if not txt_path.exists():
            print(f"⚠️ Extracted text for {doc_id} missing at {txt_path.name}")
            continue

        text = txt_path.read_text(encoding="utf-8")
        paragraphs = [p.strip() for p in text.split("  ") if len(p.strip()) > 30]

        idx = 1
        for p in paragraphs[:10]:
            snippet = p[:150] + "..." if len(p) > 150 else p
            candidate_rows.append(
                {
                    "clause_id": f"{doc_id} # Clause-{idx}",
                    "doc_id": doc_id,
                    "title": f"{doc_id} Functional Extract {idx}",
                    "snippet_text": snippet,
                    "is_decision_point": "",  # STRICTLY EMPTY FOR HUMAN ANNOTATION
                    "question": "",  # STRICTLY EMPTY FOR HUMAN ANNOTATION
                    "verbatim": "",  # STRICTLY EMPTY FOR HUMAN ANNOTATION
                }
            )
            idx += 1

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidate_rows)

    print(f"✅ Generated candidates CSV at: {csv_path}")
    print(f"   Total Candidate Rows: {len(candidate_rows)}")
    print("   The 3 annotation columns (is_decision_point, question, verbatim) are strictly empty for human annotation.")


if __name__ == "__main__":
    main()
