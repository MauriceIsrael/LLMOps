"""Essai de bout en bout, en local : engagement du Hub → instantané scellé → projection → Document Engine → HLD (#155, #153).

    make e2e-suite                          # le Document Engine est le dépôt voisin ../document-engine (`npm ci` fait)
    DOCUMENT_ENGINE_DIR=/chemin make e2e-suite

Ce que la chaîne **fait** : un instantané d'engagement du Hub (le scénario illustratif du canal K11, reconstruit sans serveur) est vérifié,
ses décisions affirmées sont projetées en ``governanceStatements`` (``pipelines/engagement/governance_projection.py``), greffées sur un
graphe de démonstration du Document Engine, et ``npm run generate`` écrit le HLD. Le script lit le Markdown produit.

Ce que la chaîne **ne fait pas**, et que ce script ne prétend pas prouver :

* les **composants** du HLD viennent d'un graphe de démonstration du Document Engine : le Hub n'en détient aucun (#138) ;
* la **conformité** n'est pas dans ce plan : le Document Engine refuse la sortie du Hub tant que ``knowledge-hub`` n'est pas admis
  (#152, voir ``make verify-suite``) ;
* l'adaptateur n'a pas de propriétaire désigné (#40) : la projection est celle de référence ;
* hypothèses et risques ne sont pas publiés par le Hub : le plan ne porte aucun registre de risques.

Sortie : ``0`` tout est conforme ; ``1`` un contrôle échoue ; ``3`` **non vérifié** (Document Engine, node ou ``npm ci`` absents) :
jamais un vert silencieux. Les ``LIMITE`` sont des limites connues, affichées, qui ne font pas échouer l'essai.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.engagement.governance_projection import project_decisions  # noqa: E402
from pipelines.engagement.snapshot import build_data, seal  # noqa: E402
from scripts.export_engagement_example import CREATED_AT, build_example, scenario  # noqa: E402
from scripts.verify_suite import NOT_VERIFIED, locate_document_engine  # noqa: E402

BLUEPRINT = ROOT / "tests" / "fixtures" / "suite" / "hld-decisions-hub.yaml"
CONTEXT = ROOT / "tests" / "fixtures" / "suite" / "generation-context.json"
ASSERTED = "Active-active gateway across two sites"
PROPOSED = "Keep a single core site for the pilot"


def _generate(de: Path, graph: dict, work: Path, label: str) -> tuple[str, str]:
    """Écrit le graphe, lance le vrai CLI du Document Engine, rend (Markdown, sortie standard)."""
    graph_file, out = work / f"{label}.graph.json", work / label
    graph_file.write_text(json.dumps(graph), encoding="utf-8")
    run = subprocess.run(  # noqa: S603
        [str(de / "node_modules" / ".bin" / "tsx"), "generate.ts", "--graph", str(graph_file), "--blueprint", str(BLUEPRINT),
         "--context", str(CONTEXT), "--format", "md", "--out", str(out)],
        cwd=de, capture_output=True, text=True, check=False,
    )
    if run.returncode != 0:
        raise RuntimeError(f"generate a échoué ({label}) : {run.stderr[-600:] or run.stdout[-600:]}")
    return next(out.glob("*.md")).read_text(encoding="utf-8"), run.stdout


def _demoted_snapshot() -> dict:
    raw, kb = scenario()
    next(d for d in raw["decisions"] if d["id"] == "D-0001").update(status="proposed", validated_by="", validated_at="")
    next(s for s in raw["subjects"] if s["name"] == "gateway-services")["level"] = "L2_decomposed"
    return seal(build_data(raw, "example-eng", "confidential", kb), "example-eng", CREATED_AT, "example")


def main() -> int:
    de, reason = locate_document_engine()
    if de is None:
        print(f"NON VÉRIFIÉ : {reason}\nRien n'a été comparé : ce n'est pas un succès.")
        return NOT_VERIFIED
    base = json.loads((de / "fixtures" / "graphs" / "rrf-sample.json").read_text(encoding="utf-8"))
    envelope = build_example()
    statements, report = project_decisions(envelope)
    graph = {**base, "governanceStatements": statements}
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    with tempfile.TemporaryDirectory(prefix="e2e-suite-") as tmp:
        work = Path(tmp)
        md, _ = _generate(de, graph, work, "nominal")
        check("la décision affirmée est dans le HLD, avec statut, réversibilité, alternative écartée et validateur",
              all(x in md for x in (ASSERTED, "accepted", "costly", "Active-passive gateway — Failover time above the budget.", "@ada")))
        check("l'instantané qui l'a produite est cité (provenance lisible)", envelope["snapshotId"] in md, envelope["snapshotId"])
        check("la décision seulement proposée n'est pas publiée", PROPOSED not in md)
        check("le HLD dit que le Hub ne publie ni hypothèses ni risques", "ne sont pas publiés par le Knowledge Hub" in md)

        again, _ = _generate(de, graph, work, "rejeu")
        check("même état, mêmes octets", again == md)

        demoted, _ = project_decisions(_demoted_snapshot())
        md_demoted, _ = _generate(de, {**base, "governanceStatements": demoted}, work, "mutation")
        check("mutation : abaisser la décision à « proposée » la retire du HLD", ASSERTED not in md_demoted and md_demoted != md)

        _, out_absent = _generate(de, copy.deepcopy(base), work, "absent")
        _, out_empty = _generate(de, {**base, "governanceStatements": []}, work, "vide")
        check("« le graphe ne publie aucun énoncé » est signalé, pas confondu avec « il n'y en a aucun »",
              "incomplete-graph" in out_absent.lower() and "incomplete-graph" not in out_empty.lower())

    limits = []
    if report["is_provisional"]:
        limits.append("instantané provisoire (" + json.dumps(report["provisional_reasons"]) + ") : le Document Engine n'a aucun champ pour "
                      f"le porter ; le HLD ne le dit pas ({'oui' if 'provisoire' in md.lower() else 'non'}).")
    for name, ok, detail in results:
        print(f"{'OK     ' if ok else 'ÉCHEC  '}{name}{f' [{detail}]' if detail and ok else ''}")
    for limit in limits:
        print(f"LIMITE {limit}")
    failed = [name for name, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} contrôles conformes.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
