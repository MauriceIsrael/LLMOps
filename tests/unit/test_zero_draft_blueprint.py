"""Tests unitaires pour la génération Blueprint + ProseStore conforme à document-engine."""

from tools.elicitation.zero_draft import ZeroDraftAssembler


def test_zero_draft_blueprint_structure():
    assembler = ZeroDraftAssembler()
    res = assembler.to_blueprint_and_prose(
        engagement="default",
        project_title="Test Project 5G",
        client_name="Client Test",
    )

    assert res["engagement"] == "default"
    assert res["project_title"] == "Test Project 5G"
    assert res["client_name"] == "Client Test"

    blueprint = res["blueprint"]
    assert blueprint["version"] == "1.0"
    assert blueprint["documentType"] == "hld"
    assert "sections" in blueprint
    assert len(blueprint["sections"]) == 5

    # Vérification des sections et blocs prose
    for sec in blueprint["sections"]:
        assert "id" in sec
        assert "title" in sec
        assert "blocks" in sec
        for blk in sec["blocks"]:
            assert blk["type"] == "prose"
            assert len(blk["anchorIds"]) > 0

    # Vérification du ProseStore
    prose_store = res["prose_store"]
    assert "contexte-projet" in prose_store
    assert "perimetre-exigences" in prose_store
    assert "securite-souverainete" in prose_store

    entry = prose_store["contexte-projet"]
    assert "content" in entry
    assert "anchoredOn" in entry
    assert "lastModelHashSeen" in entry
    assert "Test Project 5G" in entry["content"]
