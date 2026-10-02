# Audit technique — `MauriceIsrael/LLMOps`

**Révision analysée** : `31c1d6b` (branche `main`, 50 commits, auteur unique)
**Date** : 5 septembre 2026
**Méthode** : clone complet, inspection statique du code Python / TypeScript / Svelte, analyse de l'historique Git, exécution de `ruff` (jeu de règles étendu), lecture des workflows CI, des Dockerfiles et de la chaîne de déploiement GCP. Les tests n'ont pas été exécutés (dépendance `ladybug` non installée dans l'environnement d'audit) : les constats sur la suite de tests sont donc structurels, pas comportementaux.

---

## 1. Synthèse exécutive

Le projet porte une idée forte et peu commune : **un graphe de connaissances d'architecture où chaque énoncé transporte sa propre épistémologie** (`confidence` ∈ {verified, designed, vendor-stated, stated-by-client, assumed} × `maturity` ∈ L0→L4), exposé en MCP, de sorte qu'un générateur de document sache *ce qu'il a le droit d'affirmer*. C'est un angle réellement différenciant : la plupart des projets « GraphRAG » servent du texte, celui-ci sert du texte **plus son statut de preuve**. Le cœur serveur est déterministe, sans appel LLM à la lecture — un choix architectural défendable, testable et économiquement lisible.

L'exécution technique est inégale. Le socle Python est propre là où il compte (ports/adaptateurs, enveloppe de réponse normalisée, tests de caractérisation), mais la couche sécurité/configuration/déploiement présente des écarts entre **ce que la documentation promet** et **ce que le code fait réellement**. Pour un projet dont la proposition de valeur *est* la traçabilité et la fiabilité des affirmations, ces écarts ne sont pas de simples bugs : ils attaquent la crédibilité du produit lui-même.

### Notation par axe

| Axe | Note | Commentaire |
|---|:---:|---|
| Proposition de valeur / originalité | **A** | Métadonnées épistémiques + double plan : rare et pertinent |
| Architecture logicielle (Python) | **B** | Ports/adaptateurs efficaces, mais deux systèmes de configuration concurrents |
| Sécurité | **D** | Secret exposé dans l'historique, contrôle en écriture mono-couche, `authorise()` ouvert par défaut |
| Tests | **B-** | 242 tests, golden files, tests de caractérisation — mais l'évaluation est un échafaudage vide |
| CI/CD | **C** | Pas de scan sécurité, pas de couverture, front-end jamais construit, déploiement manuel |
| Documentation | **B-** | Abondante et bilingue, mais contredite par le code sur plusieurs points critiques |
| Hygiène du dépôt | **D** | 157 Mo, 117 fichiers suivis *et* ignorés, artefacts de tests versionnés |
| Pérennité / gouvernance | **C-** | Bus factor = 1, aucune release, ADR normatifs manquants |

**Verdict** : projet à fort potentiel, actuellement en état « démo publique convaincante » et non « socle réutilisable par un tiers ». Trois chantiers courts (sécurité, cohérence config, hygiène) suffiraient à basculer la perception.

---

## 2. Forces à préserver explicitement

Ces points sont bons, et il faut les protéger par des tests avant toute refonte.

1. **Le modèle épistémique.** `is_provisional`, `unripe_subjects`, `open_conflicts` dans le payload de rendu : c'est le vrai produit. Un générateur DOCX tiers peut refuser d'affirmer ce qui n'est pas mûr. Aucun concurrent direct ne fait ça proprement.
2. **La couture ports/adaptateurs.** `tools/ports/graph_store.py` définit un `Protocol` minimal (`execute_cypher`, `close`). C'est ce qui a rendu possible la migration Kùzu → LadybugDB en un commit (`0ba3bbe`) sans réécrire les outils métier. Décision d'architecture payante, à citer comme telle.
3. **L'enveloppe de réponse.** `mcp_server/core/envelope.py` normalise `ok / not_found / not_implemented / invalid_argument / error / unauthorized`. Un client MCP tiers peut brancher un traitement d'erreur générique. Peu de serveurs MCP le font.
4. **Les tests de caractérisation.** `tests/contract/test_cypher_characterization.py` (598 lignes) fige le comportement Cypher observé *avant* migration. C'est la bonne technique, appliquée au bon moment.
5. **`MIGRATION_NOTES.md`.** L'audit de couplage `import kuzu` site par site, avant migration, est de l'ingénierie sérieuse. Ce document mérite d'être promu en ADR.
6. **Le dogfooding.** Principes, ADR, patterns, contrôles NIS2/SecNumCloud/3GPP/ISO27001 sont stockés dans le format que le produit sert. La base de connaissances est son propre jeu de démonstration.
7. **L'onboarding.** README bilingue, configuration MCP copiable en 30 secondes, instance publique vivante, `SECURITY.md`, templates d'issues dont un « build a client ». L'intention d'ouverture est réelle.

