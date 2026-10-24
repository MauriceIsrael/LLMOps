"""Le canal de propositions suite → Hub (K7) rejoué avec le schéma de la suite (#157).

    make verify-proposals                               # Requirements Intake est le dépôt voisin ../requirements-intake (`npm ci` fait)
    REQUIREMENTS_INTAKE_DIR=/chemin make verify-proposals

Chaque candidate de ``schemas/examples/proposal_snapshot.example.json`` est relue par ``extractedCandidateSchema`` de Requirements Intake
(``packages/contracts``) : c'est la forme qu'un émetteur de la suite sait produire. Le Hub lit ces champs comme **facultatifs**
(``schemas/proposal_snapshot.schema.json``), donc son propre schéma ne suffit pas à prouver qu'un candidat d'un émetteur réel passe : cette
vérification le fait. Elle ne prouve **pas** qu'un émetteur existe : aucun n'a été trouvé dans la suite (#157).

Sortie : ``0`` conforme ; ``1`` une candidate est refusée ; ``3`` **non vérifié** (dépôt, node ou ``npm ci`` absents).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "schemas" / "examples" / "proposal_snapshot.example.json"
NOT_VERIFIED = 3


def main() -> int:
    ri = Path(os.environ.get("REQUIREMENTS_INTAKE_DIR") or ROOT.parent / "requirements-intake").resolve()
    tsx = ri / "node_modules" / ".bin" / "tsx"
    if not (ri / "packages" / "contracts" / "src" / "extractedCandidate.ts").is_file():
        reason = f"dépôt de Requirements Intake introuvable à {ri} (REQUIREMENTS_INTAKE_DIR)"
    elif shutil.which("node") is None or not tsx.exists():
        reason = f"node absent, ou `npm ci` non lancé dans {ri}"
    else:
        reason = ""
    if reason:
        print(f"NON VÉRIFIÉ : {reason}\nRien n'a été comparé : ce n'est pas un succès.")
        return NOT_VERIFIED
    run = subprocess.run([str(tsx), str(ROOT / "scripts" / "proposals_probe.mts"), str(ri), str(EXAMPLE)],  # noqa: S603
                         cwd=ri, capture_output=True, text=True, check=False)
    if run.returncode != 0:
        print(run.stderr[-1500:])
        print("NON VÉRIFIÉ : la sonde de Requirements Intake n'a pas pu s'exécuter.")
        return NOT_VERIFIED
    refused = 0
    for row in json.loads(run.stdout.strip().splitlines()[-1]):
        print(f"{row['id']} : {'accepté par extractedCandidateSchema' if row['accepted'] else 'REFUSÉ ' + '; '.join(row['issues'])}")
        refused += 0 if row["accepted"] else 1
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
