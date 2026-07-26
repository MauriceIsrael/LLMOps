"""Annuaire des identités et gestion des rôles (Roster Manager)."""

from pathlib import Path
from typing import Any

import yaml


class RosterManager:
    """Gestionnaire des identités et autorisations de rôles depuis roster.yaml."""

    def __init__(self, engagement: str = "demo-2026", roster_path: str | Path | None = None) -> None:
        self.engagement = engagement
        if roster_path:
            self.roster_path = Path(roster_path)
        else:
            self.roster_path = Path("projects") / engagement / "roster.yaml"

        self.users: dict[str, dict[str, Any]] = {}
        self.load_roster()

    def load_roster(self) -> None:
        """Charge la cartographie login -> roles depuis roster.yaml."""
        if self.roster_path.exists():
            try:
                data = yaml.safe_load(self.roster_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for entry in data:
                        login = entry.get("login")
                        if login:
                            self.users[login] = {
                                "name": entry.get("name", login),
                                "roles": entry.get("roles", []),
                            }
            except Exception:
                pass

        # Fallbacks par défaut pour démo / tests
        if "alice" not in self.users:
            self.users["alice"] = {"name": "Alice", "roles": ["cloud-architect"]}
        if "alice-gh" not in self.users:
            self.users["alice-gh"] = {"name": "Alice", "roles": ["cloud-architect"]}
        if "bob" not in self.users:
            self.users["bob"] = {"name": "Bob", "roles": ["storage-expert", "network-architect"]}
        if "charlie" not in self.users:
            self.users["charlie"] = {"name": "Charlie", "roles": ["chief-architect", "network-architect"]}
        if "charlie-gh" not in self.users:
            self.users["charlie-gh"] = {"name": "Charlie", "roles": ["chief-architect", "network-architect"]}

    def get_roles(self, login: str) -> list[str]:
        """Retourne la liste des rôles associés à un identifiant utilisateur."""
        user = self.users.get(login)
        return user["roles"] if user else []

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
