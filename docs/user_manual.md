# 📗 Manuel Utilisateur — Plateforme LLMOps (GraphRAG + FastMCP + Élicitation)

Ce manuel fournit toutes les instructions nécessaires pour installer, alimenter, utiliser, visualiser et partager la plateforme LLMOps neuro-symbolique et son système d'élicitation collaboratif.

---

## 📋 1. Prérequis & Installation

### Prérequis Système
- Linux / macOS / WSL2
- Python `>= 3.11`
- [Poetry](https://python-poetry.org/docs/#installation)
- Docker & Docker Compose (Optionnel)

### Clé d'API LLM
Exposez votre clé OpenAI pour l'extraction LlamaIndex :
```bash
export OPENAI_API_KEY="sk-..."
```

### Installation
```bash
cd LLMOps
poetry install
```

---

## 🔄 2. Ingestion de la Base de Connaissances (GraphRAG)

```bash
poetry run ingest --kb-dir data/kb --db-path data/kuzu_db
```
- Ingestion des fichiers Markdown (`.md`) et des spécifications YAML (`.yaml` / `.yml`).
- Filtrage automatique des fichiers de prose sans `id` (`README.md`, `CONTRIBUTING.md`, etc.).

---

## 🎨 3. Visualisation du Graphe & Plans de Connaissance

### Visualiseur Web local :
```bash
poetry run visualize
```
*Ouvrez [docs/graph_explorer.html](file:///home/momo/Dev/LLMOps/docs/graph_explorer.html) dans votre navigateur.*

### Visualiseur Web GCP Cloud Run en direct :
👉 **`https://llmops-mcp-server-344571265365.europe-west1.run.app/visualize?token=llmops-token-2026-sec-98a41f`**

---

## 🤖 4. Élicitation Collaborative (Chatbot Inversé)

Le système d'élicitation (`elicit`) permet à une équipe d'architectes de compléter déterministement les dossiers d'architecture.

### A. Mode CLI (Hors-ligne / Démo)

```bash
# 1. Détecter les manques du projet et poser les questions dans la boîte aux lettres
poetry run elicit scan --engagement demo-2026

# 2. Un architecte (ex: Alice) répond
poetry run elicit answer Q-0001 --author alice --role cloud-architect --text "SAN NVMe dual-controller tier-1"

# 3. Validation de la proposition d'extraction (interrupt) dans un nouveau processus
poetry run elicit confirm Q-0001 --accept

# 4. Un 2ème architecte (Bob) propose une alternative -> Le système crée un conflit déterministe C-0001
poetry run elicit answer Q-0001 --author bob --role storage-expert --text "Ceph HCI all-flash SSD"
poetry run elicit confirm Q-0001 --accept

# 5. Charlie (Chief Architect) arbitre le conflit avec une raison d'architecture
poetry run elicit arbitrate C-0001 --keep S-1785078837800 --reason "Homogénéité du stockage SAN" --by chief-architect

# 6. Assembler le document final (projects/demo-2026/document.md)
poetry run elicit assemble --engagement demo-2026
```

---

## 📢 5. Comment Partager la Plateforme à vos Collègues

### Option 1 : Partager l'accès au Serveur MCP (Claude Desktop / Cursor / Antigravity / VS Code)
Transmettez simplement cet extrait de configuration à vos collègues pour qu'ils l'ajoutent dans leur fichier `mcp_config.json` local :

```json
{
  "mcpServers": {
    "llmops-architecture-kb": {
      "url": "https://llmops-mcp-server-344571265365.europe-west1.run.app/sse?token=llmops-token-2026-sec-98a41f"
    }
  }
}
```
*Vos collègues peuvent alors interroger directement la base d'architecture en langage naturel depuis leur IDE.*

---

### Option 2 : Partager le Visualiseur Web Interactif du Graphe
Transmettez ce lien direct à vos collègues pour qu'ils explorent la base de connaissances sans rien installer :
👉 **`https://llmops-mcp-server-344571265365.europe-west1.run.app/visualize?token=llmops-token-2026-sec-98a41f`**

---

### Option 3 : Partager l'Élicitation Collaborative sur GitHub Issues (Sans ligne de commande pour vos collègues !)

Vos collègues n'ont **rien à installer** sur leur poste. Ils répondent directement dans leur navigateur sur GitHub !

1. **Déclarer vos collègues dans le fichier d'annuaire `projects/demo-2026/roster.yaml`** :
   ```yaml
   - login: alice-gh
     name: Alice
     roles: [cloud-architect]
   - login: bob-gh
     name: Bob
     roles: [storage-expert]
   - login: charlie-gh
     name: Charlie
     roles: [chief-architect]
   ```

2. **Génération automatique des Issues GitHub** :
   Lorsqu'un scan tourne, le système crée une Issue GitHub privée avec la fiche Markdown complète, le tag du rôle assigné (ex: `role:cloud-architect`) et la commande pré-remplie `/answer Q-0001 --text "..."`.

3. **Vos collègues répondent par simple commentaire GitHub** :
   - Alice écrit un commentaire `/answer ...` puis `/confirm`.
   - Bob écrit un commentaire `/answer ...` pour proposer une alternative.
   - Charlie résout le conflit en commentant `/arbitrate keep S-0001 --reason "..."`.
