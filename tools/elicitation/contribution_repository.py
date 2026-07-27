"""Repository de gestion du cycle de vie des contributions spontanées externes (Part B)."""

import json
from pathlib import Path

from tools.elicitation.models.contribution_schema import Contribution
from tools.elicitation.repository import ElicitationRepository
from tools.elicitation.vocabulary_protector import map_material_vocabulary


class ContributionRepository:
    """Gestionnaire de stockage et de tri des contributions spontanées."""

    def __init__(self, engagement: str = "nordwave-mcx-2027", base_dir: str | Path = "artifacts") -> None:
        self.engagement = engagement
        self.dir = Path(base_dir) / engagement / "contributions"
        self.dir.mkdir(parents=True, exist_ok=True)

    def submit(
        self,
        contributor: str,
        title: str,
        material_text: str,
        attachment_path: str | None = None,
        relates_to: str | None = None,
    ) -> Contribution:
        """Soumet une contribution externe en staging sans écriture directe dans le graphe."""
        ct_id = f"CT-{len(list(self.dir.glob('CT-*.json'))) + 1:04d}"
        c = Contribution(
            id=ct_id,
            engagement=self.engagement,
            contributor=contributor,
            title=title,
            material_text=material_text,
            attachment_path=attachment_path,
            relates_to_hint=relates_to,
            status="submitted",
        )
        self.save(c)
        return c

    def save(self, contribution: Contribution) -> None:
        """Persiste la contribution au format JSON."""
        path = self.dir / f"{contribution.id}.json"
        path.write_text(json.dumps(contribution.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")

    def get(self, ct_id: str) -> Contribution | None:
        """Charge une contribution par son ID."""
        path = self.dir / f"{ct_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return Contribution(**data)

    def list_all(self, status: str | None = None) -> list[Contribution]:
        """Liste les contributions, filtrées optionnellement par statut."""
        items = []
        for p in sorted(self.dir.glob("CT-*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            c = Contribution(**data)
            if not status or c.status == status:
                items.append(c)
        return items

    def triage(self, ct_id: str, lead_author: str, decision: str, reason: str = "", to_subject: str | None = None) -> Contribution:
        """Effectue le tri par l'architecte lead (accept, decline, redirect, to-knowledge-base)."""
        c = self.get(ct_id)
        if not c:
            raise FileNotFoundError(f"Contribution {ct_id} introuvable.")

        c.triage_decision = {
            "lead": lead_author,
            "decision": decision,
            "reason": reason,
            "target_subject": to_subject or c.relates_to_hint,
        }
        if decision == "accept":
            c.status = "triaged"
        elif decision == "decline":
            c.status = "declined"
        elif decision == "redirect":
            c.status = "redirected"
        elif decision == "to_knowledge_base":
            c.status = "kb_promoted"

        self.save(c)
        return c

    def crystallise(self, ct_id: str, db_path: str = "data/kuzu_db") -> Contribution:
        """Formule les énoncés candidats à partir du texte de matériel et cartographie le vocabulaire."""
        c = self.get(ct_id)
        if not c:
            raise FileNotFoundError(f"Contribution {ct_id} introuvable.")

        repo = ElicitationRepository(db_path=db_path)
        mapped, unmapped = map_material_vocabulary(c.material_text, repo=repo, engagement=self.engagement)

        c.mapped_subjects = mapped
        c.unmapped_terms = unmapped

        # Proposer un énoncé candidat pour chaque sujet cartographié
        st_list = []
        for subj in mapped or [c.relates_to_hint or "lmr-interworking"]:
            st_list.append({
                "engagement": self.engagement,
                "section": "4.5",
                "subject": subj,
                "predicate": "depends_on",
                "value": c.material_text.strip(),
                "author": c.contributor,
                "confidence": "observed",
                "verbatim": c.material_text.strip(),
            })

        c.proposed_statements = st_list
        c.status = "crystallised"
        self.save(c)
        return c

    def confirm_by_author(self, ct_id: str, author: str, accept: bool = True) -> Contribution:
        """Confirmation du SENS par l'auteur de la contribution."""
        c = self.get(ct_id)
        if not c:
            raise FileNotFoundError(f"Contribution {ct_id} introuvable.")

        if accept:
            c.status = "confirmed_by_author"
        else:
            c.status = "declined"

        self.save(c)
        return c

    def accept_by_lead(self, ct_id: str, lead_author: str, section_id: str = "4.5", db_path: str = "data/kuzu_db") -> tuple[Contribution, list[str]]:
        """Validation de l'ENTRÉE par l'architecte lead et persistance dans Kùzu DB."""
        c = self.get(ct_id)
        if not c:
            raise FileNotFoundError(f"Contribution {ct_id} introuvable.")

        if c.status != "confirmed_by_author":
            raise ValueError(f"La contribution {ct_id} doit d'abord être confirmée par son auteur (statut actuel: {c.status}).")

        repo = ElicitationRepository(db_path=db_path)
        persisted_ids = []

        for st_data in c.proposed_statements:
            st_data["section"] = section_id
            st_data["status"] = "active"
            st_id = repo.save_statement(st_data)
            persisted_ids.append(st_id)

        c.status = "accepted"
        self.save(c)
        return c, persisted_ids
