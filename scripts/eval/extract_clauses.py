"""Script to extract candidate specification clauses from extracted 3GPP texts into annotation/candidates.csv.

Per Workorder v2 §5.2:
- Generates annotation/candidates.csv with clause references and THREE STRICTLY EMPTY COLUMNS:
  is_decision_point, question, verbatim.
- The agent DOES NOT fill any of these three columns (even as suggestions).
"""

import csv
import json
import re
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "eval_config.json"


def extract_floor_control_clauses(text: str, doc_id: str) -> list[dict]:
    """Scans extracted spec text for clauses relevant to floor control."""
    keywords = ["floor control", "floor request", "floor grant", "floor override", "floor revoke", "floor queue"]
    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]

    if not paragraphs:
        paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 50]

    matched_clauses = []
    idx = 1

    for p in paragraphs:
        p_lower = p.lower()
        if any(kw in p_lower for kw in keywords):
            snippet = p[:250] + "..." if len(p) > 250 else p
            clean_snippet = re.sub(r"\s+", " ", snippet).strip()

            matched_clauses.append(
                {
                    "clause_id": f"{doc_id} # Clause-{idx}",
                    "doc_id": doc_id,
                    "title": f"{doc_id} Floor Control Extract {idx}",
                    "snippet_text": clean_snippet,
                    "is_decision_point": "",  # STRICTLY EMPTY FOR HUMAN ANNOTATION
                    "question": "",  # STRICTLY EMPTY FOR HUMAN ANNOTATION
                    "verbatim": "",  # STRICTLY EMPTY FOR HUMAN ANNOTATION
                }
            )
            idx += 1
            if idx > 15:  # Cap at 15 candidate clauses per document
                break

    return matched_clauses


def main() -> None:
    project_root = Path(__file__).parent.parent.parent
    extracted_dir = project_root / "data" / "eval" / "extracted"
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    csv_path = project_root / "annotation" / "candidates.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["clause_id", "doc_id", "title", "snippet_text", "is_decision_point", "question", "verbatim"]

    candidate_rows = []

    target_specs = config.get("target_specifications", [])
    if not any(s["doc_id"] == "TS 24.380" for s in target_specs):
        target_specs.append(
            {
                "doc_id": "TS 24.380",
                "stage": 3,
                "title": "Mission Critical Push To Talk (MCPTT) media plane control; Stage 3",
            }
        )

    for spec in target_specs:
        doc_id = spec["doc_id"]
        txt_path = extracted_dir / f"{doc_id.replace(' ', '_')}.txt"

        if not txt_path.exists():
            print(f"⚠️ Extracted text for {doc_id} missing at {txt_path.name}")
            continue

        text = txt_path.read_text(encoding="utf-8")
        clauses = extract_floor_control_clauses(text, doc_id)
        candidate_rows.extend(clauses)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidate_rows)

    print(f"✅ Generated candidates CSV at: {csv_path}")
    print(f"   Total Candidate Clauses Extracted: {len(candidate_rows)}")
    print("   The 3 annotation columns (is_decision_point, question, verbatim) are strictly empty for human annotation.")


if __name__ == "__main__":
    main()
