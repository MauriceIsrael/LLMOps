# Guide de Rédaction et de Relecture d'une Entrée d'Ontologie

Ce guide formalise les règles de rédaction, de validation et de gouvernance des entrées d'ontologie fédératrice dans le Knowledge Hub (cadre expérimental EDP, issues #165-#175).

---

## 1. Quand créer une entrée d'ontologie vs utiliser le glossaire

| Critère | Glossaire (`data/kb/glossary/`) | Ontologie fédératrice (`data/kb/ontology/`) |
|---|---|---|
| **Rôle principal** | Référentiel lexical pour humains et invite LLM (RAG). | Contrat sémantique formel pour vérification statique déterministe (EDP/Archinex). |
| **Contenu** | Définitions textuelles libres, acronymes, synonymes généraux. | Concept abstrait typé, relations logiques (`isolated_from`, `forbids_substrate`) et projections techniques vers l'infrastructure. |
| **Consommateur** | Prompt context, revue humaine, assistants généraux. | Option judge d'Archinex, moteurs de projection HLD $\rightarrow$ LLD (Nautobot, Cilium, Sylva, Ansible, OTel). |
| **Règle de décision** | Créer dans le glossaire si le terme clarifie le langage sans impacter les règles d'architecture ni la configuration des outils. | Créer dans l'ontologie dès qu'un concept d'architecture gouverne des règles d'isolation ou doit être projeté dans la configuration d'un composant technique. |

---

## 2. Conventions de nommage et structure

### 2.1 Identifiants et Classes de concepts
Chaque entrée déclare une URN unique et non ambiguë :
```
urn:llmops:ontology:<concept_class>:<slug>
```
- `<concept_class>` : énumération fermée parmi :
  - `SecurityZone` : Zone de sécurité logique.
  - `NetworkFunction` : Fonction réseau logique ou conteneurisée.
  - `ComputeSubstrate` : Substrat d'exécution d'infrastructure.
  - `DataClassification` : Niveau de classification des données.
  - `TrafficFlow` : Classe ou protocole de flux de trafic.
  - `Actor` : Entité ou rôle opérationnel.
- `<slug>` : identifiant textuel lisible en snake_case (ex. `bare_metal_k8s`, `signaling`, `public_internet`).

### 2.2 Raisonnement en intension (sans instanciation)
Les entrées d'ontologie expriment des **concepts d'architecture généraux**.
- **Interdiction formelle** : aucune adresse IP réelle (IPv4 ou IPv6), aucun nom d'hôte ou FQDN spécifique d'un environnement (ex. `node01.prod.local`), aucun identifiant de machine physique.
- Définition claire et intensionnelle expliquant le rôle et les propriétés du concept.
- Au moins deux synonymes : un en français et un en anglais.

### 2.3 Projections taxonomiques
Les projections traduisent le concept abstrait dans la taxonomie de chaque outil cible :
- `nautobot` : rôles d'appareils, tags, profils de plateforme ou VRF DCIM.
- `kubernetes_cilium` : labels de pods/namespaces, ports et sélecteurs de NetworkPolicies.
- `suse_sylva_capi` : classes de cluster Metal3/CAPI, profils RKE2, profils d'OS RT.
- `ansible` : groupes d'inventaire ou rôles.
- `otel_semconv` : attributs OpenTelemetry Semantic Conventions.

Toute projection doit être vérifiable contre une documentation officielle versionnée de l'outil ou un banc de test / laboratoire qualifié.

---

## 3. Checklist de relecture obligatoire

Toute Pull Request ajoutant ou modifiant une entrée dans `data/kb/ontology/` doit impérativement valider cette checklist :

- [ ] **Définition intensionnelle** : la définition décrit les propriétés conceptuelles sans aucune adresse IP, nom d'hôte ou valeur d'instanciation LLD.
- [ ] **Intégrité référentielle** : chaque URN citée dans `relationships` existe dans `data/kb/ontology/`.
- [ ] **Symétrie de l'isolation** : si `A` est `isolated_from: [B]`, alors `B` déclare également `isolated_from: [A]` (sauf asymétrie expressément documentée), et `A` n'est pas isolé de lui-même.
- [ ] **Synonymes bilingues** : au moins un synonyme en français et un en anglais, sans collision avec une autre entrée.
- [ ] **Preuve de la projection** : le champ `review_source` contient le lien vers la documentation officielle versionnée ou le procès-verbal de validation en lab d'intégration.
- [ ] **Relecteur qualifié** : le champ `reviewed_by` désigne un expert du domaine ou mainteneur habilité (la projection ne peut être validée par le seul rédacteur).
- [ ] **Contrôles exécutés avec succès** :
  ```bash
  poetry run kb check --experimental-ontology --strict
  ```
- [ ] **Registre de révisions** :
  ```bash
  poetry run kb ontology record
  ```
