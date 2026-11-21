"""Migration ponctuelle du catalogue d'ontologie du Hub depuis la fixture d'un consommateur (issue #192).

Le Hub est la source de vérité de l'ontologie ; la fixture d'Archinex (``tests/fixtures/edp/ontology_export.json``) a été enrichie
côté Archinex seulement. Cet outil reprend ce contenu dans ``data/snapshots/ontology_export.json`` de façon **additive et
déterministe**, pour une relecture par les experts du domaine :

* une entité absente du Hub est **ajoutée** ;
* pour une entité commune, un champ **absent** du Hub est complété ; un champ présent des deux côtés et différent est un
  **conflit** : la valeur du Hub est **conservée** et le conflit est listé dans le rapport (jamais écrasé en silence) ;
* ``oracle_rules`` et ``projections`` forment un lot : complété seulement si le Hub n'a ni l'un ni l'autre (jamais de mélange) ;
* tout champ complété ou modifié incrémente ``revision`` de l'entité ;
* les **données de projet** ne migrent pas : identifiants d'exigences (``REQ-…``), identifiants de lot, de tenant ou de nœud d'un
  scénario (clés de ``projections`` / ``hydration_template`` dont la valeur en porte, mots-clés, clauses qui ne sont pas des URN) ;
* les triplets sont réunis (par identifiant, puis par triplet sujet/prédicat/objet) ; un rattachement ``governed_by_clauses`` reçoit son
  triplet ``satisfies_clause`` (exigé par ``validate_clause_leaf_integrity``) avec une justification qui dit sa provenance ;
* garde-fou final : si une marque de projet subsiste dans ce qui est migré, l'outil échoue.

    python scripts/migrate_ontology_from_fixture.py --source <fixture.json>            # simulation, rapport sur la sortie standard
    python scripts/migrate_ontology_from_fixture.py --source <fixture.json> --write --report docs/ONTOLOGY-MIGRATION-REPORT.md
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

from pipelines.ontology.catalog import (
    CLAUSE_URN_PATTERN,
    build_clause_index,
    validate_clause_leaf_integrity,
)

CATALOG_PATH = Path("data/snapshots/ontology_export.json")
MIGRATION_DATE = "2026-11-21T00:00:00Z"

# Marques de projet : numéro de lot, nom de projet, organisation de scénario, identifiant d'exigence.
PROJECT_MARK = re.compile(r"lot[ _-]?[0-9]|lulu|org-lot|REQ-", re.IGNORECASE)

# Champs d'une entité qui peuvent être complétés depuis la source (le reste suit la règle « le Hub fait foi »).
SIMPLE_FIELDS = ("keywords", "hydration_template", "governed_by_clauses", "togaf_domain", "document_engine_layer",
                 "default_decision_type", "instantiated_component")
RULE_BUNDLE = ("oracle_rules", "projections")
PLAIN_FIELDS = ("title", "domain", "kind", "is_default_standard")  # jamais modifiés sur une entité commune

TRIPLET_SC_PREFIX = "tr-sc-"
TRIPLET_MIG_PREFIX = "tr-mig-"


def _has_mark(value: Any) -> bool:
    return bool(PROJECT_MARK.search(json.dumps(value, ensure_ascii=False)))


def _empty(value: Any) -> bool:
    return value is None or value == [] or value == {}


def _extends(source: Any, hub: Any) -> bool:
    """Vrai si la source ne fait qu'AJOUTER au Hub : mêmes valeurs pour tout ce que le Hub porte déjà (additif, pas un conflit)."""
    if isinstance(hub, dict):
        return isinstance(source, dict) and all(k in source and _extends(source[k], v) for k, v in hub.items())
    if isinstance(hub, list):
        return isinstance(source, list) and all(any(_extends(x, h) for x in source) for h in hub)
    return source == hub


class Report:
    def __init__(self) -> None:
        self.added_entities: list[str] = []
        self.enriched: dict[str, list[str]] = {}
        self.conflicts: list[dict[str, Any]] = []
        self.stripped: list[tuple[str, str, str]] = []  # (urn, champ, détail)
        self.revision_bumps: dict[str, tuple[int, int]] = {}
        self.triplets_added: list[str] = []
        self.triplets_generated: list[str] = []
        self.triplets_renamed: list[tuple[str, str]] = []
        self.triplets_skipped: list[tuple[str, str]] = []
        self.triplet_conflicts: list[str] = []
        self.kept_titles = 0


