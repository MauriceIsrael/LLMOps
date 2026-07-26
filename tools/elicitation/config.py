"""Configuration et vocabulaire contrôlé pour le prototype d'élicitation."""


# Liste strictement contrôlée des prédicats autorisés dans le domaine
ALLOWED_PREDICATES: set[str] = {
    "has_property",
    "is_constrained_by",
    "has_value",
    "depends_on",
    "is_excluded_because",
    "has_effort",
    "has_authority_level",
}

# Formes de réponses attendues pour les questions
EXPECTED_SHAPES: set[str] = {
    "boolean",
    "number",
    "enum",
    "free_text",
    "decision",
}

# Statuts autorisés des questions
QUESTION_STATUSES: set[str] = {
    "open",
    "sent",
    "answered",
    "confirmed",
    "declined",
    "rerouted",
}

# Statuts autorisés des énoncés
STATEMENT_STATUSES: set[str] = {
    "proposed",
    "active",
    "superseded",
    "withdrawn",
}

# Statuts de confiance des énoncés (discipline TPL-authoring)
CONFIDENCE_LEVELS: set[str] = {
    "verified",
    "designed",
    "vendor-stated",
    "assumed",
}

# Types de manques déterministes (Gaps)
GAP_TYPES: set[str] = {
    "G1_empty_section",
    "G2_unanswered_blocking",
    "G3_principle_unaddressed",
}

# Types de conflits déterministes
CONFLICT_KINDS: set[str] = {
    "contradiction",
    "principle_violation",
    "stale_basis",
}
