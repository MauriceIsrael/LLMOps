# ADR-KH-02 — Ontologie fédératrice en fichier compagnon du glossaire (schéma d'identifiants, périmètre expérimental)

**Statut** : `proposed` (cadre expérimental EDP)  
**Date** : 2026-10-29  
**Auteur** : @maintainers (Knowledge Hub)  
**Contexte & Épique** : Issue #165 (LLMOps) / Issue #166 (Archinex)  
**Dépôt** : LLMOps (Hub), `docs/adr/`

---

## 1. Contexte & Problématique

Le glossaire actuel du Knowledge Hub (`data/kb/glossary/glossary.md` complété par `data/kb/glossary/synonyms.yaml`) remplit un rôle essentiel de référentiel lexical pour les humains et les modèles (injection de contexte RAG, alignement de vocabulaire).

Cependant, pour l'Enterprise Decision Plane (EDP) et la plateforme Archinex, un vocabulaire textuel libre ne suffit plus à assurer la **vérification statique déterministe** des décisions d'architecture (HLD) :
1. Les vérifications ne doivent dépendre ni d'adresses IP réelles, ni d'inventaires d'infrastructure (LLD) inexistants au stade de la conception.
2. Un contrat sémantique formel est nécessaire entre **l'espace conceptuel** (Archinex, raisonnant en intension, zones logiques, fonctions et flux) et **l'espace d'implémentation** (Nautobot, Kubernetes/Cilium, SUSE Sylva CAPI, Ansible, OpenTelemetry), où chaque outil exploite sa propre taxonomie technique.
3. Le contrat de stabilité K3 (`{knowledgeKey, version}`) et le snapshot scellé (`data/snapshots/latest.json`) garantissent l'invariance absolue des octets pour les consommateurs de production. L'ontologie ne doit donc en aucun cas altérer ou polluer les structures de production avant sa promotion formelle.

---

## 2. Décisions Fondatrices

### 2.1 Répertoire compagnon `data/kb/ontology/` et étanchéité du glossaire
L'ontologie fédératrice est hébergée dans un répertoire compagnon dédié : `data/kb/ontology/`.
- Le glossaire existant (`data/kb/glossary/glossary.md`) et le dictionnaire de synonymes (`data/kb/glossary/synonyms.yaml`) demeurent **strictement inchangés**.
- Aucune régression : tant que le drapeau expérimental `LLMOPS_EXPERIMENTAL_ONTOLOGY=1` n'est pas activé, aucun fichier de `data/kb/ontology/` n'est chargé par le moteur de doctrine ou les APIs du Hub.

### 2.2 Schéma d'identifiants canoniques : clé de connaissance & URN
Pour s'intégrer harmonieusement avec le formalisme `KnowledgeRef` (`type:slug`) et les exigences de citation sémantique de l'EDP, deux représentations canoniques bijectives sont arrêtées :

1. **Clé de connaissance (`knowledgeKey`)** :
   ```
   ontology:<concept_class>:<slug>
   ```
   Exemple : `ontology:ComputeSubstrate:bare_metal_k8s` ou `ontology:SecurityZone:signaling`.
   Cette forme s'aligne fidèlement sur la syntaxe de référence `type:slug` utilisée par le Knowledge Hub pour tous ses actifs (`pattern:PAT-001`, `principle:P-001`).

2. **Alias URN citable (`urn`)** :
   ```
   urn:llmops:ontology:<concept_class>:<slug>
   ```
   Exemple : `urn:llmops:ontology:ComputeSubstrate:bare_metal_k8s`.
   L'URN est l'identifiant strict porté par le champ `id` des fichiers YAML d'entrée.

**Aller-retour bijectif un-pour-un** :
- `to_knowledge_key(urn)` :  
  `urn:llmops:ontology:<classe>:<slug>` $\rightarrow$ `ontology:<classe>:<slug>` (en ôtant le préfixe fixe `urn:llmops:`).
- `to_urn(knowledge_key)` :  
  `ontology:<classe>:<slug>` $\rightarrow$ `urn:llmops:ontology:<classe>:<slug>` (en préfixant par `urn:llmops:`).