def sanitize_entity(urn: str, entity: dict[str, Any], rep: Report) -> dict[str, Any]:
    """Retire d'une entité de la source ce qui est donnée de projet ; tout retrait est consigné."""
    e = copy.deepcopy(entity)

    if "governed_by_clauses" in e:
        keep = [c for c in e["governed_by_clauses"] if CLAUSE_URN_PATTERN.match(str(c))]
        for c in e["governed_by_clauses"]:
            if c not in keep:
                rep.stripped.append((urn, "governed_by_clauses", f"« {c} » n'est pas une URN de clause (identifiant d'exigence de projet)"))
        e["governed_by_clauses"] = sorted(set(keep)) if keep else []
        if not e["governed_by_clauses"]:
            del e["governed_by_clauses"]

    if "keywords" in e:
        keep_kw = [k for k in e["keywords"] if not _has_mark(k)]
        for k in e["keywords"]:
            if k not in keep_kw:
                rep.stripped.append((urn, "keywords", f"mot-clé « {k} » (marque de projet)"))
        e["keywords"] = keep_kw
        if not e["keywords"]:
            del e["keywords"]

    for part in ("projections", "hydration_template"):
        if isinstance(e.get(part), dict):
            for key in list(e[part].keys()):
                if _has_mark(e[part][key]):
                    rep.stripped.append((urn, f"{part}.{key}", "valeur d'instance d'un scénario de projet"))
                    del e[part][key]
            if not e[part]:
                del e[part]

    # Lot indivisible : des règles sans leurs paramètres seraient inertes ; on ne migre pas l'un sans l'autre.
    if e.get("oracle_rules") and not e.get("projections"):
        rep.stripped.append((urn, "oracle_rules", "règles sans projections après retrait des données de projet : non migrées"))
        del e["oracle_rules"]
    return e


def merge_entities(hub: dict[str, Any], source: dict[str, Any], rep: Report) -> dict[str, Any]:
    merged = copy.deepcopy(hub)
    for urn in sorted(source):
        src = sanitize_entity(urn, source[urn], rep)
        if urn not in merged:
            merged[urn] = src
            rep.added_entities.append(urn)
            continue

        cur = merged[urn]
        raw_src = source[urn]
        changed: list[str] = []

        for f in SIMPLE_FIELDS:
            hv, sv = cur.get(f), src.get(f)
            if _empty(sv) or hv == sv or _extends(hv, sv):
                continue  # rien à ajouter : la source est vide, identique ou déjà contenue dans le Hub
            if _empty(hv) or _extends(sv, hv):
                cur[f] = sv
                changed.append(f)
            else:
                rep.conflicts.append({"urn": urn, "field": f, "hub": hv, "source": sv})

        hub_bundle = [cur.get(f) for f in RULE_BUNDLE]
        src_bundle = [src.get(f) for f in RULE_BUNDLE]
        if any(not _empty(v) for v in src_bundle) and hub_bundle != src_bundle and not all(
            _empty(sv) or _extends(h, sv) for h, sv in zip(hub_bundle, src_bundle)
        ):
            if all(_empty(v) for v in hub_bundle) or all(_empty(h) or _extends(sv, h) for h, sv in zip(hub_bundle, src_bundle)):
                for f in RULE_BUNDLE:
                    if not _empty(src.get(f)):
                        cur[f] = src[f]
                        changed.append(f)
            else:
                rep.conflicts.append({"urn": urn, "field": "oracle_rules+projections",
                                      "hub": {f: cur.get(f) for f in RULE_BUNDLE},
                                      "source": {f: src.get(f) for f in RULE_BUNDLE}})

        for f in PLAIN_FIELDS:
            if f in raw_src and f in cur and raw_src[f] != cur[f] and not _has_mark(raw_src[f]):
                if f == "title":
                    rep.kept_titles += 1
                else:
                    rep.conflicts.append({"urn": urn, "field": f, "hub": cur[f], "source": raw_src[f]})
            elif f in raw_src and f not in cur and not _has_mark(raw_src[f]):
                cur[f] = raw_src[f]
                changed.append(f)

        if changed:
            old = int(cur.get("revision", 1))
            cur["revision"] = old + 1
            rep.enriched[urn] = changed
            rep.revision_bumps[urn] = (old, old + 1)
    return merged


