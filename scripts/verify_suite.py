"""Vérification croisée Hub ↔ Document Engine (#151, ADR-DE-41 condition 2) : le Document Engine rejoue, avec son code, ce que
le Hub émet.

    make verify-suite                                  # le Document Engine est le dépôt voisin ../document-engine
    DOCUMENT_ENGINE_DIR=/chemin make verify-suite

Ce que le script vérifie, et ce qu'il ne prouve pas :

* **Vecteurs** ``canonical-json`` identiques octet pour octet à ceux du Document Engine (le profil est le même).
* **Checksum** de chaque témoin du Hub (conformité, instantané d'engagement) recalculé par ``computeSnapshotChecksum`` du
  Document Engine : c'est la preuve par la donnée réelle, pas seulement par les vecteurs.
* **Verdict du lecteur de conformité** sur le témoin de conformité, comparé à ``EXPECTED_READER_REFUSAL``. Tant que ``knowledge-hub`` n'est
  pas admis (ADR-DE-41, #152), le verdict attendu est un **refus de provenance** : c'est un test de refus, pas un échec. Le jour de
  l'admission, il change : le script échoue, ce qui force à mettre cette table à jour avec la preuve.

Sortie : ``0`` tout a été vérifié et conforme ; ``1`` écart ; ``3`` **non vérifié** (dépôt voisin, node ou ``npm ci`` absents) :
jamais un vert silencieux quand la comparaison n'a pas eu lieu.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "tests" / "fixtures" / "canonical-json.vectors.json"
WITNESSES = [  # (nature, fichier) : seule la conformité a un lecteur dans le Document Engine
    ("conformity", ROOT / "tests" / "fixtures" / "suite" / "conformity-snapshot.golden.json"),
    ("engagement", ROOT / "schemas" / "examples" / "engagement_snapshot.example.json"),
]
NOT_VERIFIED = 3
# Avant l'admission (#152) : le lecteur refuse la provenance du Hub (premier refus, avant version, `ref` et source de preuve).
# Le lecteur de conformité lève une erreur sans code : on reconnaît le refus à son message. À mettre à jour, avec la preuve, le
# jour où la provenance est admise : le verdict attendu change alors, et ce script échoue tant qu'on ne l'a pas fait.
EXPECTED_READER_REFUSAL = "'sourceSystem' attendu 'tuleap', reçu 'knowledge-hub'"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _not_verified(reason: str) -> int:
    print(f"NON VÉRIFIÉ : {reason}")
    print("Rien n'a été comparé : ce n'est pas un succès.")
    return NOT_VERIFIED


def locate_document_engine() -> tuple[Path | None, str]:
    """Le dépôt voisin du Document Engine, prêt à servir (``npm ci`` fait), ou la raison pour laquelle il ne l'est pas."""
    de = Path(os.environ.get("DOCUMENT_ENGINE_DIR") or ROOT.parent / "document-engine").resolve()
    if not (de / "contracts" / "canonical-json.vectors.json").is_file():
        return None, f"dépôt du Document Engine introuvable à {de} (DOCUMENT_ENGINE_DIR)"
    if shutil.which("node") is None or not (de / "node_modules" / ".bin" / "tsx").exists():
        return None, f"node absent, ou `npm ci` non lancé dans {de}"
    return de, ""


def main() -> int:
    de, reason = locate_document_engine()
    if de is None:
        return _not_verified(reason)

    problems: list[str] = []

    mine, theirs = _sha(VECTORS), _sha(de / "contracts" / "canonical-json.vectors.json")
    print(f"vecteurs canonical-json : Hub {mine[:16]}…  Document Engine {theirs[:16]}…  {'identiques' if mine == theirs else 'DIFFÉRENTS'}")
    if mine != theirs:
        problems.append("les vecteurs canonical-json diffèrent du Document Engine")

    probe = subprocess.run(  # noqa: S603
        [str(de / "node_modules" / ".bin" / "tsx"), str(ROOT / "scripts" / "suite_probe.mts"), str(de),
         *(f"{kind}={path}" for kind, path in WITNESSES)],
        cwd=de, capture_output=True, text=True, check=False,
    )
    if probe.returncode != 0:
        print(probe.stderr[-2000:])
        return _not_verified("la sonde du Document Engine n'a pas pu s'exécuter")
    for row in json.loads(probe.stdout.strip().splitlines()[-1]):
        name = Path(row["file"]).name
        same = row["checksumRecomputedByDocumentEngine"] == row["checksumInEnvelope"]
        print(f"{name} (schemaVersion {row['schemaVersion']}, {row['sourceSystem']}) : checksum recalculé par le Document Engine "
              f"{'identique' if same else 'DIFFÉRENT'}")
        if not same:
            problems.append(f"{name} : checksum différent de celui que recalcule le Document Engine")
        verdict = row.get("conformityReader")
        if verdict is not None:
            print(f"{name} : lecteur de conformité du Document Engine → "
                  f"{'ACCEPTÉ' if verdict['accepted'] else 'refusé : ' + verdict['message']}")
            if verdict["accepted"] or EXPECTED_READER_REFUSAL not in verdict["message"]:
                problems.append(f"{name} : verdict du lecteur inattendu (attendu : refus « {EXPECTED_READER_REFUSAL} »). Admission de "
                                "knowledge-hub ? Mettre à jour EXPECTED_READER_REFUSAL avec la preuve, voir #152")
    for problem in problems:
        print(f"ÉCART : {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
