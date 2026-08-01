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

### Visualiseur Web local

```bash
poetry run visualize
```

*Ouvrez [docs/graph_explorer.html](file:///home/momo/Dev/LLMOps/docs/graph_explorer.html) dans votre navigateur.*

### Visualiseur Web GCP Cloud Run en direct

👉 **`https://llmops-mcp-server-344571265365.europe-west1.run.app/visualize?token=llmops-token-2026-sec-98a41f`**

---

## 🤖 4. Élicitation Collaborative (Chatbot Inversé)

Le système d'élicitation (`elicit`) permet à une équipe d'architectes de compléter déterministement les dossiers d'architecture.

### A. Mode CLI (Hors-ligne / Démo avec drapeau d'usurpation `--as`)

Grâce au drapeau d'usurpation `--as <login>` (`--as alice`, `--as bob`, `--as charlie`), **une seule personne peut simuler l'interaction de 3 personnes** sans créer de comptes GitHub !

```bash
# 1. Détecter les manques du projet et poser les questions dans la boîte aux lettres
poetry run elicit scan --engagement nordwave-mcx-2027

# 2. Réponse d'Amina (mcx-service-architect) via une fiche Markdown ou CLI
poetry run elicit answer Q-0001 --from-file artifacts/nordwave-mcx-2027/mailbox/Q-0001.md --as amina

# 3. Validation de la proposition d'extraction (Interrupt / Human-in-the-loop)
poetry run elicit confirm Q-0001 --accept

# 4. Observer la trajectoire d'un sujet (Level Gate & historisation)
poetry run elicit trajectory --engagement nordwave-mcx-2027 --subject mcx-services

# 5. Rétrogradation de maturité (Demotion non-monotone) si remise en cause
poetry run elicit demote --engagement nordwave-mcx-2027 --subject floor-control --to-level L2_decomposed --by sofia --reason "Révision nécessaire"

# 6. Soumettre une contribution externe terrain (double confirmation)
poetry run elicit contribute --engagement nordwave-mcx-2027 --file demo/answers/contribution.md --as rui

# 7. Arbitrage par Sofia (chief-architect) via --as sofia
poetry run elicit arbitrate C-0001 --keep S-0001 --reason "Arbitrage MCX service layer au site" --as sofia

# 8. Assembler le document final (projects/nordwave-mcx-2027/document.md)
poetry run elicit assemble --engagement nordwave-mcx-2027
```

### B. Mode Test d'Intégration Référent (Scénario Nordwave MCX v2)

Pour exécuter la démonstration automatisée complète couvrant les 6 phases et 18 tests d'élicitation :

```bash
poetry run pytest tests/integration/test_scenario_nordwave_mcx_v2.py -v
```

---

## 📢 5. Comment utiliser la Plateforme

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

1. **Déclarer vos collaborateurs dans le fichier d'annuaire `projects/demo-2026/roster.yaml`** :

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
