# Plan d'implémentation — Gouvernance de la base de connaissance depuis Archinex

> Destinataires : agents de codage IA travaillant dans `MauriceIsrael/LLMOps` (lots **L5 à L9**) et dans `MauriceIsrael/archinex` (lots **A6 à A11**).
> Plans compagnons : `PLAN-IMPLEMENTATION-LLMOps.md` (lots L0 à L4) et `PLAN-IMPLEMENTATION-Archinex.md` (lots A0 à A5).
> Date de référence : 30/09/2026.

---

## 0. À lire avant toute ligne de code

### 0.1 Objectif

Les experts **n'utilisent plus de ligne de commande ni de fichier** pour enrichir la base de connaissance (KB). Tout se fait dans Archinex :

- création des comptes et attribution des rôles KB (relecteur d'un domaine, mainteneur, évaluateur) ;
- sollicitation des experts : boîte de revue personnelle, assignation, relances, campagnes d'enrichissement ;
- relecture des candidats (accepter, amender, rejeter, seconde revue) ;
- évaluations : validation du jeu d'évaluation du juge, retours des débats sur les verdicts de `check_option` ;
- élargissement de la doctrine : création et amendement d'actifs, écriture et test des clauses `checks`, ingestion des référentiels, déclaration de couverture ;
- promotion et publication, déclenchées par un mainteneur depuis l'interface.

### 0.2 Pourquoi le plan Archinex actuel ne suffit pas

| Besoin | Couvert aujourd'hui ? | Manque |
|---|---|---|
| Soumettre des candidats depuis un arbitrage | Oui (A5) | — |
| Voir le statut de ses candidats | Oui (A5) | — |
| Relire les candidats | **Non** | La revue n'existe que dans `apps/kb-client-app`, derrière un jeton partagé `LLMOPS_REVIEW_TOKEN`. LLMOps ne sait pas **qui** relit : le `reviewer` est déclaré dans le corps de la requête. |
| Comptes et jetons experts | **Non** | Les relecteurs sont des jetons statiques dans `ENGAGEMENT_TOKENS` (variable d'environnement) ; les propriétaires de domaine sont un fichier `data/kb/owners.yaml`. |
| Solliciter un expert | **Non** | LLMOps notifie par Discord, ntfy ou e-mail un *handle* ; aucune boîte de revue, aucune réassignation, aucune campagne. Le plan A5 interdit à Archinex de notifier. |
| Évaluations | **Non** | Annotations du jeu d'évaluation dans un fichier JSONL, `make eval-check` en CLI ; les contestations de verdicts dans les débats Archinex ne remontent pas. |
| Élargir la doctrine | **Partiel** | Création d'actif possible via `POST /api/knowledge/candidates`, mais sans formulaire guidé ; clauses `checks` sans simulation ; ingestion de référentiel uniquement en CLI (`kb ingest-framework`, feuille CSV). |
| Promouvoir et publier | **Non** | `kb promote` / `kb publish` en CLI, écriture dans `data/kb/` et commit git manuel. Sur Cloud Run, le disque est éphémère : la file de candidats et les écritures dans `data/kb/` sont perdues au redémarrage. |

### 0.3 Répartition des responsabilités (règle directrice)

| Archinex | LLMOps |
|---|---|
| **Identité** des personnes (comptes, invitations, rôles), interface, sollicitation (boîte de revue, notifications in-app et e-mail, campagnes), LLM local pour les **propositions** (`llm-derived`) | **Règles déterministes** : contrôles, autorisation fine (qui peut relire quel domaine), routage vers le propriétaire, confiance, couverture, publication. Aucun LLM sur une route servie. |
| Décide **comment** joindre un expert | Décide **qui** doit agir (propriétaire, second relecteur) et le trace |
| Ne stocke aucune doctrine | Seule source de la doctrine, des candidats, des évaluations et des manifestes |

Conséquences :

- La règle A5 « Archinex ne notifie personne » est remplacée ainsi : **LLMOps désigne le destinataire et émet un événement ; Archinex délivre la notification à ses utilisateurs.** Les canaux Discord, ntfy et e-mail de LLMOps restent un repli pour les handles sans compte Archinex.
- L'écran `/governance/candidates` de `apps/kb-client-app` passe en **console de secours du mainteneur**, sans évolution (voir D4).

### 0.4 Règles non négociables (en plus de celles des plans compagnons)

1. **Compatibilité ascendante** : les interfaces LLMOps 1.0 à 1.3 sont gelées (`tests/contract/frozen/`). Tout ajout est optionnel ; le contrat passe en 1.4, 1.5…
2. **Aucune autorité déclarative** : un relecteur, un évaluateur ou un mainteneur est identifié par une **assertion signée** (§3.1), jamais par un champ du corps de la requête. Le champ `reviewer` de `PATCH /api/knowledge/candidates/{id}` reste accepté pour les clients existants, mais il est ignoré (et doit correspondre, sinon 403) dès qu'une assertion est présente.
3. **Rien de `llm-derived` ne devient doctrine sans action humaine tracée** (auteur, rôle, date) ; un actif n'est jamais `active` ni `verified` sans revue.
4. **Chaque action d'expert est un événement** (Archinex : `DomainEvent` ; LLMOps : `history` du candidat ou journal de gouvernance), en ajout seul.
5. **Aucun secret dans le navigateur** : le jeton de service Archinex → LLMOps et la clé de signature restent côté serveur.

---

## 1. Décisions à prendre avant de coder

Chaque décision a une recommandation. Le mainteneur valide ou corrige, puis la décision est consignée dans `docs/decisions/` (LLMOps) et `openspec/changes/<lot>/design.md` (Archinex).

| # | Question | Recommandation | Alternative |
|---|---|---|---|
| **D1** | Où persister l'état de gouvernance LLMOps (candidats, propriétaires, évaluations, ingestions, journal) ? | **PostgreSQL** (Cloud SQL en production, SQLite en dev) via SQLAlchemy + Alembic, derrière l'interface `CandidateRepository` existante. Le backend `file` reste pour le dev et les tests. | Volume persistant monté sur Cloud Run + fichiers JSON (plus simple, moins robuste en concurrence). |
| **D2** | Comment publier la doctrine depuis un serveur au disque éphémère ? | **Publication par pull request git** : `kb promote` / `kb publish` côté serveur ouvrent une branche et une PR sur le dépôt de la KB via une GitHub App ; la fusion déclenche la reconstruction (`cloudbuild.yaml`) et le nouvel instantané scellé. Git reste la source de vérité et la trace d'audit. | Écriture sur un volume persistant + synchronisation git périodique (risque de divergence). |
| **D3** | Comment LLMOps connaît-il l'identité d'un expert ? | **Assertion d'acteur signée par Archinex** (JWT court, EdDSA, clé publique publiée par Archinex et configurée dans LLMOps), transmise avec le jeton de service Archinex. | Un jeton LLMOps par expert, géré par une API d'administration (plus de secrets à distribuer, révocation plus lourde). |
| **D4** | Que devient l'écran de revue de `apps/kb-client-app` ? | **Console de secours du mainteneur**, gelée. Toute nouvelle fonction de gouvernance se fait dans Archinex. | Le supprimer après A7. |
| **D5** | Qui fait autorité sur la liste des propriétaires de domaine ? | **LLMOps** (table `domain_owners`, amorcée depuis `data/kb/owners.yaml`, modifiable par un `kb:admin` via Archinex, chaque changement journalisé). Archinex ne fait que lier un compte à un handle. | Archinex (mais alors LLMOps dépend d'Archinex pour router les candidats venant d'autres systèmes). |

---

## 2. Vue d'ensemble des lots

| Lot | Dépôt | Titre | Dépend de |
|---|---|---|---|
| **L5** | LLMOps | Identité déléguée et état de gouvernance persistant | L3, D1, D3, D5 |
| **L6** | LLMOps | API de revue et de sollicitation (boîte, assignation, événements, propriétaires) | L5 |
| **L7** | LLMOps | Atelier de doctrine et évaluations (modèles d'actifs, simulation de clauses, jeu d'évaluation, retours de verdicts) | L5 |
| **L8** | LLMOps | Ingestion des référentiels par API (téléversement, feuille de revue en ligne, déclaration de couverture) | L5, L6 |
| **L9** | LLMOps | Promotion et publication serveur par PR git, métriques de santé | L6, D2 |
| **A6** | Archinex | Comptes, rôles KB et assertion d'acteur | A1, L5 |
| **A7** | Archinex | Boîte de revue et sollicitation des experts | A6, L6 |
| **A8** | Archinex | Atelier de doctrine (création, amendement, clauses) | A7, L7 |
| **A9** | Archinex | Évaluations (jeu d'évaluation, retours des débats) | A3, A8, L7 |
| **A10** | Archinex | Référentiels (ingestion, revue, couverture) | A7, L8 |
| **A11** | Archinex | Tableau de bord de la KB et campagnes d'enrichissement | A7, L9 |

Ordre recommandé : L5 → A6 → L6 → A7 (premier jalon utile : les experts relisent dans Archinex), puis L7 ∥ L8 → A8 ∥ A10, puis A9, L9, A11.

Portes :

- **G5** (après A7) — Un expert invité dans Archinex relit un candidat de son domaine sans ligne de commande ; un expert d'un autre domaine reçoit 403 ; la seconde revue d'un principe est sollicitée automatiquement.
- **G6** (après A8, A9, A10) — Les 5 clauses brouillon (P-001, P-002, P-009, P-012, P-015) sont validées ou amendées depuis Archinex ; le jeu d'évaluation est annoté en ligne et `recall ≥ 80 %` s'affiche ; un référentiel est ingéré, revu et déclaré couvert sans CLI.
- **G7** (après L9, A11) — Un candidat accepté est promu et publié depuis Archinex (PR de KB créée puis fusionnée), et l'instantané scellé suivant le contient.

---

## 3. Contrat entre Archinex et LLMOps (contrat LLMOps 1.4 à 1.8)

### 3.1 Authentification des personnes (L5, A6)

Chaque appel d'Archinex porte :

- `Authorization: Bearer <jeton de service Archinex>` : un jeton de `ENGAGEMENT_TOKENS` avec le scope `kb:delegate` (nouveau). Il authentifie **le système**.
- `X-Actor-Assertion: <JWT>` : l'identité de **la personne**, signée par Archinex. Claims :

```json
{
  "iss": "archinex",
  "aud": "llmops",
  "sub": "user:4f1c…",
  "handle": "@security-compliance-team",
  "name": "…",
  "email": "…",
  "kb_roles": ["kb:review", "kb:evaluate", "kb:maintain", "kb:admin"],
  "iat": 1790000000,
  "exp": 1790000300,
  "jti": "…"
}
```

Règles LLMOps :

- Assertion acceptée seulement si le jeton de service a `kb:delegate`, si la signature est valide (clés `ARCHINEX_JWKS_URL` ou `ARCHINEX_PUBLIC_KEY`), si `aud = llmops` et si `exp - iat ≤ 300 s`. Le `jti` est mémorisé jusqu'à `exp` (anti-rejeu).
- Le **rôle déclaré ne suffit pas** : pour relire un candidat, le `handle` doit aussi être propriétaire du domaine du candidat (ou d'un parent), ou `default_owner`, ou porter `kb:maintain`. C'est LLMOps qui tranche (règle déterministe, testée).
- L'acteur de l'assertion devient `actor`, `reviewer` ou `author` dans l'historique ; le jeton brut n'est jamais journalisé (déjà le cas en L2).
- Sans assertion, le comportement 1.3 est inchangé (jetons `kb:review` existants).

Nouvelle interface : `GET /api/knowledge/me` → `{handle, kb_roles, owned_domains, pending_reviews}`, pour vérifier l'intégration.

### 3.2 Revue et sollicitation (L6, A7)

| Route (contrat 1.5) | Outil MCP | Rôle |
|---|---|---|
| `GET /api/knowledge/reviews/inbox` | `get_review_inbox` | Candidats qui attendent **l'acteur** : propriétaire assigné, second relecteur désigné, ou réassignation. Tri par ancienneté ; champ `due_at` (5 jours ouvrés). |
| `POST /api/knowledge/candidates/{id}/assign` | `assign_kb_candidate` | Réassigner à un autre handle propriétaire (`kb:maintain` ou propriétaire actuel), avec motif. |
| `POST /api/knowledge/candidates/{id}/request-review` | `request_kb_review` | Solliciter un expert précis (second relecteur, avis consultatif). Crée une **demande de revue** `{requested_handle, kind: second_review\|advice, message, due_at}`. |
| `POST /api/knowledge/candidates/{id}/comments` | `comment_kb_candidate` | Fil de discussion sur un candidat (question à l'auteur, réponse). Un commentaire n'est pas une décision. |
| `GET /api/knowledge/events?since=<cursor>` | — | Flux d'événements de gouvernance, en ajout seul : `candidate.submitted`, `candidate.assigned`, `review.requested`, `candidate.reviewed`, `candidate.promoted`, `candidate.published`, `reminder.due`, `eval.updated`, `coverage.changed`. Chaque événement porte `recipients: [handle]`. |
| `GET/PUT /api/knowledge/owners` | `list_domain_owners` | Registre des propriétaires (lecture pour tous, écriture `kb:admin`, chaque changement journalisé). Amorcé depuis `owners.yaml`. |

- Le webhook sortant est optionnel (`GOVERNANCE_WEBHOOK_URL`, signé HMAC) ; Archinex commence par un **polling** du flux toutes les 30 s.
- `kb remind` devient une tâche interne qui émet `reminder.due` ; la commande CLI reste.

### 3.3 Atelier de doctrine et évaluations (L7, A8, A9)

| Route (contrat 1.6) | Rôle |
|---|---|
| `GET /api/knowledge/templates/{asset_type}` | Gabarit structuré d'un type d'actif : champs de front-matter (avec vocabulaire des domaines, phases, confiance), sections attendues, aide. Généré depuis `data/kb/*/_template.md` et `data/kb/schema/frontmatter.schema.json`. |
| `POST /api/knowledge/candidates/validate` | **Contrôles à blanc** d'un contenu, sans créer de candidat : renvoie les 7 contrôles. Permet un retour immédiat dans le formulaire. |
| `POST /api/knowledge/checks/simulate` | Évalue des **clauses proposées** (`checks[]`) contre le jeu d'évaluation et contre des options libres : verdicts avant/après, régressions, rappel et précision. Déterministe. |
| `GET /api/knowledge/evals/{dataset}` / `PATCH …/cases/{case_id}` | Jeu d'évaluation `check_option_v1` stocké en base (import initial du JSONL) : lister les cas, annoter (`expected`), passer `annotation_status` à `validated` avec l'annotateur. |
| `POST /api/knowledge/evals/{dataset}/runs` / `GET …/runs/{id}` | Exécuter l'évaluation (celle de `make eval-check`) et consulter rappel, précision, cas manqués. |
| `POST /api/knowledge/verdict-feedback` | Retour d'un humain sur un verdict (`typed_id`, `check_id`, option, `feedback: wrong_violation\|missed_violation\|correct`, justification). Stocké, et converti **à la demande d'un évaluateur** en cas d'évaluation ou en candidat `amendment` de la clause. |

### 3.4 Référentiels (L8, A10)

| Route (contrat 1.7) | Rôle |
|---|---|
| `POST /api/frameworks/ingestions` (multipart) | Téléverser une source (pdf, html, txt, docx) avec `framework`, `version`, `tag` ; exécute l'ingestion de L3 (extraction, SHA-256, découpage) dans le stockage de gouvernance ; renvoie un `ingestion_id`. Rôle `kb:maintain`. |
| `GET /api/frameworks/ingestions/{id}` | Exigences découpées, avec texte légal, liens proposés, critères proposés, décision de revue par ligne. **Remplace la feuille CSV.** |
| `PATCH /api/frameworks/ingestions/{id}/rows/{requirement_id}` | Décision de l'expert sur une ligne (`accept`, `amend`, `reject`, liens, critères, commentaire) ; relecteur = acteur de l'assertion. |
| `POST /api/frameworks/ingestions/{id}/link-proposals` | Archinex dépose les **liens proposés par son LLM local** (`llm-derived`), validés contre les identifiants existants. LLMOps n'appelle aucun LLM. |
| `POST /api/frameworks/ingestions/{id}/apply` | Équivalent de `kb apply-review` : crée les candidats `framework_ingestion` revus et les promeut (via L9). |
| `POST /api/frameworks/{fw}/coverage-declaration` | Équivalent de `kb declare-coverage` ; refusé avec la liste des manques, comme en CLI. |

### 3.5 Promotion, publication et santé (L9, A11)

| Route (contrat 1.8) | Rôle |
|---|---|
| `POST /api/knowledge/candidates/{id}/promote` | Rôle `kb:maintain`. Écrit l'actif dans une branche de travail du dépôt de KB (D2). |
| `POST /api/knowledge/publications` | Rôle `kb:maintain`. Regroupe les candidats promus, ouvre la PR de KB (titre, `CHANGELOG`, liste des relecteurs), renvoie son URL. À la fusion (webhook GitHub ou polling), les candidats passent en `published` avec l'identifiant de l'instantané. |
| `GET /api/knowledge/health` | Indicateurs : volume par type et domaine, actifs `validated_by` vide, part de verdicts `unassessed`, couverture par référentiel, âge de la file par propriétaire, candidats en retard, dernier instantané. |

---

## 4. Lots LLMOps

### L5 — Identité déléguée et état de gouvernance persistant

1. Stockage de gouvernance selon D1 : `pipelines/governance/store.py` (SQLAlchemy), migrations Alembic, tables `candidates`, `candidate_events`, `review_requests`, `comments`, `domain_owners`, `governance_events`, `eval_datasets`, `eval_cases`, `eval_runs`, `verdict_feedback`, `framework_ingestions`, `ingestion_rows`. `CandidateRepository` gagne une implémentation `sql` (`CANDIDATES_BACKEND=sql`), et le stub `gcs` est retiré.
2. Commande `kb migrate-governance` : importe `data/candidates/*.json`, `data/kb/owners.yaml` et `tests/evals/datasets/check_option_v1.jsonl`. Idempotente.
3. Vérification des assertions (§3.1) dans `mcp_server/core/auth.py` : `resolve_actor(request) -> Actor | None`, scope `kb:delegate`, anti-rejeu. L'autorisation de revue se base sur `domain_owners` et non plus sur `owners.yaml` lu à chaque appel.
4. `GET /api/knowledge/me`.
5. Tests : signature invalide, audience fausse, assertion expirée ou rejouée → 401 ; jeton sans `kb:delegate` → assertion ignorée ; `reviewer` du corps différent de l'acteur → 403 ; relecteur hors domaine → 403.

**Critères** : tests gelés verts ; les tests L2 passent avec le backend `sql` (SQLite) et `file` ; la file survit à un redémarrage.

### L6 — API de revue et de sollicitation

1. Routes et outils de §3.2, avec schémas (`schemas/review_inbox.schema.json`, `governance_event.schema.json`) et types TS.
2. Demandes de revue : la seconde revue d'un principe crée une `review_request` vers le second propriétaire désigné (même règle qu'en L2) ; `review_kb_candidate` clôt la demande de l'acteur.
3. Flux d'événements avec curseur ; `recipients` calculés de façon déterministe ; webhook HMAC optionnel.
4. `notify_owner` : n'envoie Discord, ntfy ou e-mail que si le handle n'a pas de compte déclaré par Archinex (`domain_owners.delegated = true`), pour éviter les doubles notifications.
5. Tests : boîte de revue par acteur, réassignation, demande de seconde revue, relances (`reminder.due` après 5 jours ouvrés), idempotence du curseur.

### L7 — Atelier de doctrine et évaluations

1. `GET /api/knowledge/templates/{type}` et `POST /api/knowledge/candidates/validate` (réutilisent `pipelines/kb_candidates/checks.py`).
2. `POST /api/knowledge/checks/simulate` : construit un index de doctrine temporaire où les clauses proposées remplacent celles de l'actif, exécute `check_option` sur les cas du jeu d'évaluation et sur les options fournies, renvoie le différentiel. Aucune écriture.
3. Jeu d'évaluation en base, annotations avec annotateur et date, exécutions historisées ; `make eval-check` lit la base si configurée, sinon le JSONL.
4. `verdict-feedback` et conversion en cas d'évaluation ou en candidat `amendment` (action d'un `kb:evaluate`).
5. Tests : simulation déterministe ; une clause qui fait baisser le rappel est signalée comme régression ; un retour converti produit un cas annoté `proposed`.

### L8 — Ingestion des référentiels par API

1. Routes de §3.4 réutilisant `pipelines/frameworks/` ; le texte source est stocké (ou référencé) avec son SHA-256 ; `data/staging/` n'est plus utilisé côté serveur.
2. Taille maximale, types MIME contrôlés, extraction dans un processus borné en temps.
3. `apply` passe par le cycle des candidats (L2) puis par la promotion de L9.
4. Tests : le scénario de bout en bout de L3 (`tests/integration/test_framework_ingestion.py`) est rejoué via l'API.

### L9 — Promotion et publication par PR git, santé

1. `pipelines/publication/git_publisher.py` : client GitHub App (clé en secret), branche `kb/publication-<date>-<n>`, un commit par actif, PR avec `CHANGELOG` et relecteurs. Mode `local` conservé pour le dev (écriture directe, commande `kb publish`).
2. Réception de la fusion (webhook GitHub signé, ou polling) → candidats `published`, événement `candidate.published`.
3. `GET /api/knowledge/health`.
4. Tests : publisher simulé (faux client GitHub) ; aucune écriture dans `data/kb/` du conteneur en mode `github`.

---

## 5. Lots Archinex

### A6 — Comptes, rôles KB et assertion d'acteur

1. Modèle Prisma `User` étendu (ou `KbProfile`) : `kbHandle` (unique), `kbRoles` (`kb:review`, `kb:evaluate`, `kb:maintain`, `kb:admin`), `kbDomains` (lecture seule, synchronisés depuis `GET /api/knowledge/owners`).
2. Écran **Administration › Experts** (rôle admin Archinex) : inviter un expert par e-mail (lien d'activation à usage unique, expiration 7 jours), lui attribuer un handle et des rôles KB, désactiver un compte. Pour `kb:admin` : modifier le registre des propriétaires (`PUT /api/knowledge/owners`), chaque changement tracé en `DomainEvent`.
3. `src/lib/server/llmops/actorAssertion.ts` : signature EdDSA des assertions (clé privée en secret serveur), JWKS publié sur `/.well-known/jwks.json`. `llmopsClient` ajoute `X-Actor-Assertion` à chaque appel fait **au nom d'un utilisateur** ; les appels système (seed, polling) n'en portent pas.
4. Casbin : ressources `kb:*` alignées sur les rôles KB ; un utilisateur sans rôle KB ne voit pas les écrans de gouvernance.
5. Page **Mon profil KB** : `GET /api/knowledge/me` (handle, domaines possédés, revues en attente).

**Critères** : un expert invité active son compte et voit ses domaines ; l'assertion est refusée par LLMOps si la clé est fausse (test d'intégration avec le faux LLMOps) ; aucun secret dans le bundle client (test).

### A7 — Boîte de revue et sollicitation

1. **Boîte de revue** (`/kb/reviews`) : candidats de `GET /api/knowledge/reviews/inbox`, retard mis en évidence, filtre par domaine et type.
2. **Fiche candidat** : contenu, diff avec l'actif cible pour un amendement, résultats des 7 contrôles expliqués, verdicts de `doctrine_conflict`, historique, fil de commentaires. Actions : *Accepter*, *Amender* (éditeur Markdown + front-matter avec contrôles à blanc de L7), *Rejeter* (motif obligatoire), *Réassigner*, *Solliciter un expert* (sélecteur parmi les comptes ayant le domaine), *Demander un complément à l'auteur*.
3. **Notifications** : polling de `GET /api/knowledge/events` (tâche serveur), création de notifications in-app pour les `recipients` ayant un compte, e-mail récapitulatif quotidien (désactivable par l'utilisateur), relances à échéance. Un expert sans compte reste notifié par LLMOps (L6 §4).
4. La fiche de décision d'A5 affiche le statut et les commentaires des candidats issus de l'arbitrage.
5. Le badge `production_mode` est visible partout ; un contenu `llm-derived` est affiché « proposé par IA, non validé ».

**Critères (porte G5)** : scénario e2e avec faux LLMOps : soumission → notification in-app du bon expert → acceptation → seconde revue sollicitée et faite par un autre expert → statut `accepted` visible sur la décision.

### A8 — Atelier de doctrine

1. **Nouvel actif** : assistant en étapes basé sur `GET /api/knowledge/templates/{type}` (principe, pattern, ADR, contrôle, terme de glossaire), contrôles à blanc à chaque étape, choix des preuves (`measure`, `audit`, `engagement`, `vendor-doc`) avec aperçu de la confiance calculée, soumission.
2. **Amender un actif** : depuis l'explorateur de doctrine (lecture via `get_asset`), bouton *Proposer un amendement* qui ouvre l'éditeur prérempli.
3. **Éditeur de clauses `checks`** : formulaire (`kind`, `when.terms_any/terms_all`, `expect`, `message`) avec aide sur le vocabulaire et les synonymes, et bouton *Tester* qui appelle `POST /api/knowledge/checks/simulate` (verdicts avant/après sur le jeu d'évaluation et sur des options saisies). La validation passe `checks_status` à `validated` via un candidat `amendment` relu.
4. **Assistance LLM locale (optionnelle)** : proposer un brouillon d'actif ou de clause à partir d'une décision ou d'un REX ; toujours `llm-derived`, jamais soumis sans action humaine.
5. **Import des propositions en attente** : écran mainteneur listant `data/proposals/*.jsonl` exposés par LLMOps (ou importés), avec *Soumettre à la revue* par lot — pour mettre en file les 18 brouillons IT sans CLI.

**Critères** : un expert crée un pattern dont tous les contrôles passent avant soumission ; une clause testée affiche son effet sur le rappel ; un contenu avec une IP privée est bloqué dès la saisie.

### A9 — Évaluations

1. **Campagne d'annotation** du jeu d'évaluation : cas assignés aux évaluateurs par domaine, annotation `expected` par `typed_id`, validation (`annotation_status: validated`), double annotation optionnelle avec accord inter-annotateurs affiché.
2. **Exécution** d'une évaluation depuis l'interface, historique des rappels et précisions, liste des cas manqués avec lien vers la clause à amender.
3. **Retours des débats** : dans le fil d'arguments d'A3, sur chaque argument `verification` issu de `check_option`, actions *Verdict juste* / *Fausse violation* / *Violation manquée* avec justification → `POST /api/knowledge/verdict-feedback`. Un évaluateur trie les retours et les convertit en cas d'évaluation ou en amendement de clause.

**Critères (porte G6, partie évaluation)** : les 30 cas sont validés dans l'interface ; le rappel affiché est celui de LLMOps ; un retour de débat devient un cas d'évaluation.

### A10 — Référentiels

1. **Référentiels** (`/kb/frameworks`) : couverture de chaque référentiel (reprise de `docs/COVERAGE.md` via `get_framework_coverage`), manifeste provisoire ou issu d'une source, exigences manquantes.
2. **Nouvelle ingestion** (mainteneur) : téléversement de la source officielle, version, tag ; suivi de l'extraction.
3. **Revue en ligne** des exigences découpées (remplace la feuille CSV) : une ligne par exigence, texte légal, liens et critères proposés, décision et commentaire, assignation des lignes aux experts du domaine. Bouton *Proposer des liens* : LLM local d'Archinex → `POST …/link-proposals` (`llm-derived`).
4. *Appliquer la revue* puis *Déclarer la couverture* (réservé à l'expert propriétaire du référentiel), avec affichage des blocages renvoyés par LLMOps.
5. Le bandeau de couverture des projets (A4 §7.2) renvoie vers cet écran.

**Critères (porte G6, partie référentiels)** : l'extrait NIS2 de test est ingéré, revu et déclaré couvert entièrement depuis Archinex (e2e avec faux LLMOps rejouant les réponses de L8).

### A11 — Tableau de bord et campagnes d'enrichissement

1. **Santé de la KB** : indicateurs de `GET /api/knowledge/health` (volume par domaine, actifs non validés, part d'`unassessed`, couverture, âge de la file par propriétaire, dernier instantané).
2. **Campagnes** : un mainteneur crée une campagne (objectif, périmètre, échéance, experts), par exemple « valider les clauses brouillon », « couvrir NIS2 », « relire les 18 brouillons IT », « valider les contrôles existants (`validated_by` vide) ». Les tâches sont des demandes de revue (L6) ou des cas d'évaluation (L7) ; la progression est calculée à partir des événements.
3. **Publication** (mainteneur) : liste des candidats acceptés, *Promouvoir*, *Publier* (PR de KB, L9), suivi jusqu'à `published`.
4. Suggestions de campagnes générées de façon déterministe à partir des indicateurs (domaine sans clause, référentiel `partial`, file en retard).

**Critères (porte G7)** : une campagne « valider les clauses brouillon » est créée, réalisée et close dans l'interface ; une publication ouvre une PR de KB puis passe les candidats en `published`.

---

## 6. Reprise de l'existant (à faire dès L5/A6)

| Existant | Reprise |
|---|---|
| `data/kb/owners.yaml` (100 domaines, 23 handles) | Importé dans `domain_owners` ; un compte Archinex est créé et invité par handle ; les e-mails manquants sont saisis à l'invitation. |
| Jetons `kb:review` de `ENGAGEMENT_TOKENS` | Conservés pour la console de secours ; les experts passent par Archinex. |
| 5 clauses `checks` brouillon | Première campagne A11 : revue dans l'éditeur de clauses (A8). |
| `tests/evals/datasets/check_option_v1.jsonl` | Importé en base (L7) ; campagne d'annotation (A9). |
| `data/proposals/it-infrastructure.jsonl` (18 brouillons) | Soumis depuis l'écran d'import (A8 §5) ; campagne de revue du domaine `it-infrastructure/*`. |
| Manifestes provisoires (NIS2, ISO 27001, SecNumCloud, RGPD, 3GPP) | Campagne « sources officielles » : téléversement et revue en ligne (A10). |
| Contrôles existants sans `validated_by` | Campagne de validation par référentiel, via une ingestion ou un amendement en lot. |

---

## 7. Définition de « terminé »

Pour chaque PR, en plus des règles des plans compagnons :

- [ ] LLMOps : `make verify` et `make test` verts, tests gelés inchangés, nouvelles interfaces gelées, schémas et types TS publiés, contrat `knowledge-hub-api-v1.md` §5.x mis à jour, `schema_version` en version mineure suivante.
- [ ] Archinex : `npm run verify` vert, proposition OpenSpec du lot, faux LLMOps (`tests/helpers/fakeLlmops.ts`) étendu aux nouvelles routes.
- [ ] Chaque action d'expert est attribuée à une personne identifiée par assertion, jamais par un champ libre.
- [ ] Aucun LLM appelé par une route servie de LLMOps ; toute sortie de LLM d'Archinex est validée par zod et marquée `llm-derived`.
- [ ] Aucun secret (jeton de service, clé de signature, clé GitHub App) dans le navigateur ni dans le dépôt.
- [ ] Documentation utilisateur (`USER_GUIDE.md` d'Archinex) : un parcours par rôle (expert relecteur, évaluateur, mainteneur, administrateur).

## 8. Hors périmètre

- Générer ou valider de la doctrine sans humain (auto-acceptation, seuils automatiques).
- Déplacer la doctrine elle-même hors de git (voir D2).
- Faire évoluer l'écran de revue de `apps/kb-client-app` (D4).
- L'assemblage du HLD.
