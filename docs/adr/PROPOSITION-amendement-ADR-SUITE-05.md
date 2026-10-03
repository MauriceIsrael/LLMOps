# Proposition d'amendement à ADR-SUITE-05 — le Hub porte aussi la base d'engagement

**Statut** : brouillon du propriétaire du Knowledge Hub, **à soumettre** aux propriétaires de la suite. Il ne modifie rien chez eux.
**Limite de lecture** : je n'ai lu `ADR-SUITE-05` que par ce qu'en rapportent `docs/knowledge-hub/` de Document Studio et le texte d'origine d'ADR-KH-01 (« miroir de ADR-SUITE-05 rév. 2 »). Les numéros de décision (D1, D4, D6) sont repris de ces citations ; **à vérifier contre le texte lui-même avant envoi**.

## Contexte
ADR-SUITE-05 pose que le Knowledge Hub est la mémoire d'ingénierie transverse, **pas un composant de la suite**, relié par canal à instantané scellé, jamais par RPC (amendement du 2026-09-13). Il y est dit que le Hub ne détient aucune décision ni exigence de programme, et que la décision d'un engagement vit chez son producteur (D4).

## Proposition
Le Hub contient deux bases isolées : la **base de connaissance** (générique, agnostique de programme, expérience d'experts sur un vertical) et la **base d'engagement** (exigences, décisions, énoncés, conflits, manques d'un programme). Archinex, outil de délibération des architectes, y écrit comme client interactif ; la suite ne le connaît pas. Le Hub devient l'**émetteur** d'une seconde famille de canaux à instantané scellé : l'engagement.

### Amendements demandés
1. **D1/D2** : « le Hub ne détient aucune donnée de programme » devient « la base de connaissance n'en détient aucune ; la base d'engagement en détient, sous les préalables de l'ADR-KH-01 A10-d ».
2. **D4** : préciser qui est le « producteur » d'un engagement délibéré hors suite : le Hub, comme système d'enregistrement ; le poste de délibération n'est pas un émetteur.
3. **Registre de canaux** : ajouter la famille « engagement » avec le Hub pour émetteur. Choisir : un canal unique ou un canal par nature d'objet (décisions, exigences, conflits, manques).
4. **Maintenir** : pas de RPC ; pas de prose de livrable côté Hub ; l'assistance de prose n'est pas un canal ; garde de classification en sortie (ADR-DE-43).

## Questions à trancher avec les propriétaires
- Les « décisions de programme » qu'Architecture Studio porte (si c'est bien le cas) sont-elles les mêmes objets que les décisions délibérées dans Archinex ? Sinon, deux natures de décision coexistent et le vocabulaire doit les distinguer.
- Une exigence d'appel d'offres du Hub et une exigence prise en charge par Requirements Intake / Tuleap : laquelle fait foi ? Lequel des deux alimente l'autre ? (Position actuelle du Hub, ADR-KH-01 A10-h : il garde les exigences de l'appel d'offres, qui servent à solliciter les architectes, jusqu'à clarification.)
- L'émetteur d'un canal doit-il être un composant de la suite pour figurer au registre ? (si oui, le Hub y entre comme émetteur sans y entrer comme composant : à confirmer.)
- Qui consomme l'instantané d'engagement : un adaptateur vers `ProjectedGraph` (LLMOps#40) ou directement un composant ?

## Conséquence si refus
Le repli est l'option A de `docs/SUITE-MAP.md` : l'engagement reste chez Archinex, qui émet lui-même le canal sous un nom neutre.
