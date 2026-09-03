"""Annuaire des identités, gestion des rôles et des compétences (Roster Manager)."""

from pathlib import Path
from typing import Any

import yaml


class RosterManager:
    """Gestionnaire des identités, autorisations et compétences techniques depuis roster.yaml."""

    def __init__(self, engagement: str = "demo-2026", roster_path: str | Path | None = None) -> None:
        self.engagement = engagement
        if roster_path:
            self.roster_path = Path(roster_path)
        else:
            p_path = Path("projects") / engagement / "roster.yaml"
            a_path = Path("artifacts") / engagement / "roster.yaml"
            self.roster_path = p_path if p_path.exists() else (a_path if a_path.exists() else p_path)

        self.users: dict[str, dict[str, Any]] = {}
        self.external_contractors: list[dict[str, Any]] = []
        self.load_roster()

    def load_roster(self) -> None:
        """Charge la cartographie login -> roles et skills depuis roster.yaml."""
        if self.roster_path.exists():
            try:
                data = yaml.safe_load(self.roster_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for entry in data:
                        login = entry.get("login")
                        if login:
                            skills_raw = entry.get("skills", [])
                            # Normalise skills to list of skill IDs
                            normalized_skills = []
                            for s in skills_raw:
                                if isinstance(s, dict):
                                    normalized_skills.append(s.get("id"))
                                elif isinstance(s, str):
                                    normalized_skills.append(s)
                            self.users[login] = {
                                "name": entry.get("name", login),
                                "roles": entry.get("roles", []),
                                "skills": [s for s in normalized_skills if s],
                                "skills_details": skills_raw,
                            }
                elif isinstance(data, dict):
                    # Structure enrichie avec personnel et external_contractors
                    for entry in data.get("members", []):
                        login = entry.get("login")
                        if login:
                            skills_raw = entry.get("skills", [])
                            normalized_skills = [s.get("id") if isinstance(s, dict) else s for s in skills_raw]
                            self.users[login] = {
                                "name": entry.get("name", login),
                                "roles": entry.get("roles", []),
                                "skills": [s for s in normalized_skills if s],
                                "skills_details": skills_raw,
                            }
                    self.external_contractors = data.get("external_contractors", [])
            except Exception:
                pass

        # Fallbacks par défaut pour démo / tests si non renseignés
        if "alice" not in self.users:
            self.users["alice"] = {
                "name": "Alice",
                "roles": ["cloud-architect"],
                "skills": ["SKL-KUBE-TELCO", "SKL-AUTO-GITOPS"],
                "skills_details": ["SKL-KUBE-TELCO", "SKL-AUTO-GITOPS"],
            }
        if "alice-gh" not in self.users:
            self.users["alice-gh"] = {
                "name": "Alice",
                "roles": ["cloud-architect"],
                "skills": ["SKL-KUBE-TELCO", "SKL-AUTO-GITOPS"],
                "skills_details": ["SKL-KUBE-TELCO", "SKL-AUTO-GITOPS"],
            }
        if "bob" not in self.users:
            self.users["bob"] = {
                "name": "Bob",
                "roles": ["storage-expert", "network-architect", "security-architect"],
                "skills": ["SKL-NET-UNDERLAY", "SKL-SEC-ZEROTRUST", "SKL-OBS-SOC"],
                "skills_details": ["SKL-NET-UNDERLAY", "SKL-SEC-ZEROTRUST", "SKL-OBS-SOC"],
            }
        if "charlie" not in self.users:
            self.users["charlie"] = {
                "name": "Charlie",
                "roles": ["chief-architect", "network-architect"],
                "skills": ["SKL-TELCO-CORE", "SKL-RESIL-DR"],
                "skills_details": ["SKL-TELCO-CORE", "SKL-RESIL-DR"],
            }
        if "charlie-gh" not in self.users:
            self.users["charlie-gh"] = {
                "name": "Charlie",
                "roles": ["chief-architect", "network-architect"],
                "skills": ["SKL-TELCO-CORE", "SKL-RESIL-DR"],
                "skills_details": ["SKL-TELCO-CORE", "SKL-RESIL-DR"],
            }

    def get_roles(self, login: str) -> list[str]:
        """Retourne la liste des rôles associés à un identifiant utilisateur."""
        user = self.users.get(login)
        return user["roles"] if user else []

    def get_skills(self, login: str) -> list[str]:
        """Retourne la liste des compétences (IDs) d'un utilisateur."""
        user = self.users.get(login)
        return user.get("skills", []) if user else []

    def get_all_covered_skills(self) -> set[str]:
        """Retourne l'ensemble des compétences couvertes par l'équipe et les prestataires externes."""
        covered = set()
        for u in self.users.values():
            covered.update(u.get("skills", []))
        for c in self.external_contractors:
            skill = c.get("skill")
            if skill:
                covered.add(skill)
        return covered

    def check_permission(self, login: str, required_role: str) -> tuple[bool, str | None]:
        """Vérifie si l'utilisateur possède le rôle requis et renvoie un message de refus au besoin."""
        roles = self.get_roles(login)
        if not roles:
            return (
                False,
                f"❌ Compte non reconnu : `{login}` n'est pas enregistré dans le roster du projet `{self.engagement}`. Veuillez demander votre ajout dans `roster.yaml`.",
            )

        if required_role not in roles and "chief-architect" not in roles:
            return (
                False,
                f"❌ Commande refusée : L'exécutant `{login}` ne possède pas le rôle requis `{required_role}` (Rôles actuels : {roles}).",
            )

        return (True, None)

    def add_skill(
        self,
        login: str,
        skill_id: str,
        level: str = "senior",
        evidence: str | None = None,
        certified: bool = False,
    ) -> bool:
        """Ajoute une compétence à un collaborateur existant."""
        if login not in self.users:
            return False
        user = self.users[login]
        if skill_id not in user["skills"]:
            user["skills"].append(skill_id)
            user.setdefault("skills_details", []).append({
                "id": skill_id,
                "level": level,
                "evidence": evidence or "Auto-declared via CLI",
                "certified": certified,
            })
            self.save_roster()
            return True
        return False

    def assign_user(
        self,
        login: str,
        name: str | None = None,
        roles: list[str] | None = None,
        skills: list[str] | None = None,
    ) -> None:
        """Affecte un nouveau collaborateur au projet avec ses rôles et compétences."""
        clean_skills = skills or []
        self.users[login] = {
            "name": name or login,
            "roles": roles or ["architect"],
            "skills": clean_skills,
            "skills_details": [{"id": s, "level": "senior"} for s in clean_skills],
        }
        self.save_roster()

    def contract_expertise(
        self,
        skill_id: str,
        provider: str,
        ref: str,
    ) -> None:
        """Enregistre le recours à une assistance technique / prestation d'expertise externe."""
        self.external_contractors.append({
            "skill": skill_id,
            "provider": provider,
            "ref": ref,
        })
        self.save_roster()

    def save_roster(self) -> None:
        """Persiste l'état actuel dans le fichier YAML du roster."""
        self.roster_path.parent.mkdir(parents=True, exist_ok=True)
        members = []
        for login, data in self.users.items():
            members.append({
                "login": login,
                "name": data.get("name", login),
                "roles": data.get("roles", []),
                "skills": data.get("skills_details", data.get("skills", [])),
            })
        payload: Any = members
        if self.external_contractors:
            payload = {
                "members": members,
                "external_contractors": self.external_contractors,
            }
        self.roster_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
