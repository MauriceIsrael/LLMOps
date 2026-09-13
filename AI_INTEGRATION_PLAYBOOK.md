# Playbook d'Intégration Inter-Dépôts & Constitution des Agents IA
## Architecture Suite & Knowledge Hub (LLMOps)

> **Statut** : Document de Gouvernance Opérationnelle & Directive Système  
> **Date d'effet** : 2026-09-13  
> **Origine** : Capitalisation issue de la *Revue à froid des propositions d'intégration du 2026-09-12* (4 issues et 3 PRs soumises aux dépôts `requirements-intake`, `document-engine`, `Document-studio`, `WBS-engine`).

---

## 1. Contexte et Raison d'Être

Lors des premières propositions d'intégration de LLMOps (Knowledge Hub) au sein des dépôts de l'*Architecture Suite*, plusieurs anomalies d'hygiène de code, de périmètre et de posture technique ont été identifiées par les mainteneurs de la suite :
* Fuite de chemins absolus de la machine hôte (`file:///home/momo/...`) et travail isolé dans des répertoires temporaires d'agent (`.gemini/.../scratch/`),
* Fichiers parasites committés dans les arbres Git des dépôts cibles (`PULL_REQUEST.md`),
* Altération unilatérale de contrats partagés (`channel-registry.md`, `vendored.manifest.json`) au sein de simples Pull Requests de fonctionnalité,
* Replis silencieux de type `catch { return []; }` masquant les pannes réseau ou d'authentification sous l'apparence de résultats vides,
* Types et structures de données inventés (`WBSNode`, `WBSData`) sans vérification préalable dans le code source cible,
* Fuite passive potentielle par déclenchement réseau non consenti à chaque frappe de clavier sur des documents CCTP sensibles.

Ce playbook édicte les **7 Règles d'Or** que **tout agent IA et tout développeur** doit impérativement respecter lors d'une contribution inter-dépôts.

---

## 2. Les 7 Règles d'Or de l'Intégration Inter-Dépôts

### Règle 1 : Règle du Clone Réel (Bannissement du Mode Scratch)
* **Obligation** : Tout travail de modification de code sur un dépôt de la suite (`Document-studio`, `document-engine`, `requirements-intake`, `WBS-engine`) ou sur `LLMOps` s'exécute **exclusivement dans un vrai clone Git**, situé dans l'arborescence standard de développement (`~/Dev/<nom-du-depot>`).
* **Interdiction** : Il est formellement interdit de cloner, modifier ou builder du code dans des dossiers temporaires ou caches d'agent (ex: `~/.gemini/antigravity/brain/.../scratch/`).
* **Zéro fuite d'URI locale** : Aucun chemin absolu hôte (`/home/momo/...`, `file:///...`, `C:\...`) ne doit jamais apparaître dans un commit, une PR, un log public ou une issue GitHub.

### Règle 2 : Zéro Artefact Parasite dans Git
* **Obligation** : L'arbre Git d'une branche de PR ne doit contenir **que** le code source métier, ses tests et sa documentation canonique.
* **Bannissement de `PULL_REQUEST.md`** : Les notes d'intention, brouillons de PR ou résumés générés par les modèles d'IA ne doivent **jamais** être committés dans le dépôt. Le texte d'une PR s'injecte via l'API GitHub (`gh pr create --body ...`) ou l'interface web.
* **Contrôle pré-commit** : Avant tout push, exécuter obligatoirement `git status` et `git diff --staged` pour vérifier l'absence de fichiers temporaires, de scripts jetables ou de résidus de build.

### Règle 3 : Inviolabilité des Contrats Partagés
* **Principe d'isolation** : Les dépôts de la suite partagent des contrats inter-composants (ex: `contracts/channel-registry.md`, `src/document-engine/vendored.manifest.json`). Ces contrats sont protégés par des témoins de parité et des empreintes cryptographiques SHA-256 synchronisées sur 6 dépôts.
* **Interdiction formelle** : Il est interdit de modifier un contrat partagé ou un manifeste d'empreinte dans une PR applicative ou de fonctionnalité.
* **Procédure dédiée** : Toute évolution d'un schéma partagé exige une PR de contrat dédiée, coordonnée, validée par l'ensemble des mainteneurs et régénérée par le tooling multi-dépôt officiel.