def merge_triplets(hub_t: list[dict[str, Any]], src_t: list[dict[str, Any]], entities: dict[str, Any], rep: Report) -> list[dict[str, Any]]:
    out = [copy.deepcopy(t) for t in hub_t]
    ids = {t["id"] for t in out}
    keys = {(t["subject"], t["predicate"], t["object"]) for t in out}
    next_mig = 1
    for t in sorted(src_t, key=lambda x: x["id"]):
        key = (t["subject"], t["predicate"], t["object"])
        if _has_mark(t.get("object")) or _has_mark(t.get("subject")):
            rep.triplets_skipped.append((t["id"], "marque de projet dans le sujet ou l'objet"))
            continue
        if t["subject"] not in entities:
            rep.triplets_skipped.append((t["id"], f"sujet absent du catalogue : {t['subject']}"))
            continue
        if t["predicate"] == "satisfies_clause":
            # Régénérés plus bas à partir de governed_by_clauses (une seule source).
            continue
        if key in keys:
            rep.triplets_skipped.append((t["id"], "triplet déjà présent (même sujet, prédicat, objet)"))
            continue
        new = copy.deepcopy(t)
        if _has_mark(new.get("rationale", "")):
            rep.stripped.append((t["id"], "rationale", "marque de projet dans la justification : remplacée"))
            new["rationale"] = "Lien repris de la fixture d'Archinex ; justification à rédiger par le relecteur du domaine."
        if new["id"] in ids:
            renamed = f"{TRIPLET_MIG_PREFIX}{next_mig:03d}"
            next_mig += 1
            rep.triplet_conflicts.append(f"{new['id']} (même identifiant que le Hub, contenu différent) → {renamed}")
            rep.triplets_renamed.append((new["id"], renamed))
            new["id"] = renamed
        out.append(new)
        ids.add(new["id"])
        keys.add(key)
        rep.triplets_added.append(new["id"])

    # satisfies_clause : un triplet par (feuille, clause) de governed_by_clauses, justification explicite sur sa provenance.
    sc_n = max([int(t["id"][len(TRIPLET_SC_PREFIX):]) for t in out if t["id"].startswith(TRIPLET_SC_PREFIX)] + [0])
    have = {(t["subject"], t["object"]) for t in out if t["predicate"] == "satisfies_clause"}
    for urn in sorted(entities):
        e = entities[urn]
        if e.get("kind") != "leaf":
            continue
        for clause in e.get("governed_by_clauses", []):
            if (urn, clause) in have:
                continue
            sc_n += 1
            tid = f"{TRIPLET_SC_PREFIX}{sc_n:03d}"
            out.append({
                "id": tid, "subject": urn, "predicate": "satisfies_clause", "object": clause,
                "rationale": "Rattachement repris de la fixture d'Archinex (governed_by_clauses) ; justification à rédiger par le relecteur du domaine.",
            })
            rep.triplets_generated.append(tid)
    return out


def guard_no_project_data(entities: dict[str, Any], before: dict[str, Any]) -> list[str]:
    """Aucune marque de projet dans ce que la migration a ajouté ou modifié."""
    bad = []
    for urn, e in entities.items():
        if before.get(urn) != e and _has_mark(e) and not _has_mark(before.get(urn, {})):
            bad.append(urn)
    return bad


