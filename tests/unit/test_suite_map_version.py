"""#159: ``docs/SUITE-MAP.md`` annonce le contrat qu'il décrit ; il ne peut plus rester sur un numéro que le code a dépassé."""

import re
from pathlib import Path

from mcp_server.core.version import CONTRACT_VERSION

TEXT = (Path(__file__).resolve().parents[2] / "docs" / "SUITE-MAP.md").read_text(encoding="utf-8")


def test_the_suite_map_describes_the_contract_of_the_code():
    declared = re.search(r"^Contrat décrit : \*\*(\d+\.\d+)\*\*", TEXT, re.MULTILINE)
    assert declared, "SUITE-MAP.md doit commencer par « Contrat décrit : **x.y** »"
    assert declared.group(1) == CONTRACT_VERSION, (
        f"SUITE-MAP.md décrit le contrat {declared.group(1)}, le code est à {CONTRACT_VERSION} : relire le document "
        "(§3 et §5), puis mettre à jour « Contrat décrit » et l'historique des révisions"
    )


def test_the_last_review_is_dated_and_listed_in_the_history():
    review = re.search(r"Dernière relecture : \*\*(\d+ \w+ \d{4})\*\*", TEXT)
    assert review, "« Dernière relecture : **jj mois aaaa** » est requis"
    assert f"| {CONTRACT_VERSION} |" in TEXT.split("## Historique des révisions", 1)[-1], (
        "l'historique des révisions ne mentionne pas le contrat courant"
    )
