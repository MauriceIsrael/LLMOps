# 🤖 Prototype d'Élicitation Pilotée par les Manques (`TPL-elicitation-proto`)

Ce module implémente le modèle de **Chatbot Inversé (Inverted-Chatbot Model)**. Le système connaît le schéma attendu d'un document projet, détecte les manques (`gaps`), interroge les experts métiers via une boîte aux lettres (`FileMailbox`), interprète leurs réponses en énoncés typés (`Statement`), s'interrompt pour validation humaine (`interrupt`), détecte les contradictions sous forme de conflits sans rien écraser, et rassemble le document d'architecture.

---

## 👥 Scénario d'Interaction à 3 Architectes

Ce scénario illustre l'interaction entre **3 architectes** et le système d'élicitation :
1. **Alice** (`cloud-architect`) : Répond sur l'infrastructure de stockage du cluster de management.
2. **Bob** (`storage-expert`) : Propose une solution alternative (HCI Ceph) générant un conflit déterministe.
3. **Charlie** (`chief-architect`) : Arbitre le conflit entre Alice et Bob, lève le statut `PROVISIONAL` et valide le document.

---

## 🎬 Déroulement du Scénario (Commandes à Copier-Coller)

### Étape 1 : Le système scanne le projet `demo-2026` et émet les questions
```bash
# Scan déterministe des manques (G1, G2, G3)
poetry run elicit scan --engagement demo-2026 --max-questions 8
```
*Le système génère `Q-0001` pour le stockage du cluster de management et l'envoie dans `projects/demo-2026/mailbox/questions/Q-0001.json`.*

---

### Étape 2 : Alice (`cloud-architect`) soumet sa réponse et le flux s'interrompt
```bash
# Alice répond qu'un SAN NVMe dual-controller est préconisé
poetry run elicit answer Q-0001 --author alice --role cloud-architect --text "Nous préconisons un SAN NVMe dual-controller tier-1."
```
*Le flux interprète la réponse en candidat `has_property = SAN NVMe dual-controller` et s'arrête sur l'étape `confirm` (LangGraph `interrupt`).*

```bash
# Alice confirme les énoncés extraits dans un NOUVEAU processus
poetry run elicit confirm Q-0001 --accept
```
*L'énoncé de certitude `verified` d'Alice est enregistré dans LadybugDB.*

---

### Étape 3 : Bob (`storage-expert`) soumet une réponse contradictoire
```bash
# Bob propose une architecture alternative sur la même section 5.2
poetry run elicit answer Q-0001 --author bob --role storage-expert --text "Le stockage doit s'appuyer sur un cluster Ceph HCI all-flash SSD."

# Bob confirme son énoncé
poetry run elicit confirm Q-0001 --accept
```
*Le système de détection déterministe de contradictions détecte un conflit entre Alice et Bob. Il crée le conflit `C-0001` sans écraser ni retirer l'énoncé d'Alice.*

---

### Étape 4 : Assemblage intermédiaire par le Système
```bash
# Assembler le document avec les conflits ouverts
poetry run elicit assemble --engagement demo-2026
```
*Le document est généré dans `projects/demo-2026/document.md` avec le statut `PROVISIONAL` et le registre des conflits affiché.*

```bash
# Lister les conflits ouverts
poetry run elicit conflicts --engagement demo-2026
```

---

### Étape 5 : Charlie (`chief-architect`) arbitre le conflit
```bash
# Charlie arbitre en faveur d'Alice et donne la raison d'architecture
poetry run elicit arbitrate C-0001 --keep S-1785078837800 --reason "Homogénéité du stockage SAN avec le datacenter existant" --by chief-architect

# Assembler le document final
poetry run elicit assemble --engagement demo-2026
```
*L'énoncé de Bob passe à `superseded`. Le document `projects/demo-2026/document.md` est validé au statut `COMPLETE`.*

---

## 🧪 Exécution des Tests d'Acceptation Automatisés

```bash
poetry run pytest tests/unit/test_elicitation.py -v
```

---

## 📝 Note de REX Harvest (Retours d'Expérience & Recommandations)

### Ce qui a été difficile :
1. **Durabilité LangGraph hors mémoire** : Garantir la persistance de l'interruption `interrupt` avec `SqliteSaver` entre deux processus Python distincts a exigé une sérialisation stricte de l'état `IntakeState`.
2. **Isolement des transactions LadybugDB** : La gestion des verrous et de l'ouverture en écriture `read_only=False` de LadybugDB nécessitait une libération explicite des connexions lors des transitions de processus.

### Ce que nous modifierions pour la mise en production :
1. **Webhooks Mailbox** : Remplacer `FileMailbox` par `GitHubIssuesMailbox` en écoutant les Webhooks d'issues GitHub/GitLab pour rendre la saisie des experts 100 % asynchrone sur leurs outils quotidiens.
2. **Multi-graphes LangGraph distribués** : Héberger le checkpointer LangGraph sur un cluster PostgreSQL (`PostgresSaver`) pour supporter la haute disponibilité et les élicitations multi-projets simultanées.
