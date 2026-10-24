# Tests : repartir d'une base propre

Une suite de tests n'est utile que si, **sur une copie neuve et avec les dépendances du verrou**, elle passe entièrement. Ce document
dit comment obtenir cette situation, ce qu'on doit y voir, et comment lire les écarts connus. Il a été écrit après un état des lieux où
la suite donnait des résultats différents selon la machine (voir « Pourquoi ce document »).

## Les trois règles

1. **Les dépendances viennent du verrou** (`poetry.lock`), jamais d'un `pip install` libre. Le moteur de graphe `ladybug` est borné
   dans `pyproject.toml` (`>=0.15.3,<0.21`) : la 0.21.0 renvoie `NULL` pour la ligne d'ancrage d'un `MATCH … OPTIONAL MATCH` quand la
   partie optionnelle ne trouve rien, sans erreur.
2. **Une exécution part d'une copie qui ne contient aucun reste d'une exécution précédente.** Les tests écrivent dans `data/`
   (le fichier versionné `data/engagements/nordwave-mcx-2027.lbug`, des bases ignorées par git, `data/suggestions/`). Une base écrite par
   une autre version du moteur n'est plus lisible par celle du verrou.
3. **Le résultat attendu est « zéro échec »**, et les tests ignorés sont connus et listés (voir plus bas). Un échec n'est jamais
   « normal » : on le corrige, ou on ouvre une issue qui le nomme.

## Ce que contient la suite

| Dossier | Contenu | Lancé par `make test-all` |
|---|---|---|
| `tests/unit` | règles pures, schémas, instantanés, garde-fous (dont `test_ladybug_version_guard.py`) | oui |
| `tests/contract` | formes d'interface figées (`tests/contract/frozen/`), fixtures, enveloppes | oui |
| `tests/integration` | API REST/MCP réelles sur une base de test, gouvernance SQLite | oui |
| `tests/e2e` | scénarios de la démonstration de référence (lisent `examples/`) | oui |
| `tests/bench`, `tests/eval` | bancs et évaluations déterministes | oui |
| `tests/evals` | évaluations DeepEval : exigent `deepeval` et un modèle | **non** (`--ignore=tests/evals`) |

`make test` (ancien) n'en lance qu'une partie ; `make verify` ne lance que lint + types + contrat + unitaires, **pas** les
tests d'intégration. Le crochet pre-push (`make hooks`) est plus léger encore : `make quick` (ruff + garde des noms de projet, quelques
secondes). Les tests, c'est la CI ; en local, un test ciblé suffit (`pytest tests/unit/test_xxx.py -k …`). Pour la suite complète : `make test-all`.

## Procédure A : copie propre, en local

```bash
# 1. Une copie neuve du code, sans aucun reste d'exécution (ni dans le dépôt de travail, ni dans ses fichiers ignorés)
git worktree add ../llmops-clean HEAD          # ou : git clone <dépôt> llmops-clean
cd ../llmops-clean

# 2. Les dépendances du verrou, et rien d'autre
poetry install --with dev                       # ajouter « --with dev,eval » pour pouvoir collecter tests/evals
make test-env-check                             # échoue avec un message clair si le moteur de graphe est hors borne

# 3. La suite complète
make test-all
```