### Règle 4 : Sincérité et Rigueur de la Provenance
* **Signature canonique** : Tout snapshot, verdict de conformité ou donnée émise par le Knowledge Hub doit porter sa signature authentique :
  ```json
  {
    "sourceSystem": "knowledge-hub",
    "snapshotId": "kh-<engagement>-<framework>-<timestamp>"
  }
  ```
* **Interdiction d'usurpation** : Il est interdit de faire passer une réponse du Knowledge Hub pour celle d'un autre système tiers (comme Tuleap), sauf cas de bridge de compatibilité explicite documenté et activé par le paramètre `source_system=tuleap`.
* **Empreintes vérifiables** : Les condensats SHA-256 doivent être calculés selon la spécification stricte `canonical-json (v1)` et vérifiables par les suites de tests des dépôts consommateurs (cf. `tests/fixtures/canonical_conformity_vector.json`).

### Règle 5 : Résilience et Transparence « Fail Loud »
* **Bannissement des faux négatifs** : Les connecteurs HTTP et bridges ne doivent **jamais** étouffer les erreurs sous des listes vides :
  ```typescript
  // ❌ INTERDIT : Masque silencieusement les erreurs 401, 403, 500 et les pannes réseau
  try {
    return await api.getExtractedCandidates();
  } catch (e) {
    return []; // FAUX : Fait croire à l'utilisateur qu'il n'y a aucun résultat !
  }
  ```
* **Comportement requis (Fail Loud)** :
  ```typescript
  // ✅ REQUIS : Propager l'exception ou lever une erreur typée exploitable
  try {
    return await api.getExtractedCandidates();
  } catch (error) {
    throw new KnowledgeHubConnectionError(`Échec de récupération Hub (${error.status}): ${error.message}`);
  }
  ```
* L'utilisateur et le système appelant doivent savoir exactement si une liste est vide parce qu'il n'y a pas de donnée, ou parce que le service est indisponible ou non authentifié.

### Règle 6 : Vérification Réelle des ADRs, Types et Roadmaps
* **Zéro hallucination contractuelle** : Avant de proposer du code ou une issue, l'agent ou le développeur doit **lire le code existant** du dépôt cible. Il est proscrit d'inventer des types non existants (ex: `WBSNode`, `WBSData`) sans avoir vérifié les exports réels de `@architecture-suite/contracts`.
* **Respect des ADRs validées** : Prendre en compte les contraintes architecturales réelles du projet hôte. Exemple : `ADR-SUITE-05` impose un fonctionnement *offline-first* strict pour `requirements-intake` ; un appel réseau ne peut donc pas être bloquant dans le sas d'admission local.
* **Véracité des roadmaps** : Ne jamais promettre de jalons ou affirmer des dates non actées. Se référer au fichier `ROADMAP.md` réel du dépôt hôte.

### Règle 7 : Protection des Données & Anti-Fuite Passive
* **Contexte CCTP & Sensibilité** : Les documents traités dans l'Architecture Suite (CCTP, dossiers d'appels d'offres, exigences OIV/SecNumCloud) contiennent des données sensibles ou classifiées.
* **Interdiction de la recherche à la frappe non sollicitée** : Il est interdit d'émettre des requêtes HTTP vers le Hub à chaque frappe dans un champ de texte (keystroke streaming) sans debounce ni consentement explicite.
* **Déclenchement explicite** : Tout appel vers le Knowledge Hub doit résulter d'une action délibérée de l'utilisateur (clic sur « Interroger le Knowledge Hub », commande explicite ou raccourci clavier dédié).

---

## 3. Matrice de Référence des Dépôts de la Suite

