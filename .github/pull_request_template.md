<!--
TITRE : type(portée) [contrat …] : résumé court

  [contrat → 1.36]            la PR CRÉE ce contrat (numéro pris à l'ouverture, voir ci-dessous)
  [contrat → 1.36 · inst. 1.9] idem, avec la nouvelle version de l'instantané d'engagement scellé quand elle change
  [contrat —]                 aucun nouveau contrat (correctif, tests, documentation, outillage)

Exemples : « feat(engagement) [contrat → 1.36 · inst. 1.9] : … »
           « test(base) [contrat —] : borner ladybug et rendre la suite reproductible »

LE NUMÉRO SE PREND À L'OUVERTURE, pas à l'écriture. Plusieurs lots avancent en parallèle et se croisent : une PR a vu son
numéro pris trois fois de suite (1.33, 1.34, 1.35), avec renumérotation, conflits et suite relancée à chaque fois. Avant de
l'écrire : relire CONTRACT_VERSION de `main` ET lister les PR ouvertes qui annoncent un contrat ; s'il est réservé, prendre le
suivant et le dire. Après tout merge de `main` dans la branche, relire le numéro.

Supprimer ce commentaire avant de publier.
-->

## Contrat

| | |
|---|---|
| Contrat créé | 1.__ (`mcp_server/core/version.py`) / aucun |
| Instantané d'engagement (`schemaVersion`) | inchangé / 1.__ |
| Routes | ajoutées : … / modifiées : … / aucune |
| Clients touchés (Archinex, suite) | aucun / lecteur tolérant vérifié / à adapter : … |
| Numéro relu sur `main` et les PR ouvertes le | … |

## Contexte

<!-- Pourquoi cette PR : le constat, avec la preuve (échec, log, issue). Un faux problème ne se corrige pas. -->

## Ce qui change

<!-- Par grands blocs. Signaler ce qui change des sceaux ou des sorties existantes, même « pour le mieux ». -->

## Vérification

- [ ] **Suite complète en copie neuve**, dépendances du lock (`make test-all` ou `make test-docker`, `docs/TESTING.md`) : _N tests, N échecs, N ignorés_
- [ ] Un échec isolé est **rejoué seul** avant d'être qualifié d'instable, et décrit tel quel (jamais arrondi)
- [ ] Contrat changé : `version.py`, `docs/VERSIONING.md`, `docs/contracts/knowledge-hub-api-v1.md` (§5.N) à jour
- [ ] Contrat changé : fixtures régénérées **depuis une copie neuve** (`docs/TESTING.md`, « Quand on change quelque chose »), seul `knowledge_snapshot.json` attendu
- [ ] Schéma d'instantané changé : exemple (`scripts/export_engagement_example.py`) et types (`scripts/generate_schemas.py`) régénérés, tests de version mis à jour
- [ ] Aucun fichier `data/**/*.lbug` committé
- [ ] Mise à jour depuis `main` faite, numéro de contrat relu, tests relancés **après** cette mise à jour
- [ ] Client concerné (Archinex) rejoué contre ce Hub si le format d'un instantané change (`docs/testing.md` d'Archinex)

## Limites (dites, pas masquées)

<!-- Ce qui n'est pas fait, pas mesuré, pas éprouvé ; ce qui dépend d'une autre PR ou d'une décision. Pas de CI sur ce dépôt : le dire si rien n'a tourné ailleurs que chez l'auteur. -->

## À décider

<!-- Points qui reviennent à la personne qui relit. N'écrire « closes #N » que si l'issue est vraiment soldée. -->