def render_report(rep: Report, before: dict[str, Any], after: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Rapport de migration de l'ontologie depuis la fixture d'Archinex")
    a("")
    a("Généré par `scripts/migrate_ontology_from_fixture.py` (issue #192). **Aide à la relecture** : chaque ajout est de la doctrine à valider "
      "par les experts du domaine ; les conflits ne sont **pas** tranchés (la valeur du Hub est conservée).")
    a("")
    a("## Synthèse")
    a("")
    a(f"- Entités : {len(before['entities'])} → **{len(after['entities'])}** ({len(rep.added_entities)} ajoutées, {len(rep.enriched)} enrichies, "
      f"{sum(1 for _ in rep.conflicts)} conflit(s) conservés côté Hub).")
    leaves = [u for u, e in after["entities"].items() if e.get("kind") == "leaf"]
    a(f"- Feuilles : {sum(1 for e in before['entities'].values() if e.get('kind') == 'leaf')} → **{len(leaves)}** ; "
      f"avec `projections` : {sum(1 for e in before['entities'].values() if e.get('kind') == 'leaf' and e.get('projections'))} → "
      f"**{sum(1 for u in leaves if after['entities'][u].get('projections'))}**.")
    a(f"- Triplets : {len(before['triplets'])} → **{len(after['triplets'])}** ({len(rep.triplets_added)} repris, "
      f"{len(rep.triplets_generated)} `satisfies_clause` générés, {len(rep.triplets_skipped)} écartés).")
    a(f"- Titres différents conservés côté Hub (sans conflit de fond) : {rep.kept_titles}.")
    a(f"- Données de projet retirées : {len(rep.stripped)}.")
    a("")
    a("## À trancher par les experts : conflits (valeur du Hub conservée)")
    a("")
    if not rep.conflicts:
        a("Aucun.")
    for c in rep.conflicts:
        a(f"### `{c['urn']}` : `{c['field']}`")
        a("")
        a("- **Hub (conservé)** : `" + json.dumps(c["hub"], ensure_ascii=False)[:400] + "`")
        a("- **Fixture d'Archinex** : `" + json.dumps(c["source"], ensure_ascii=False)[:400] + "`")
        a("")
    a("## Données de projet retirées de la migration")
    a("")
    for urn, field, detail in rep.stripped:
        a(f"- `{urn}` · `{field}` : {detail}")
    a("")
    a("## Entités enrichies (champ absent du Hub complété ; `revision` incrémentée)")
    a("")
    for urn, fields in sorted(rep.enriched.items()):
        o, n = rep.revision_bumps[urn]
        a(f"- `{urn}` : {', '.join(fields)} (révision {o} → {n})")
    a("")
    a("## Entités ajoutées")
    a("")
    for urn in rep.added_entities:
        e = after["entities"][urn]
        a(f"- `{urn}` ({e.get('kind')}, révision {e.get('revision')}) : {e.get('title', '')}")
    a("")
    a("## Triplets")
    a("")
    if rep.triplets_renamed:
        a("Identifiants en collision avec le Hub (contenu différent), renumérotés :")
        for old, new in rep.triplets_renamed:
            a(f"- `{old}` → `{new}`")
        a("")
    a(f"Triplets `satisfies_clause` générés : {len(rep.triplets_generated)} (justification « reprise de la fixture, à rédiger »).")
    a("")
    if rep.triplets_skipped:
        a("Triplets de la source écartés :")
        for tid, why in rep.triplets_skipped:
            a(f"- `{tid}` : {why}")
    a("")
    return "\n".join(lines) + "\n"


def migrate(catalog: dict[str, Any], source: dict[str, Any]) -> tuple[dict[str, Any], Report]:
    rep = Report()
    out = copy.deepcopy(catalog)
    out["entities"] = merge_entities(catalog["entities"], source["entities"], rep)
    out["triplets"] = merge_triplets(catalog["triplets"], source["triplets"], out["entities"], rep)
    bad = guard_no_project_data(out["entities"], catalog["entities"])
    if bad:
        raise SystemExit("Marque de projet résiduelle dans : " + ", ".join(bad))
    out["generated_at"] = MIGRATION_DATE
    out["clause_index"] = build_clause_index(out["entities"], out["triplets"])
    errors = validate_clause_leaf_integrity(out)
    if errors:
        raise SystemExit("Intégrité clause ↔ feuille rompue :\n  " + "\n  ".join(errors[:15]))
    return out, rep


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, type=Path, help="Fixture d'ontologie du consommateur (forme catalogue).")
    ap.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    ap.add_argument("--write", action="store_true", help="Écrit le catalogue (sinon simulation).")
    ap.add_argument("--report", type=Path, help="Écrit le rapport de relecture (Markdown).")
    args = ap.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    source = json.loads(args.source.read_text(encoding="utf-8"))
    out, rep = migrate(catalog, source)
    report = render_report(rep, catalog, out)
    if args.report:
        args.report.write_text(report, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(report)
    if args.write:
        args.catalog.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(f"Catalogue écrit : {args.catalog}", file=sys.stderr)


if __name__ == "__main__":
    main()
