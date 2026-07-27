"""Protecteur de vocabulaire canonique évitant la pollution du graphe par les contributions externes."""


from tools.elicitation.repository import ElicitationRepository


def map_material_vocabulary(
    material_text: str, repo: ElicitationRepository, engagement: str = "nordwave-mcx-2027"
) -> tuple[list[str], list[str]]:
    """Cartographie les termes du matériel externe sur les sujets canoniques existants.

    Retourne:
      (mapped_subjects, unmapped_terms)
    """
    board = repo.get_subjects_maturity_board(engagement)
    existing_subjects = {b["subject"] for b in board}

    mapped = []
    unmapped = []

    # Cartographie de synonymes courants
    synonyms = {
        "interworking gateway": "lmr-interworking",
        "the EMS": "ericsson-enm",
        "mobile core": "mobile-core",
        "floor control": "floor-control",
        "media distribution": "media-distribution",
        "group management": "group-management",
    }

    text_lower = material_text.lower()

    for term, canon in synonyms.items():
        if term in text_lower:
            if canon in existing_subjects or canon == "ericsson-enm":
                mapped.append(canon)

    for subj in existing_subjects:
        if subj.lower() in text_lower or subj.replace("-", " ") in text_lower:
            if subj not in mapped:
                mapped.append(subj)

    # Détecter d'éventuels termes candidats non cartographiés (ex: profile store)
    known_candidates = ["profile store", "custom gateway", "vendor extension"]
    for candidate in known_candidates:
        if candidate in text_lower and candidate not in mapped:
            unmapped.append(candidate)

    return list(set(mapped)), list(set(unmapped))