### 2.3 Classes de concepts initiales
Le périmètre d'amorçage s'appuie sur une énumération fermée de 6 classes de concepts fondamentales :
1. `SecurityZone` : Zone de sécurité logique (ex. zone de signalisation, zone plan utilisateur, internet public).
2. `NetworkFunction` : Fonction réseau virtualisée, conteneurisée ou physique (ex. AMF, UPF, SMF).
3. `ComputeSubstrate` : Substrat d'exécution d'infrastructure (ex. bare-metal K8s, VM virtualisée).
4. `DataClassification` : Niveau de sensibilité et gouvernance de la donnée (ex. restreint, public, souverain).
5. `TrafficFlow` : Classe ou protocole de flux de trafic entre zones (ex. 3GPP SBA Control, OAM).
6. `Actor` : Rôle ou entité opérationnelle interagissant avec le système.

### 2.4 Projections taxonomiques et autorité de validation
Chaque entrée d'ontologie peut déclarer un dictionnaire de projections techniques par outil cible :
- `nautobot` : tags, rôles ou attributs DCIM Nautobot.
- `kubernetes_cilium` : labels de pods/namespaces et sélecteurs de NetworkPolicies Cilium.
- `suse_sylva_capi` : classes de clusters Cluster API, profils matériels Metal3 ou templates d'OS.
- `ansible` : groupes d'inventaire ou variables de rôles.
- `otel_semconv` : attributs OpenTelemetry Semantic Conventions.

**Validation des projections** :  
Une projection engage les règles de génération d'infrastructure de la suite. Par conséquent, une projection **ne peut pas** être validée par le seul rédacteur de l'entrée. Sa validation requiert obligatoirement la relecture d'un expert du domaine ou d'un mainteneur habilité (`kb:maintain` ou propriétaire de domaine désigné), formalisée par les métadonnées `reviewed_by` et `reviewed_at`.

### 2.5 Cycle de vie et versionnement des entrées
Chaque entrée d'ontologie respecte le cycle de vie formel :
- `status` : `draft` | `validated` | `rejected`
- `revision` : entier strictement positif ($1, 2, 3, \dots$).
- Registre de révisions : un ledger dédié `data/kb/ontology/version-ledger.json` enregistre le condensat SHA-256 du contenu canonique de chaque révision publiée d'une entrée.
- Règle de non-altération (analogue à K3) : une révision publiée ne peut plus jamais voir son contenu ni ses projections modifiés sans incrément de `revision`.

### 2.6 Intégrité référentielle stricte
Toutes les relations logiques (`isolated_from`, `forbids_substrate`, `requires_capabilities`, `allowed_traffic_classes`) doivent pointer exclusivement vers des URNs valides et déclarées dans l'ontologie.
- Les relations du PoC (ex. `urn:llmops:ontology:ComputeSubstrate:virtualized_vm`, `urn:llmops:ontology:ComputeSubstrate:oob_redfish`, `urn:llmops:ontology:ComputeSubstrate:realtime_kernel`) doivent obligatoirement disposer d'une entrée déclarée dans le référentiel pour que l'ontologie soit réputée intègre.
- Les relations d'isolation (`isolated_from`) doivent être réflexivement interdites (une zone ne s'isole pas d'elle-même) et être symétriques par défaut, sauf déclaration explicite d'asymétrie.

### 2.7 Déterminisme et absence d'inférence serveur
Le noyau d'ontologie du Knowledge Hub est strictement déterministe. Il ne réalise aucun appel réseau, aucune résolution dynamique heuristique et aucun appel LLM à l'évaluation ou au chargement.

---

## 3. Ce qui NE change pas (Garanties de non-régression)

1. **Snapshot scellé inchangé** :  
   `data/snapshots/latest.json` et son `payload_sha256` demeurent absolument identiques. L'ontologie n'est pas injectée dans le snapshot de production du Hub.
2. **Registre de versions stable inchangé** :  
   Le ledger général `version-ledger.json` du Hub ne contient pas les entrées d'ontologie tant que l'EDP est au stade expérimental.
3. **Réponses des APIs et outils MCP existants** :  
   En l'absence du drapeau d'environnement `LLMOPS_EXPERIMENTAL_ONTOLOGY=1`, aucun endpoint d'ontologie n'est exposé et aucune réponse du Hub ne varie, assurant une stricte identité octet pour octet.

---

## 4. Conséquences

- **Positives** :  
  - Permet à Archinex de vérifier formellement les architectures HLD contre un référentiel sémantique typé.
  - Préserve intégralement la rétrocompatibilité et l'isolation du cycle de vie de production du Knowledge Hub.
- **Engagements** :  
  - Maintenir un outillage de contrôle rigoureux (`kb check --experimental-ontology`).
  - Gérer l'export scellé dédié `ontology_export.json` séparé du snapshot principal.