| Dépôt | Rôle dans la Suite | Règle Clé d'Intégration |
|---|---|---|
| `requirements-intake` | Sas d'admission et curation des exigences | **Offline-First (ADR-SUITE-05)** : Le sas local fonctionne hors-ligne. L'extraction Hub (`POST /api/rfp/shred-to-candidates`) est asynchrone et hors du chemin critique d'admission. Destination : `knowledge-hub-reference`. |
| `document-engine` | Compilateur pur HLD / documents d'architecture | **Puretée du compilateur (ADR-DE-05)** : `compile()` reste 100% pur et offline. Le snapshot de conformité (`ConformityData`) est pré-chargé out-of-band avec `sourceSystem: "knowledge-hub"` et injecté en mémoire. |
| `Document-studio` | Interface graphique de modélisation et de rédaction | **Anti-fuite & Isolation** : Recherche Hub sur action explicite (bouton). Ne pas toucher à `channel-registry.md` ni `vendored.manifest.json`. Proxy Vite propre. |
| `WBS-engine` | Moteur de décomposition de tâches et WBS | **Lecture seule non intrusive** : Requêtage de `GET /api/skills/matrix` pour audit d'affectation. Ne pas modifier le canal scellé `wbs-snapshot`. |
| `LLMOps` (Knowledge Hub) | Base de connaissances vivante (MCP + REST) | **Double mode** : REST synchrone pour les UIs + Snapshots scellés pour les gates offline-first. API documentée dans `docs/contracts/knowledge-hub-api-v1.md`. |

---

## 4. Checklist Pré-Vol pour toute Intervention IA

Avant de valider ou soumettre un commit / une Pull Request :

- [ ] **Emplacement** : Le travail a-t-il été fait dans `/home/momo/Dev/<repo>` (et non sous `scratch/`) ?
- [ ] **Nettoyage** : A-t-on supprimé tout fichier temporaire (`PULL_REQUEST.md`, scripts `.sh`, `.py` jetables) ?
- [ ] **Hygiène Git** : Le `git diff` a-t-il été relu ligne par ligne ? Contient-il des chemins locaux ou des secrets ?
- [ ] **Contrats** : Les fichiers de contrats partagés (`channel-registry.md`, `vendored.manifest.json`) sont-ils intacts et conformes à `main` ?
- [ ] **Gestion d'erreur** : Tous les blocs `try / catch` propagent-ils l'erreur de manière explicite (*Fail Loud*) sans retour silencieux de tableau vide ?
- [ ] **Typage & Tests** : Les commandes locales de validation (`npm run lint`, `npm run typecheck`, `npm test` ou `poetry run pytest`) passent-elles à 100 % ?
- [ ] **Documentation** : Le `CHANGELOG.md` du dépôt hôte est-il renseigné au format exact attendu par ce dépôt ?

---

## 5. Directive Système pour les Agents IA (Prompt à Réutiliser)

Lorsqu'un agent IA est mandaté pour intervenir sur une tâche d'intégration liée à LLMOps ou aux dépôts partenaires, injecter la consigne suivante dans son contexte d'exécution :

```markdown
### DIRECTIVE SYSTÈME : RÈGLES DE COLLABORATION INTER-DÉPÔTS (PLAYBOOK ARCHITECTURE SUITE)

Tu interviens sur un dépôt de l'Architecture Suite (ou sur LLMOps). Tu DOIS respecter scrupuleusement les règles suivantes :
1. TRAVAIL EN CLONE RÉEL : Opère toujours dans le répertoire normal du dépôt (`~/Dev/<repo>`), jamais dans des répertoires temporaires ou scratch. Ne fais jamais fuiter de chemins machine hôte (`file:///...`).
2. ZÉRO ARTEFACT PARASITE : Ne crée ni ne committe JAMAIS de fichier `PULL_REQUEST.md` ou de scripts temporaires dans l'arborescence Git.
3. CONTRATS PARTAGÉS INTOUCHABLES : Ne modifie JAMAIS `contracts/channel-registry.md` ou `vendored.manifest.json` dans une PR de fonctionnalité. Ces fichiers nécessitent un protocole inter-dépôts dédié.
4. PROVENANCE AUTHENTIQUE : Signe toujours les données émises par le Hub avec `sourceSystem: "knowledge-hub"` et des identifiants `kh-...`.
5. FAIL LOUD : Ne masque jamais les pannes réseau ou d'authentification (401/500) avec des retours de listes vides (`catch { return []; }`). Lève des erreurs explicites.
6. ZÉRO HALLUCINATION : Vérifie les types TypeScript/Python réels dans le code du dépôt avant de les utiliser. Ne fabrique pas de faux types.
7. ANTI-FUITE : Privilégie un déclenchement explicite (bouton utilisateur) plutôt que des requêtes à la frappe sans debounce lors de la manipulation de CCTP sensibles.
```

