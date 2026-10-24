# Note — ce qui circule vers le Hub quand le Document Engine demande de l'assistance de prose

> À joindre à la décision de suite sur l'assistance (ADR-SUITE-05, second amendement, D5 et D6) et à la revue de `document-engine#32`. Issue #156.
> Relevé du 2026-10-24 sur le code du Hub (`mcp_server/main.py`, `pipelines/prose_grounding.py`). La PR `document-engine#32` n'a pas été relue ici : ce qui est dit de
> ce que le Document Engine envoie vient de la revue de la suite du 2026-09-12 (`Document-studio`, `docs/REVUE-INTEGRATION-KNOWLEDGE-HUB-2026-09.md`).

## Ce que le Hub reçoit, lit, garde

| | |
|---|---|
| **Reçu** | tout ce que le client met dans le corps de `POST /api/prose/suggest-batch`. Selon la revue, le fournisseur de `document-engine#32` envoie le `ProseContext` complet (extraits du graphe projeté) |
| **Lu** | `blockId`, `instructions`, et les `context.anchoredItems[].attributes.label`. Rien d'autre. Ces libellés et la consigne forment la requête adressée à la base de connaissances |
| **Ignoré** | `anchorIds`, le reste du contexte, tout champ inconnu : vecteur de test `test_anchor_ids_and_the_rest_of_the_context_are_received_but_ignored` |
| **Écrit** | rien dans la base, rien dans un fichier. `basedOnModelHash` est calculé en mémoire |
| **Journalisé** | dans `mcp_server/main.py`, `pipelines/prose_grounding.py` et le calcul du contexte de doctrine, aucune écriture de journal du corps n'a été trouvée (recherche de `logging`, d'audit et d'écriture). Les journaux d'accès du serveur HTTP et de l'hébergeur n'ont pas été examinés : à vérifier pour le déploiement visé |
| **Rendu** | des extraits de doctrine déjà publiés par la base, jamais une phrase sur le projet ; **aucun brouillon** quand rien ne s'applique |

## Ce qui doit décider la suite

1. **Le Hub n'a besoin que des libellés et de la consigne.** Envoyer le `ProseContext` complet expose plus que nécessaire. Recommandation côté Hub : le fournisseur du Document Engine n'envoie que `blockId`, `instructions` et les libellés d'éléments ancrés.
2. **Quelle instance ?** Le jeton `demo-public-2026-08` de l'instance de démonstration est **public** (`docs/llmops-integration.md` d'Archinex, §4). Ne jamais y envoyer le contenu d'un dossier réel ; une instance locale ou privée, avec son propre jeton de service, est la seule cible acceptable pour un projet.
3. **Authentification** : jeton de service (`Authorization: Bearer`), jamais l'identité d'un expert.
4. **Pas un canal** : aucun instantané, aucune empreinte à vérifier côté Document Engine ; la sortie est une **suggestion** qu'un humain accepte (ADR-DE-02), qui n'entre jamais comme fait ni comme citation (D6).

## Priorité de fournisseur (côté Document Engine, hors Hub)

La revue relève une priorité silencieuse Hub > Anthropic quand les deux sont configurés. C'est une décision de configuration du Document Engine, pas du Hub : à demander par issue jumelle (voir l'issue #156).
