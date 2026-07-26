"""Parser déterministe pour le protocole de commandes dans les commentaires d'experts."""

import re
from dataclasses import dataclass


@dataclass
class ParsedCommand:
    """Structure d'une commande d'expert analysée."""

    name: str  # answer | confirm | edit | reject | contest | reroute | decline | arbitrate
    target_id: str | None = None
    reason: str | None = None
    keep_statement_id: str | None = None
    text_payload: str = ""
    raw_verbatim: str = ""
    is_valid: bool = True
    error_message: str | None = None


class CommandParser:
    """Parseur déterministe s'assurant que la commande est la 1ère ligne non-vide."""

    @staticmethod
    def parse_comment(comment_text: str) -> ParsedCommand | None:
        """Analyse le texte d'un commentaire. Reçoit le texte brut complet."""
        if not comment_text or not comment_text.strip():
            return None

        lines = comment_text.strip().splitlines()
        first_non_empty_idx = -1
        for idx, line in enumerate(lines):
            if line.strip():
                first_non_empty_idx = idx
                break

        if first_non_empty_idx == -1:
            return None

        first_line = lines[first_non_empty_idx].strip()

        # Vérifier si la première ligne non-vide commence par un /
        if not first_line.startswith("/"):
            return None

        # Conserver le reste des lignes comme verbatim multi-lignes
        verbatim_lines = lines[first_non_empty_idx:]
        full_verbatim = "\n".join(verbatim_lines)

        # Tokenizer la première ligne
        tokens = first_line.split()
        cmd_name = tokens[0][1:].lower()  # Enlever le / initial

        if cmd_name == "answer":
            # Ex: /answer Q-0001 --text "..." ou /answer Text libre...
            target_id = tokens[1] if len(tokens) > 1 and tokens[1].startswith("Q-") else None
            rest_idx = 2 if target_id else 1
            payload = " ".join(tokens[rest_idx:]).replace("--text", "").strip(' "')
            return ParsedCommand(
                name="answer",
                target_id=target_id,
                text_payload=payload if payload else full_verbatim,
                raw_verbatim=full_verbatim,
            )

        elif cmd_name == "confirm":
            # Ex: /confirm Q-0001
            target_id = tokens[1] if len(tokens) > 1 else None
            return ParsedCommand(
                name="confirm",
                target_id=target_id,
                raw_verbatim=full_verbatim,
            )

        elif cmd_name == "edit":
            # Ex: /edit Q-0001
            target_id = tokens[1] if len(tokens) > 1 else None
            return ParsedCommand(
                name="edit",
                target_id=target_id,
                raw_verbatim=full_verbatim,
            )

        elif cmd_name == "reject":
            # Ex: /reject Q-0001 Raison du rejet...
            target_id = tokens[1] if len(tokens) > 1 and tokens[1].startswith("Q-") else None
            reason = " ".join(tokens[2:]) if target_id else " ".join(tokens[1:])
            return ParsedCommand(
                name="reject",
                target_id=target_id,
                reason=reason if reason else "Rejet par l'expert",
                raw_verbatim=full_verbatim,
            )

        elif cmd_name == "arbitrate":
            # Ex: /arbitrate keep S-0001 --reason "..."
            if "--reason" not in first_line:
                return ParsedCommand(
                    name="arbitrate",
                    is_valid=False,
                    error_message="Commande /arbitrate refusée : le paramètre obligatoire --reason est manquant.",
                )

            match = re.search(r"/arbitrate\s+keep\s+(\S+)\s+--reason\s+[\"']?(.*?)[\"']?$", first_line)
            if match:
                keep_id = match.group(1)
                reason_text = match.group(2)
                return ParsedCommand(
                    name="arbitrate",
                    keep_statement_id=keep_id,
                    reason=reason_text,
                    raw_verbatim=full_verbatim,
                )
            else:
                return ParsedCommand(
                    name="arbitrate",
                    is_valid=False,
                    error_message="Format invalide pour /arbitrate. Utilisation : /arbitrate keep <statement_id> --reason \"...\"",
                )

        elif cmd_name == "contest":
            # Ex: /contest S-0001 Énoncé alternatif...
            target_id = tokens[1] if len(tokens) > 1 else None
            payload = " ".join(tokens[2:])
            return ParsedCommand(
                name="contest",
                target_id=target_id,
                text_payload=payload,
                raw_verbatim=full_verbatim,
            )

        elif cmd_name == "reroute":
            # Ex: /reroute cloud-architect Raison...
            target_role = tokens[1] if len(tokens) > 1 else "cloud-architect"
            reason = " ".join(tokens[2:])
            return ParsedCommand(
                name="reroute",
                text_payload=target_role,
                reason=reason,
                raw_verbatim=full_verbatim,
            )

        elif cmd_name == "decline":
            # Ex: /decline Raison de l'inconnu...
            reason = " ".join(tokens[1:])
            return ParsedCommand(
                name="decline",
                reason=reason,
                raw_verbatim=full_verbatim,
            )

        return None