---

## 3. Constats critiques (P0 — à traiter cette semaine)

### P0-1 — Webhook Discord actif exposé dans l'historique Git

Le commit `9a50305` (« feat(notifier): configure default Discord webhook ») a introduit en dur :

```
DEFAULT_DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1544949043631882250/NlTlNyu1u5Zr9ilw5UCeZoiUrT1nBvFG2F3ArNLg-y4NSGxN4UOPpLkzPhM90x9awKGY"
```

dans `mcp_server/core/notifier.py` **et** dans le code TypeScript de l'application (`758e874`). Le commit `8014c53` l'a retiré du HEAD — mais **retirer un secret du code ne le révoque pas**. Il reste lisible par `git log -p`, par tout fork, et par tout clone déjà effectué.

**Impact** : n'importe qui peut poster dans le canal Discord du propriétaire (spam, hameçonnage crédible puisque le message vient du webhook « officiel »).

**Action** :
1. Révoquer/régénérer le webhook dans Discord **maintenant** (c'est la seule mesure qui compte).
2. Ne pas réécrire l'historique si le dépôt est déjà largement cloné — c'est illusoire. Traiter le secret comme brûlé.
3. Ajouter `gitleaks` en pré-commit **et** en job CI bloquant, pour que le cas ne se reproduise pas.

---

### P0-2 — Le drapeau `read_only` est accepté puis ignoré

`tools/adapters/ladybug_store.py` :

```python
def get_database(cls, db_path: str, read_only: bool = False) -> Any:
    ...
    db = lb.Database(cache_key, ..., read_only=False)   # ligne 36 — valeur littérale
```

Le paramètre `read_only` est reçu, stocké dans `self.read_only` (ligne 92)… et jamais transmis à `lb.Database`. Tous les appelants qui écrivent `make_graph_store(path, read_only=True)` — dont `mcp_server/core/db.py:103` et le endpoint `/health` — obtiennent en réalité une base **ouverte en écriture**.

Conséquence : la seule protection en écriture du serveur est le filtre de `mcp_server/core/db.py:95` :

```python
write_keywords = r"\b(CREATE|SET|DELETE|MERGE|DROP|ALTER|DETACH|REMOVE)\b"
```

C'est une **liste noire par expression régulière, en couche unique**, avec trois défauts :

- **Trous de couverture.** `COPY … FROM/TO`, `EXPORT DATABASE`, `IMPORT DATABASE`, `INSTALL`, `LOAD EXTENSION`, `ATTACH` ne sont pas dans la liste. Selon ce que LadybugDB expose, certains permettent une écriture disque ou une lecture de fichier arbitraire depuis le serveur. `CALL` est explicitement utilisé ailleurs dans le code (`CALL table_info(...)`) et n'est donc pas filtrable sans casse.
- **Faux positifs.** `MATCH (a:Asset) WHERE a.domain CONTAINS 'merge' RETURN a` est rejeté : le mot-clé est cherché dans la chaîne brute, littéraux de chaîne compris. Une requête de lecture légitime peut être refusée.
- **Aucune défense en profondeur.** Le contrôle censé être structurel (base ouverte en lecture seule) est neutralisé par le bug ci-dessus. Il ne reste qu'une couche, la plus fragile.

**Action** :
1. Corriger `get_database` pour propager `read_only` (et propager `read_only` dans le cache : deux instances avec des modes différents ne doivent pas partager la même entrée de cache).
2. Conserver le filtre regex comme **deuxième** ligne, pas comme la seule, et le convertir en liste blanche : n'autoriser que les requêtes dont le premier mot-clé significatif est `MATCH`, `RETURN`, `WITH`, `UNWIND`, `CALL <procédure autorisée>`.
3. Ajouter un test de contrat par mot-clé refusé **et** un test qui prouve que la base sous-jacente rejette l'écriture même si le filtre est contourné.

---

### P0-3 — `authorise()` est ouvert par défaut

`mcp_server/core/auth.py`, fin de fonction :

```python
env_tokens = os.getenv("ENGAGEMENT_TOKENS", "").strip()
if env_tokens:
    ...  # scoping multi-tenant
# When ENGAGEMENT_TOKENS is not configured, default_user or standard callers are accepted
```

Si `ENGAGEMENT_TOKENS` est vide — oubli, erreur de déploiement, variable non propagée dans un nouvel environnement — **tout appelant accède à tout engagement**. Un point de contrôle d'autorisation doit échouer fermé, jamais ouvert.

Deux aggravants dans la même fonction :

- **Rôles par comparaison de chaîne** : `if caller in ("server_admin", "admin", "system"): return`. L'identité d'appelant provient du jeton présenté ; si un jeton locataire vaut littéralement `admin`, son porteur devient administrateur.
- **Liste noire pilotée par les tests** : `if caller.startswith("unauthorised") or ... or caller == "anonymous_blocked"`. Ce sont des chaînes magiques issues des tests unitaires, promues en logique de production. Le test devrait constater le refus par défaut, pas imposer un motif de nom.

**Action** : inverser la logique (refus par défaut, autorisation explicite), séparer *jeton* et *identité* (le jeton est une clé d'une table `token → {tenant_id, scopes, role}`), et remplacer les rôles-chaînes par une énumération typée.

---

### P0-4 — `SECURITY.md` contredit la configuration réellement déployée

`SECURITY.md` affirme, à propos du jeton public `demo-public-2026-08` :

> It grants access exclusively to the **read-only Knowledge Plane** (`LLMOPS_PLANE=knowledge`) … No write, insert, update, or delete operations are exposed or permitted on the public endpoint.

`cloudbuild.yaml` déploie en réalité :

```yaml
- 'GRAPH_BACKEND=ladybug,LLMOPS_TRANSPORT=sse,LLMOPS_PLANE=all,ENGAGEMENT_TOKENS=demo-public-2026-08:nordwave-mcx-2027'
```

avec `--allow-unauthenticated`. Le plan Engagement est donc exposé (dix outils supplémentaires enregistrés par `mcp_server/main.py:89`), et le dernier commit le confirme (« enable all planes on Cloud Run with scoped public demo token »). La politique de sécurité publiée décrit un déploiement qui n'existe plus.

**Action** : synchroniser `SECURITY.md` avec `cloudbuild.yaml`, et — mieux — ajouter un job CI qui échoue si la valeur de `LLMOPS_PLANE` dans `cloudbuild.yaml` ne correspond pas à celle documentée. Le dépôt possède déjà ce réflexe pour le jeton de démo (étape « Check Demo Token Consistency ») : appliquer le même patron au plan.

---

### P0-5 — Contournement d'authentification par `session_id`

`mcp_server/main.py:210-221` : si aucun jeton valide n'est fourni mais que le paramètre de requête `session_id` correspond à une session SSE active, la requête est acceptée avec `caller = "default_user"`.

Un `session_id` transite en **paramètre d'URL** : il apparaît dans les journaux d'accès Cloud Run, les en-têtes `Referer` et l'historique des proxys. Combiné à P0-3 (si `ENGAGEMENT_TOKENS` venait à être vide), `default_user` obtient un accès complet.

**Action** : lier la session à l'identité qui l'a créée (le `caller` est déjà stocké dans `_session_callers` — l'utiliser au lieu du repli `"default_user"`), et refuser toute requête `/messages` dont l'identité de session est inconnue.

---

## 4. Constats majeurs (P1 — ce sprint)

### P1-1 — Deux systèmes de configuration concurrents, avec dérive de valeurs

| | `mcp_server/config.py` | `mcp_server/core/config.py` |
|---|---|---|
| Classe | `Settings` | `ServerConfig` |
| Préfixe env | `LLMOPS_` | *aucun* |
| Chemin BD | `DB_PATH = data/kuzu_db` | `db_path = data/knowledge.lbug` |
| `.env` | `load_dotenv()` global | `env_file=".env"` |

Les deux sont instanciés à l'import et **les deux sont importés par `mcp_server/main.py`** (lignes 22 et 27). `mcp_server/db/ladybug_client.py` utilise `settings.DB_PATH`, c'est-à-dire un chemin Kùzu obsolète, comme valeur de repli.

Conséquence directe et vérifiable : `ServerConfig.plane` est typé `Literal["knowledge", "engagement"]`, sans préfixe d'environnement — la variable `LLMOPS_PLANE=all` fixée dans le `Dockerfile` **ne peut donc pas** alimenter ce champ. Le code contourne le problème en lisant `os.getenv("LLMOPS_PLANE", server_config.plane)` directement (lignes 63 et 234). La configuration typée est court-circuitée par la configuration réelle.

**Action** : fusionner en un seul `Settings` avec préfixe `LLMOPS_`, élargir `plane` à `Literal["knowledge", "engagement", "all"]`, supprimer les 13 `os.getenv` dispersés hors tests, et faire échouer le démarrage si une variable requise manque.

### P1-2 — Propagation d'identité incohérente → bug fonctionnel

`mcp_server/core/db.py:126` :

```python
def open_connection(scope: str | None = None, caller: str = "default_user") -> ...
```

La valeur par défaut est la chaîne `"default_user"`, **pas `None`**. Or `authorise()` ne consulte le `ContextVar` d'identité que si `caller is None`. Et `query_graph` (`mcp_server/knowledge/tools.py`) appelle `open_connection(scope=engagement)` sans passer d'appelant.

Résultat en production (où `ENGAGEMENT_TOKENS` est défini) : `authorise("default_user", "nordwave-mcx-2027")` → `default_user` absent de la table → **`Unauthorised`**. Le jeton de démo, pourtant explicitement scopé sur cet engagement, ne peut pas utiliser `query_graph` sur son propre engagement. Ce n'est pas une faille, c'est une fonctionnalité cassée par une valeur par défaut.

Symptôme adjacent : l'identité circule par **trois canaux redondants** (`ContextVar`, `request.state.caller`, `request.scope["caller"]`), ce qui trahit une propagation dont personne n'est sûr. Les `ContextVar` posés dans un `BaseHTTPMiddleware` Starlette sont un piège documenté ; la redondance est un contournement, pas une solution.

**Action** : `caller: str | None = None` par défaut, un seul canal d'identité, et un test d'intégration qui vérifie qu'un jeton scopé A ne lit pas l'engagement B *et* qu'il lit bien A.

### P1-3 — `/health` ne mesure pas la santé

`mcp_server/main.py:238` :

```python
store = make_graph_store("data/knowledge.kuzu", read_only=True)
```

Chemin Kùzu codé en dur, alors que le stockage a migré vers `.lbug`. L'ouverture échoue (ou est silencieusement redirigée par la logique de compatibilité de `ladybug_store.py:73-90`), l'exception est capturée, et le endpoint **renvoie `200 {"status": "ok"}` avec un champ `warning`**.

Un endpoint de santé qui renvoie `ok` quand la base est injoignable rend le `HEALTHCHECK` du Dockerfile et l'étape 5 de `scripts/deploy_gcp.sh` purement décoratifs : le déploiement sera déclaré réussi même si le graphe est vide.

**Action** : `/health` (liveness, toujours 200) et `/ready` (readiness : compte les nœuds `Asset`, renvoie **503** si l'ouverture échoue ou si le compte est nul). Utiliser `server_config.knowledge_db_path`, jamais un littéral.

### P1-4 — Les ADR normatifs du projet n'existent pas

`ADR-0014` et `ADR-0015` sont cités **40 fois** dans le code et la documentation, y compris comme source normative du différenciateur n°3 du README (« Dual-Plane Physical Isolation (ADR-0015) ») et dans les docstrings de `core/config.py`, `core/envelope.py`, `core/registration.py`.

`data/kb/decisions/` contient `ADR-0001` à `ADR-0013`. Ni `ADR-0014` ni `ADR-0015` n'existent en fichier, et aucun des deux n'apparaît dans `data/snapshots/latest.json` ni dans `fixtures/sealed_snapshot.json`.

C'est le constat le plus dommageable symboliquement : **un produit dont la thèse est la traçabilité des affirmations vers des décisions sourcées, viole cette thèse dans son propre dépôt.** Un évaluateur externe qui suit un lien `ADR-0015` et ne trouve rien tirera cette conclusion en trente secondes.

**Action** : rédiger les deux ADR (le contenu existe déjà, dispersé dans `docs/architecture.md` et `MIGRATION_NOTES.md`), les ingérer dans le graphe, et ajouter un test de contrat qui échoue si un identifiant `ADR-XXXX` cité dans le code ou la doc n'a pas de nœud correspondant. L'outil `get_dangling_references` existe déjà pour le plan Engagement — appliquer le même principe au dépôt.

### P1-5 — Le front-end n'est jamais vérifié par la CI

`apps/kb-client-app/` (SvelteKit 5, ~8 800 lignes) n'apparaît dans **aucun** workflow. Pas de `npm ci`, pas de `npm run build`, pas de `svelte-check` (le script existe pourtant), pas d'ESLint, pas de test unitaire ni end-to-end. Une régression front-end n'est détectable que manuellement.

Trois problèmes de sécurité s'y ajoutent :

- **`src/lib/auth/jwt.server.ts:20`** : repli sur un secret codé en dur si `JWT_SECRET` n'est pas défini. Le commentaire dit « NEVER use in production » — mais rien n'empêche le démarrage. Un déploiement sans `JWT_SECRET` permet à quiconque connaît ce dépôt public de forger un jeton `role: admin`. **Il faut lever une exception au démarrage, pas commenter.**
- **`src/lib/auth/users.server.ts`** : utilisateurs codés en dur avec mots de passe en clair (`admin123`). Le module semble mort (`hooks.server.ts` interroge Prisma), mais il est toujours exporté et importable. Du code d'authentification mort est du code d'authentification qui sera réactivé par erreur.
- **`prisma/dev.db`** est versionné. Vérifier ce qu'il contient avant de le laisser dans un dépôt public.

**Action** : job CI `frontend` (install, `svelte-check`, build), échec au démarrage si `JWT_SECRET` absent ou < 32 caractères, suppression de `users.server.ts`, retrait de `dev.db` du suivi.

### P1-6 — Workflow `ingest-kb.yml` obsolète depuis la migration

```yaml
- name: Upload Kùzu DB Artifacts
  path: |
    data/knowledge.kuzu
    data/engagements
```

`data/knowledge.kuzu` n'existe plus. Le workflow ne définit pas non plus `GRAPH_BACKEND: ladybug`, contrairement à `ci.yml` et `eval.yml`. Il s'exécute à chaque push touchant `data/kb/**` et produit un artefact vide ou partiel — un échec silencieux.

### P1-7 — L'évaluation est un échafaudage sans données

Le protocole d'évaluation (`docs/eval/PROTOCOL.md`) est intellectuellement solide : appariement chronologique des versions 3GPP, définition explicite d'un point de décision architectural, limite méthodologique assumée. C'est du travail sérieux.

Mais :

| Artefact | Attendu | Réel |
|---|---|---|
| `annotation/candidates.csv` | annotations pour le κ de Cohen | **50 lignes, 0 annotée** (`is_decision_point`, `question`, `verbatim` tous vides) |
| `tests/evals/datasets/adr_qa_dataset.json` | jeu QA sémantique | **2 cas** |
| `tests/bench/adr_bench.jsonl` | benchmark ADR | **10 cas** |

`scripts/eval/compute_kappa.py` n'a rien à calculer. Le workflow `eval.yml` s'exécute **toutes les nuits** avec `OPENAI_API_KEY` pour évaluer 2 cas sémantiques. Par ailleurs, ni `tests/bench`, ni `tests/evals`, ni `tests/eval` ne sont exécutés par `ci.yml` ou par `make test` — le harnais existe, il n'est pas dans la boucle.

**Action** : soit annoter le corpus (même 50 lignes par un seul annotateur, en le déclarant honnêtement comme κ non calculable faute de second annotateur), soit retirer la promesse de la documentation. Passer `eval.yml` de quotidien à hebdomadaire tant que le corpus est de cette taille.

### P1-8 — Le sceau SHA-256 n'est jamais vérifié

Le différenciateur n°4 annonce un « SHA-256 payload sealing ». `tests/contract/test_fixtures_contract.py:67` vérifie… que le champ existe et commence par `sha256:`. Le condensat n'est **jamais recalculé** sur le payload canonique. Un snapshot périmé, tronqué ou modifié à la main passe la CI.

**Action** : un test qui recalcule `payload_sha256` et compare, plus une étape CI qui régénère le snapshot et échoue en cas de dérive avec la version committée. Sans cela le « sceau » est un champ décoratif.

---

## 5. Constats moyens (P2)

### P2-1 — Hygiène du dépôt : 157 Mo pour ~29 000 lignes de code

| Poste | Poids |
|---|---|
| `data/eval/sources/upload/3gpp/` | **~56 Mo** (10 fichiers `.doc`/`.docx` + leurs `.zip` d'origine, doublons) |
| `docs/Notes KB/` | **~22 Mo** (2 `.zip`, 2 PDF, 2 DOCX, versions v1 et v2 côte à côte) |
| Bases `.lbug` + `dev.db` + artefacts `.kz` | ~3 Mo |

Les spécifications 3GPP sont versionnées **deux fois** (archive `.zip` *et* document extrait). Elles sont téléchargeables par `scripts/eval/fetch_3gpp.py`, qui existe déjà.

**117 fichiers sont simultanément suivis par Git et listés dans `.gitignore`** (`git ls-files -i -c`) : `artifacts/test_conf/`, `artifacts/test_unc/`, `artifacts/test_run_checks/`, `projects/`, `apps/kb-client-app/scratch/`. Le `.gitignore` a été écrit *après* les commits ; il n'a donc aucun effet sur ces fichiers. Des bases de graphe issues d'exécutions de tests (`.wal`, `.lock`, `.shadow`, `n-*.hindex`) sont dans le dépôt public.

**Action** : `git rm -r --cached` sur les 117 fichiers, suppression des `.zip` redondants (garder soit l'archive, soit l'extrait), Git LFS ou téléchargement à la demande pour les corpus 3GPP. Un clone devrait peser < 20 Mo.

### P2-2 — Gestion des erreurs : masquage et fuite d'information

Deux motifs opposés, tous deux problématiques.

**Masquage** — `mcp_server/knowledge/tools.py:63` :

```python
if "Binder exception" in err_str or "does not exist" in err_str or "Table" in err_str:
    return ok_response([])
```

Une erreur de schéma est convertie en **succès avec zéro résultat**, sur la base d'une correspondance de sous-chaîne dans un message d'exception. Un client ne peut pas distinguer « aucun asset ne correspond » de « la table `Asset` a disparu ». Sur l'ensemble du code non-test : 88 `except Exception`, dont 17 suivis d'un `pass`.

**Fuite** — `error_response(str(e))` propage le texte brut de l'exception au client MCP : chemins de fichiers du conteneur, internes LadybugDB, éventuellement fragments de requête. Sur un endpoint public non authentifié, c'est de la divulgation d'information.

**Action** : exceptions typées (`SchemaError`, `EngagementNotFound`, `QueryRejected`) levées au niveau adaptateur, mappées vers l'enveloppe au niveau outil. Message générique au client + identifiant de corrélation, détail complet dans les logs serveur.

### P2-3 — Configuration de lint permissive et non représentative

`pyproject.toml` : `ignore = ["E402", "E501", "E702", "UP009", "W291", "W293"]`. Avec ces règles réactivées : **886** lignes trop longues, 117 lignes blanches contenant des espaces, 19 usages de `;`. Le lint « passe » parce qu'il ne regarde pas.

Avec un jeu de règles standard (`B`, `SIM`, `RET`, `ARG`) : 24 arguments de fonction inutilisés, 12 `try/except` supprimables, 9 appels de fonction en argument par défaut (`B008` — piège classique), 4 fichiers ouverts sans gestionnaire de contexte (`SIM115`, fuite de descripteurs), 1 `raise` sans `from` dans un `except` (`B904`, perte de la chaîne d'exception).

Point d'attention : avec `ruff 0.16`, `ruff check .` **échoue** sur `tests/integration/test_scenario_nordwave_mcx.py:239` (`UP031`). Le projet épingle `ruff = "^0.4.0"` et la CI installe `latest` via Poetry — mais la CI comme le script de déploiement exécutent `ruff check .` en étape bloquante. Selon la version résolue, `make lint` et `deploy_gcp.sh` peuvent être rouges.

**Action** : épingler la version exacte de ruff, activer `B` + `SIM` + `RET`, corriger les ~116 points auto-corrigeables (`--fix`), et traiter E501 par `line-length` plutôt que par ignorance de la règle.

### P2-4 — Conteneurisation et déploiement

**Quatre Dockerfiles** (`Dockerfile`, `docker/Dockerfile.cloudrun`, `docker/Dockerfile.mcp`, `docker/Dockerfile.pipeline`) pour un service. `cloudbuild.yaml` n'utilise que celui de la racine ; les autres dérivent en silence. `Dockerfile.cloudrun` installe les dépendances **dev et eval** (pas de `--without dev,eval`) et masque les échecs d'ingestion par `|| true`.

Sur le Dockerfile réellement utilisé :

- Mono-étage : `build-essential` et `g++` restent dans l'image finale (poids + surface d'attaque).
- Aucun `USER` : le conteneur tourne en **root**.
- Image de base non épinglée par digest (`python:3.11-slim`).
- `HEALTHCHECK` inopérant sur Cloud Run (ignoré par la plateforme).

Chaîne de livraison :

- Déploiement **manuel** depuis un poste (`scripts/deploy_gcp.sh` → `gcloud builds submit`). Aucun lien traçable entre un commit et la révision en production.
- Le script détecte un arbre de travail sale (étape 2) mais **continue quand même** : il est possible de déployer du code non committé.
- Tag `latest`, aucun déploiement par digest immuable, aucune procédure de rollback documentée.

**Action** : un seul Dockerfile multi-étage avec utilisateur non-root ; CD depuis GitHub Actions via Workload Identity Federation ; déploiement par digest ; `exit 1` sur arbre sale.

### P2-5 — Documentation contredite par le code

`.env.example` est le cas le plus net :

```
# Docker Compose reads .env automatically. The Python code does NOT
# (no python-dotenv), so for `poetry run ...` load it into the shell first
```

Or `python-dotenv` est une dépendance déclarée (`pyproject.toml`) et `load_dotenv()` est appelé à l'import de `mcp_server/config.py`. La documentation dit l'inverse du code.

Plus grave : `.env.example` documente **2 variables** (`OPENAI_API_KEY`, `OWNER_NOTIFICATION_WEBHOOK`) alors que le code en lit **12** — dont toutes les variables critiques de sécurité : `SERVER_TOKEN`, `LLMOPS_AUTH_TOKEN`, `ENGAGEMENT_TOKENS`, `GRAPH_BACKEND`, `LLMOPS_PLANE`, `LLMOPS_TRANSPORT`, `KUZU_DB_PATH`, `GITHUB_TOKEN`, plus `JWT_SECRET` côté application. Un nouveau contributeur ne peut pas démarrer un serveur correctement configuré à partir de ce fichier.

Incohérence secondaire : deux variables pour le même usage, `NOTIFICATION_WEBHOOK_URL` et `OWNER_NOTIFICATION_WEBHOOK`.

Autres écarts :

- Le README annonce les compteurs de démonstration pour « `data/knowledge.kuzu` » — chemin qui n'existe plus.
- `make demo` lance le serveur au premier plan (bloquant) ; `make demo-check` doit donc être lancé dans un second terminal, ce que le README ne dit pas. Le premier contact avec le projet est un blocage.
- `README.fr.md` fait 88 lignes contre 113 pour la version anglaise : dérive de contenu. La CI vérifie la présence du jeton de démo dans les deux, mais rien d'autre.

### P2-6 — Fichiers de travail internes exposés

`WORKORDER-NOTES.md` est un journal d'exécution de commande de travail (« Lot 0 — Déblocage légal », « Noticed but Deferred », erreurs `HTTP 401: Bad credentials` de `gh`). C'est un artefact de processus interne, pas de la documentation produit. Il révèle au passage que la **description et les topics GitHub du dépôt n'ont jamais été renseignés** — action différée jamais reprise, alors que c'est le premier élément de découvrabilité du projet.

**Action** : déplacer ce contenu vers des issues GitHub ou un `CHANGELOG.md`, et renseigner description + topics (`mcp`, `model-context-protocol`, `knowledge-graph`, `architecture-decision-records`, `graphrag`).

---

## 6. Constats mineurs (P3)

- **`scripts/import_graph.py:151-163`** : interpolation directe d'identifiants dans du Cypher (`f"MATCH (a1:Asset {{id: '{src}'}}) ..."`). Sur un script d'import alimenté par un JSON externe, une apostrophe dans un identifiant casse la requête, et un contenu hostile l'injecte. Les outils MCP, eux, sont correctement paramétrés — c'est le script qui fait exception.
- **`tools/elicitation/mailbox/renderers.py:17`** : environnement Jinja2 sans `autoescape`. La sortie est du Markdown (risque limité), mais du contenu client passe dans ces gabarits et sera rendu en HTML par l'application Svelte. Injection Markdown/HTML possible.
- **Cache de connexions non protégé** : `LadybugGraphStore._conn_cache` est un dictionnaire de classe partagé, sans verrou, alors que la docstring de `LadybugClient` annonce « Thread-safe client ». Avec `--concurrency=20` sur Cloud Run, plusieurs requêtes partagent la même connexion.
- **Suppression automatique du WAL** : `ladybug_store.py:38-41` supprime `<db>.wal` si le message d'erreur contient `"wal"` ou `"record type"`. Une récupération destructrice déclenchée par correspondance de sous-chaîne sur un message d'exception — à remplacer par un échec explicite et une procédure de récupération manuelle.
- **`close()` cosmétiques** : `ReadOnlyLadybugClient.close()` se réduit à `gc.collect()` ; `LadybugGraphStore.close()` fait des `del` dans des `try/except: pass`. La libération des ressources n'est pas garantie.
- **Données personnelles en dur** : `notifier.py:22-23` contient l'adresse e-mail personnelle du propriétaire et un lien d'invitation Discord. À déplacer en configuration.
- **Identifiants GCP dans le dépôt** : `deploy_gcp.sh` expose `PROJECT_ID="canvas-eye-403415"` et le numéro de projet dans l'URL. Acceptable pour une démo assumée, à externaliser pour tout usage sérieux.
- **`os._exit(0)`** dans `make demo-check` et dans la vérification de build du Dockerfile : court-circuite les gestionnaires de sortie et la fermeture des ressources. Fonctionne, mais masquera un jour une erreur de fermeture de base.
- **710 occurrences de `S101` (assert)** : normal dans les tests, mais à vérifier qu'aucun `assert` ne sert de contrôle en production (Python les supprime avec `-O`).
- **Aucune release** : un seul tag, `ready-for-test`. `docs/VERSIONING.md` définit une politique de version que le dépôt n'applique pas. Un intégrateur tiers n'a aucun point d'ancrage stable.
- **Bus factor = 1** : 50 commits, un seul auteur, aucun `CODEOWNERS` racine (il en existe un dans `data/kb/`), pas de template de PR, pas de Dependabot, pas de CodeQL.

---

## 7. Plan d'amélioration continue

### Sprint 1 — « Reprendre le contrôle de la surface d'exposition » (1 semaine)

| # | Action | Critère de sortie |
|---|---|---|
| 1 | Révoquer le webhook Discord | Nouveau webhook en Secret Manager, ancien invalidé |
| 2 | `gitleaks` en CI bloquant + pré-commit | CI rouge sur secret introduit |
| 3 | Propager `read_only` dans `get_database` | Test : une écriture sur connexion lecture est rejetée par la BD |
| 4 | Filtre Cypher en liste blanche (2ᵉ couche) | Test paramétré : `COPY`, `EXPORT`, `INSTALL`, `LOAD` rejetés |
| 5 | `authorise()` fermé par défaut | Test : `ENGAGEMENT_TOKENS` vide ⇒ tout engagement refusé |
| 6 | Séparer jeton et identité (`token → tenant`) | Un jeton nommé `admin` n'obtient pas les droits admin |
| 7 | Corriger `open_connection(caller=None)` | Test : jeton scopé A lit A, ne lit pas B |
| 8 | Aligner `SECURITY.md` et `cloudbuild.yaml` | Job CI de cohérence sur `LLMOPS_PLANE` |
| 9 | `JWT_SECRET` obligatoire au démarrage | L'app refuse de démarrer sans secret ≥ 32 car. |

### Sprint 2 — « Une seule source de vérité » (1 à 2 semaines)

| # | Action | Critère de sortie |
|---|---|---|
| 10 | Fusionner `Settings` et `ServerConfig` | Un seul module, préfixe `LLMOPS_`, 0 `os.getenv` hors tests |
| 11 | `/health` + `/ready` réels | `/ready` renvoie 503 si `Asset` = 0 |
| 12 | Rédiger et ingérer ADR-0014 / ADR-0015 | Test de contrat : 0 référence ADR pendante |
| 13 | Régénérer `.env.example` (12 variables) | Un contributeur démarre le serveur depuis ce seul fichier |
| 14 | Purger 117 fichiers suivis-et-ignorés + corpus 3GPP | `git ls-files -i -c` = 0 ; clone < 20 Mo |
| 15 | Réparer `ingest-kb.yml` (chemins `.lbug`, `GRAPH_BACKEND`) | Artefact non vide |
| 16 | Vérification réelle du sceau SHA-256 | Test recalculant le condensat + détection de dérive en CI |
| 17 | Job CI front-end (`svelte-check` + build) | PR bloquée sur régression Svelte |
| 18 | Supprimer `users.server.ts` et `prisma/dev.db` | Aucun identifiant en clair dans le dépôt |

### Sprint 3 — « Rendre le socle réutilisable » (2 à 3 semaines)

| # | Action | Critère de sortie |
|---|---|---|
| 19 | Exceptions typées + enveloppe sans détail interne | Aucun `str(e)` brut renvoyé au client |
| 20 | Ruff épinglé, `B`/`SIM`/`RET` activés, `--fix` appliqué | 0 erreur sur le jeu élargi |
| 21 | Couverture mesurée avec seuil (départ : niveau actuel) | `pytest --cov` bloquant sur régression |
| 22 | Dockerfile unique multi-étage, non-root | Une seule image, `USER` non privilégié |
| 23 | CD depuis GitHub Actions (WIF), déploiement par digest | Traçabilité commit → révision Cloud Run |
| 24 | Annoter le corpus 3GPP **ou** retirer la promesse | `compute_kappa.py` produit un chiffre, ou la doc est honnête |
| 25 | `v0.1.0` taguée, `CHANGELOG.md`, description + topics GitHub | Un tiers peut épingler une version |
| 26 | Dependabot + CodeQL + `bandit` | Alertes de dépendances actives |
| 27 | `WORKORDER-NOTES.md` → issues, parité README FR/EN | Doc produit ≠ journal de processus |

### Indicateurs à suivre

| Indicateur | Aujourd'hui | Cible 3 mois |
|---|---|---|
| Secrets détectés (historique + HEAD) | 1 actif | 0 |
| Couches de contrôle en écriture | 1 (regex) | 2 (BD + liste blanche) |
| Fichiers suivis *et* ignorés | 117 | 0 |
| Taille du clone | 157 Mo | < 20 Mo |
| Références ADR pendantes | 40 | 0 |
| Systèmes de configuration | 2 | 1 |
| Variables d'env documentées / utilisées | 2 / 12 | 12 / 12 |
| Lignes front-end couvertes par la CI | 0 | build + `svelte-check` |
| Cas d'évaluation annotés | 0 / 50 | 50 / 50 ou promesse retirée |
| Contributeurs distincts | 1 | ≥ 2 |

---

## 8. Recommandation transversale

Une seule idée à retenir si tout le reste est écarté : **appliquer au dépôt la discipline que le produit vend.**

Le produit affirme qu'un énoncé sans source vérifiable doit être marqué `assumed`, et qu'un document contenant des énoncés non mûrs doit se déclarer `is_provisional`. Le dépôt, lui, affirme sans source : `ADR-0015` n'existe pas, le sceau SHA-256 n'est pas vérifié, `SECURITY.md` décrit un déploiement obsolète, `read_only` est un paramètre décoratif, `.env.example` contredit le code.

Chacun de ces écarts se corrige par un test de contrat — et le projet sait déjà écrire des tests de contrat, il en a une suite entière. Le chemin le plus court vers la crédibilité n'est pas d'ajouter des fonctionnalités : c'est de retourner les mécanismes de vérification existants vers le dépôt lui-même. Un test « aucune référence ADR pendante », un test « le sceau se recalcule », un test « `SECURITY.md` correspond à `cloudbuild.yaml` » : trois tests courts qui transforment la thèse du projet en propriété démontrée plutôt qu'en argument marketing.

C'est aussi la meilleure démonstration commerciale possible. Un prospect qui constate que le dépôt applique à lui-même la traçabilité qu'il vend n'a plus besoin qu'on lui explique la valeur du produit.