Dans un dépôt de travail existant, au minimum : `git checkout -- data/` (restaure le fichier versionné), puis
`git clean -ndX data/` pour **voir** les fichiers ignorés qui traînent (retirer l'option `-n` pour les supprimer). Une copie neuve est
plus sûre qu'un nettoyage.

## Procédure B : Docker (machine sans environnement Python maîtrisé)

```bash
make test-docker
# équivaut à :
docker build -f docker/Dockerfile.test -t llmops-test:latest .
docker run --rm llmops-test:latest
```

L'image installe `poetry.lock` (Python 3.11, la version des images déployées), copie le dépôt, et lance la même sélection que
`make test-all`. Chaque `docker run` repart d'un système de fichiers neuf : aucun reste possible.

- Arguments pytest au choix : `docker run --rm llmops-test:latest pytest tests/unit -k k17 -q`.
- Avec les évaluations : `docker build --build-arg WITH_EVAL=1 -f docker/Dockerfile.test -t llmops-test:eval .` puis
  `docker run --rm llmops-test:eval pytest tests/evals -q`.
- `.dockerignore` exclut `.git` : les tests qui interrogent git retombent sur leur valeur de repli (`unknown`).

> **État de cette procédure** : la procédure A a été exécutée de bout en bout. L'image de la procédure B a été écrite mais **pas
> construite** (l'environnement de rédaction n'avait pas de démon Docker) : la première construction sur votre machine est sa
> vérification. Si elle révèle une dépendance système manquante ou un test qui suppose `.git`, corrigez l'image et ce paragraphe.

## Résultat attendu

Voir la section « Dernier état connu » en bas de ce document. Les tests ignorés (`s`) sont ceux qui exigent une ressource absente :
modèle d'embedding local (`KB_SEMANTIC_EVAL=1`), serveur d'engagement réel, etc.

## Lire un échec : les symptômes connus

| Symptôme | Cause | Remède |
|---|---|---|
| `test_ladybug_version_guard` échoue ; ou `st_id` vaut `None` dans `test_contract_optional_match_and_nulls` ; ou `get_compliance_matrix` : `'in <string>' requires string as left operand, not NoneType` | moteur `ladybug` ≥ 0.21 installé hors du verrou | reconstruire l'environnement : `poetry install` (ou Docker) |
| `Trying to read a database file with a different version. Database file version: 47, Current build storage version: 43` | une base `.lbug` écrite par un moteur plus récent est restée dans `data/` | copie neuve ; sinon `git clean -ndX data/` puis supprimer les bases ignorées |
| `ERROR collecting tests/evals/semantic/...: No module named 'deepeval'` ; `pytest` s'interrompt avant d'exécuter quoi que ce soit | groupe de dépendances `eval` non installé | `--ignore=tests/evals` (c'est ce que fait `make test-all`) ou `poetry install --with dev,eval` |
| `Fixture knowledge_snapshot.json is stale!` | la version du contrat a changé, ou le contenu des fixtures | voir « Quand on change le contrat » |
| `git status` montre `data/engagements/nordwave-mcx-2027.lbug` modifié après les tests | des tests ouvrent en écriture la base versionnée | `git checkout -- data/` ; ne pas committer ce fichier |

## Quand on change quelque chose

- **On change la version du contrat** (`mcp_server/core/version.py`) : les fixtures la contiennent. Régénérer **dans une copie neuve**
  (sinon des moteurs ou des bases locales s'y glissent) :

  ```python
  # depuis la racine d'une copie neuve, avec l'environnement du verrou
  from pathlib import Path; import tempfile
  from scripts.export_fixtures import export_fixtures
  export_fixtures(engagement="nordwave-mcx-2027", output_dir=Path("fixtures"), snapshot_dir=Path(tempfile.mkdtemp()))
  ```

  puis ne garder que les fichiers dont le contenu **réel** a changé (les horodatages `created_at` / `updated_at` et l'identifiant du
  snapshot scellé sont ignorés par le test ; ne pas les committer pour rien). `snapshot_dir` hors dépôt évite de publier un
  snapshot et de toucher au registre des versions. Ne **jamais** committer `data/engagements/*.lbug` qui en résulte.
- **On ingère un référentiel** (`kb ingest-framework`) : le nombre de contrôles change. Les tests ne figent aucun total ; ils vérifient
  que chaque contrôle écrit à la main est mis en œuvre par un actif et que le rapport rend compte de chaque contrôle une fois.
- **On veut monter `ladybug`** : installer la version visée hors du verrou dans une copie neuve, lancer `make test-all` ;
  `test_contract_optional_match_and_nulls` et `test_get_compliance_matrix` sont les canaris. Ne relever la borne de `pyproject.toml`
  (puis `poetry lock`) que si toute la suite passe, et seulement alors. La 0.20.x a passé les canaris ; la 0.21.0 à la 0.21.2 non.
- **On ajoute un test qui écrit dans `data/`** : il doit travailler sur une copie temporaire (`tmp_path`), pas sur le dépôt.

## Pourquoi ce document

Un état des lieux (octobre 2026) a montré qu'aucune version du moteur de graphe ne faisait passer toute la suite sur une machine
« ordinaire » : avec le verrou (0.19.1), des tests passaient mais certaines bases laissées par une exécution avec un moteur plus récent
devenaient illisibles ; avec le moteur le plus récent (0.21.2), trois tests échouaient pour une raison de fond. S'y ajoutaient des
compteurs figés sur la taille de la base de connaissances, des fixtures produites sous Windows (chemins en `\`), un `pytest` nu qui
s'interrompait à la collecte, et un `.dockerignore` qui excluait `poetry.lock` (les images se construisaient donc sans le verrou).
Tout ce qui précède est corrigé ou nommé ici.

## La CI

`.github/workflows/tests.yml` s'exécute sur chaque PR et sur `main` : Python 3.11, dépendances de `poetry.lock` (Poetry 2.5.1),
puis `ruff`, `scripts/check_no_project_names.py`, `mypy`, la garde de version du moteur de graphe, et la suite de ce document
(`pytest tests --ignore=tests/evals`). C'est `make lint` suivi de `make test-all`, sur un clone propre.

- **Elle est utile si elle est exigée** : dans les réglages du dépôt (Branches → règle de protection de `main`), cocher « Require status
  checks to pass » et choisir `tests`. Sans cela elle informe, elle n'empêche rien.
- **Après une publication de base de connaissances** (`kb publish`, `kb apply-review`) : les fixtures et le snapshot scellé changent ; la CI
  échoue tant que `fixtures/` n'est pas régénéré depuis une copie neuve (« Quand on change quelque chose »).
- **Le juge lit le graphe compilé, pas les fichiers** (issue #85) : après toute modification de `data/kb`, reconstruire le graphe
  (`poetry run ingest --kb-dir data/kb`, ou `kb publish`) et le **commiter avec les fichiers**. `poetry run kb check` dit si le graphe décrit
  les fichiers (`--strict` refuse aussi un graphe sans empreinte) ; `tests/integration/test_kb_consistency.py` le vérifie sur le dépôt : la CI échoue si le graphe
  versionné est périmé, et le test se saute tant qu'il n'a pas d'empreinte (la prochaine publication le reconstruit). Le serveur avertit au démarrage et `GET /api/knowledge/health` (`compiled_base`) le rapporte ; il ne reconstruit jamais seul.
- **Montée de version du moteur de graphe ou de Python** : changer `python-version` ici et dans `docker/Dockerfile.test` ensemble.

## Vérification croisée avec le Document Engine (`make verify-suite`)

Le Document Engine est un dépôt voisin (`../document-engine`, ou `DOCUMENT_ENGINE_DIR`) ; il faut y avoir lancé `npm ci`. Le script `scripts/verify_suite.py`
n'écrit rien dans l'un ni l'autre dépôt. Il rejoue **avec le code du Document Engine** : (1) l'identité octet pour octet des vecteurs `canonical-json` ;
(2) le recalcul du `checksum` des témoins du Hub (`tests/fixtures/suite/conformity-snapshot.golden.json`, reconstruit par
`tests/contract/test_conformity_golden.py`, et `schemas/examples/engagement_snapshot.example.json`) ; (3) le verdict de son lecteur de conformité sur le témoin de
conformité.

Le verdict attendu aujourd'hui est un **refus de provenance** (`knowledge-hub` n'est pas admis, ADR-DE-41) : c'est un test de refus, il passe. Le jour de
l'admission, il change, le script échoue, et `EXPECTED_READER_REFUSAL` doit être mis à jour avec la preuve (issue #152). Codes de sortie : `0` tout vérifié et
conforme, `1` écart, **`3` non vérifié** (dépôt, node ou `npm ci` absents) : jamais un vert silencieux quand rien n'a été comparé. Cette cible n'est pas dans
`make test-all` : elle exige un autre dépôt.

Régénérer le témoin de conformité après un changement de l'émetteur : `CONFORMITY_WRITE_GOLDEN=1 poetry run pytest tests/contract/test_conformity_golden.py`.

## Le canal de propositions avec le schéma de la suite (`make verify-proposals`)

Même idée que `verify-suite`, pour le canal suite → Hub (K7) : `scripts/verify_proposals.py` relit chaque candidate de `schemas/examples/proposal_snapshot.example.json` avec `extractedCandidateSchema`
de Requirements Intake (dépôt voisin `../requirements-intake`, ou `REQUIREMENTS_INTAKE_DIR` ; `npm ci` fait). Le schéma du Hub lisant ces champs comme facultatifs, il ne suffit pas à prouver qu'un émetteur réel passe.
Codes de sortie : `0` conforme, `1` candidate refusée, `3` non vérifié. Il ne prouve pas qu'un émetteur existe (`docs/contracts/proposals-emitter-guide.md`).

## Ce que cette procédure ne couvre pas

- **La CI (`.github/workflows/tests.yml`) lance la suite complète, pas les évaluations avec modèle ni les clients.** Les tests « live » d'Archinex contre le serveur de contrat ne tournent pas ici (voir plus haut) ; une PR qui change ce que ces clients lisent doit les rejouer à la main. Le crochet pre-push, lui, ne lance que lint + contrat + unitaires.
- Les évaluations avec modèle (`tests/evals`) ne sont ni lancées par défaut ni mesurées ici.
- Les résultats ont été obtenus sous Python 3.13 (procédure A) ; l'image Docker vise 3.11 (voir l'état de la procédure B).

## Dernier état connu

Exécution en **copie neuve** (`git worktree`), Python 3.13, dépendances du verrou (`ladybug` 0.19.1), `make test-all` :

| | |
|---|---|
| Tests | 1331 |
| Échecs | **0** |
| Ignorés | 6, tous documentés : modèle d'embedding local absent (4, `KB_SEMANTIC_EVAL=1`), backend SQL seulement (1), « le vrai blueprint n'est pas encore dans le dépôt » (1) |
| Durée | environ 8-10 minutes |

Contre-épreuve sur le moteur : la même suite, sur `main` avant ces corrections et avec `ladybug` **0.20.4**, ne donne que les trois
échecs de tests périmés corrigés ici (compteurs de `compliance_mapper`, fixtures en chemins Windows) ; la 0.20.x est donc compatible.
Avec la **0.21.2** : trois échecs de fond (`OPTIONAL MATCH`, `get_compliance_matrix` et sa forme figée). C'est pourquoi la borne
est `<0.21`.
