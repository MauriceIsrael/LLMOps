# Proposition d'entrées du registre de canaux pour les canaux du Hub

> Préparation côté Hub, issue #154. **Rien n'est inscrit** : `contracts/channel-registry.json` est une copie identique dans les dépôts porteurs, et l'amendement du 2026-09-13 d'ADR-SUITE-05 écrit qu'il bouge « le jour où un canal est réellement branché,
> avec son témoin et son empreinte, et alors chez ses huit détenteurs à la fois ». Cette proposition dit à quoi ressembleraient les entrées, et **ce qui empêche de les inscrire aujourd'hui**.
> Relevé du 2026-10-24 : registre `contractVersion` 1.20, 16 canaux, aucun du Hub, aucune direction suite → Hub ; la liste `repositories` ne nomme pas le Hub.

## Format du registre (relevé sur `channel-registry.json`)

`id`, `emitter`, `consumers[]`, `payload`, `envelope`, `schemaVersion`, `witness {sha256, emitterPath, consumerPath, heldBy, regenerate, rebuiltByEmitterTest}` (ou `witness: null`), `notes`. Le numéro de contrat **appartient à l'émetteur** ;
l'empreinte du témoin est épinglée chez ses deux extrémités ; `consumers` est une liste.

## Les trois entrées possibles

Les chemins et empreintes sont ceux de ce dépôt au 2026-10-24 ; `null` = n'existe pas encore. Les empreintes changent à chaque régénération du témoin.

```json
[
  {
    "id": "engagement-snapshot",
    "emitter": "knowledge-hub",
    "consumers": [],
    "payload": "EngagementSnapshotData",
    "envelope": "ExternalSnapshotEnvelope",
    "schemaVersion": "1.8",
    "witness": {
      "sha256": "e4762a7c013da5cc31ee27727ae8ed73281b218d37165ced257cb29f7ef2f57a",
      "emitterPath": "schemas/examples/engagement_snapshot.example.json",
      "consumerPath": null,
      "heldBy": null,
      "regenerate": "poetry run python scripts/export_engagement_example.py",
      "rebuiltByEmitterTest": true
    },
    "notes": "À TRANCHER : aucun lecteur (SUITE-MAP §5.1, adaptateur A20 sans propriétaire). Le sceau change à chaque montée du contrat du Hub (`pins.contract_version`) : le témoin et son empreinte se régénèrent alors."
  },
  {
    "id": "conformity-snapshot-hub",
    "emitter": "knowledge-hub",
    "consumers": [
      "document-engine"
    ],
    "payload": "ConformityData",
    "envelope": "ExternalSnapshotEnvelope",
    "schemaVersion": "2.0",
    "witness": {
      "sha256": "c186cd20dd00e113e87387609a15cd5024d5e6b199e09570fd74fa2486b118fe",
      "emitterPath": "tests/fixtures/suite/conformity-snapshot.golden.json",
      "consumerPath": null,
      "heldBy": null,
      "regenerate": "CONFORMITY_WRITE_GOLDEN=1 poetry run pytest tests/contract/test_conformity_golden.py",
      "rebuiltByEmitterTest": true
    },
    "notes": "À TRANCHER : le lecteur du Document Engine refuse cette charge (provenance, version, ref, source de preuve : dossier d'admission, #152). Ne pas inscrire avant l'admission. Même contrat que `conformity-snapshot` (émis par conformity-engine, 4.0) : un contrat, N émetteurs (ADR-DE-41 §3), donc plutôt un second émetteur du canal existant qu'un nouveau canal."
  },
  {
    "id": "proposal-snapshot",
    "emitter": "requirements-intake | document-studio | architecture-studio (à désigner : un émetteur par entrée une fois réels)",
    "consumers": [
      "knowledge-hub"
    ],
    "payload": "ProposalSnapshotData",
    "envelope": "ExternalSnapshotEnvelope",
    "schemaVersion": "1.0",
    "witness": {
      "sha256": "85fb8653cc9ee79aa5b586b66758a9858ef7515a8a4e01f9ad28953a03664ea5",
      "emitterPath": null,
      "consumerPath": "schemas/examples/proposal_snapshot.example.json",
      "heldBy": "knowledge-hub",
      "regenerate": "poetry run python scripts/export_proposal_example.py",
      "rebuiltByEmitterTest": false
    },
    "notes": "À TRANCHER : aucun émetteur trouvé dans la suite. Le témoin est celui du LECTEUR (le Hub), pas d'un émetteur : `rebuiltByEmitterTest` est donc faux, à dire. Guide : docs/contracts/proposals-emitter-guide.md. Direction suite → Hub, que le registre n'a pas encore connue (ses consommateurs sont tous des composants de la suite)."
  }
]
```

## Ce qui empêche d'inscrire aujourd'hui

| Entrée | Obstacle |
|---|---|
| `engagement-snapshot` | **Aucun lecteur** : l'adaptateur vers le Document Engine (A20, #40) n'a pas de propriétaire. Un canal sans lecteur est « un témoin qui n'atteste rien » |
| `conformity-snapshot-hub` | Le lecteur du Document Engine **refuse** la charge (provenance, version, `ref`, source de preuve : `docs/plans/DOSSIER-ADMISSION-KH-ADR-DE-41.md`). Et ce serait un **second émetteur du canal existant** `conformity-snapshot` (un contrat, N émetteurs, ADR-DE-41 §3), pas un canal nouveau : le registre n'a qu'un champ `emitter` par canal |
| `proposal-snapshot` | **Aucun émetteur** trouvé dans la suite ; le témoin est celui du **lecteur** ; direction suite → Hub, que le registre n'a jamais portée |

## Questions à poser aux propriétaires (SUITE-MAP §5.4 et §6)

1. Le registre accepte-t-il un **émetteur qui n'est pas un composant de la suite** (le Hub, `repositories`) ? Si oui, `repositories` nomme-t-il le Hub, avec quelle clé ?
2. Un canal **peut-il avoir plusieurs émetteurs** (`emitter` est un singulier : le défaut que le passage de `consumer` à `consumers` a déjà corrigé pour les lecteurs) ?
3. Le registre accepte-t-il une direction **suite → Hub**, où le témoin est tenu par le lecteur ?
4. Un canal « engagement » est-il **un** canal ou **un par nature d'objet** (décisions, exigences, conflits, manques) ?

Coût d'une inscription : une modification identique dans huit dépôts, avec l'empreinte épinglée dans un test de chacun.
