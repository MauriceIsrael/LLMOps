"""Templates de questions par niveau de maturité et validation stricte du contrat de portée (forbids)."""

import re
from typing import Any

QUESTION_TEMPLATES: dict[str, dict[str, Any]] = {
    "L1_framing": {
        "scope": "the purpose, the boundary, and what must hold",
        "forbids": ["mechanism", "technology", "number"],
        "shape": "prose",
        "example": "What is {subject} for, and what must keep working when everything else degrades?",
    },
    "L2_decomposition": {
        "scope": "the parts, and nothing about how any part works",
        "forbids": ["mechanism_for_part", "technology", "number"],
        "shape": "list_of_parts",
        "example": "What parts does {subject} break into, and which of them carries the risk?",
    },
    "L3_decision": {
        "scope": "the mechanism for one named part, and the alternatives rejected",
        "forbids": ["threshold", "sizing_value"],
        "requires": ["one_part_named"],
        "shape": "decision_with_alternatives",
        "example": "For {part}, which mechanism, and what did you rule out?",
    },
    "L4_specification": {
        "scope": "a value, its unit, and the condition under which it holds",
        "requires": ["one_decided_mechanism_named"],
        "shape": "value_with_unit_and_condition",
        "example": "For {part} under {mechanism}, what is the {parameter}, at which percentile and under what load?",
    },
}

# Technologies, mécanismes ou termes interdits dans L1/L2
FORBIDDEN_TECH_TERMS = [
    r"\b5QI\b",
    r"\bSGi-LAN\b",
    r"\bgNodeB\b",
    r"\beNodeB\b",
    r"\bSCTP\b",
    r"\bIPSec\b",
    r"\bMPLS\b",
    r"\bmultihoming\b",
]

# Chiffres et seuils numériques (ex: 100 ms, 50 Mbps, p95, 200 concurrent)
FORBIDDEN_NUMERIC_PATTERNS = [
    r"\b\d+\s*(ms|s|Mbps|Gbps|kbps|MB|GB|%|p\d+)\b",
    r"\b\d+\s+(concurrent|users|talkgroups|channels)\b",
]


def validate_question_scope(question_text: str, level: str) -> tuple[bool, str]:
    """Vérifie si le texte d'une question respecte le contrat de portée (forbids) du niveau."""
    template = QUESTION_TEMPLATES.get(level)
    if not template:
        return True, ""

    forbids = template.get("forbids", [])

    # Validation pour L1_framing et L2_decomposition
    if "technology" in forbids or "mechanism" in forbids or "mechanism_for_part" in forbids:
        for pattern in FORBIDDEN_TECH_TERMS:
            if re.search(pattern, question_text, re.IGNORECASE):
                return (
                    False,
                    f"Violates {level} scope contract: question contains forbidden technology term matching '{pattern}'.",
                )

    if "number" in forbids or "threshold" in forbids or "sizing_value" in forbids:
        for pattern in FORBIDDEN_NUMERIC_PATTERNS:
            if re.search(pattern, question_text, re.IGNORECASE):
                return (
                    False,
                    f"Violates {level} scope contract: question contains forbidden numerical threshold matching '{pattern}'.",
                )

    return True, ""
