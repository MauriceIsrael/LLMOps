# LLMOps — Base de Connaissances d'Architecture Interrogeable en MCP

> Base de connaissances d'architecture interrogeable en MCP : chaque énoncé porte sa confiance et sa maturité, pour que vos générateurs de documents sachent ce qu'ils ont le droit d'affirmer.

[English Version (README.md)](README.md)

---

## Démarrage Rapide & Configuration Client MCP

Connectez n'importe quel client MCP (Claude Desktop, Cursor, Antigravity, VS Code) en 30 secondes.

### 1. Connexion Distante (GCP Cloud Run Serverless SSE)

Ajoutez la configuration suivante dans votre client MCP (ex: `claude_desktop_config.json` ou paramètres Cursor) :

```json
{
  "mcpServers": {
    "llmops-remote": {
      "url": "https://llmops-mcp-server-344571265365.europe-west1.run.app/sse",
      "headers": {
        "Authorization": "Bearer demo-public-2026-08"
      }
    }
  }
}
```

### 2. Connexion Locale (STDIO via Poetry)

```json
{
  "mcpServers": {
    "llmops-knowledge": {
      "command": "poetry",
      "args": ["run", "mcp-server-knowledge"],
      "cwd": "/chemin/vers/LLMOps"
    },
    "llmops-engagement": {
      "command": "poetry",
      "args": ["run", "mcp-server-engagement"],
      "cwd": "/chemin/vers/LLMOps"
    }
  }
}
```

### 3. Démonstration en Une Commande

```bash
make demo
make demo-check
```

**Nombres de Nœuds Attendus (`make demo-check`) :**
- **Plan de Connaissances (`data/knowledge.kuzu`)** : `Asset`: ~46 nœuds, `GlossaryTerm`: ~10 nœuds.
- **Plan d'Engagement (`nordwave-mcx-2027`)** : `Subject`: 8 nœuds, `Statement`: 9 nœuds, `Conflict`: 2 nœuds.

---

## Liens vers la Documentation

- **[Guide d'Intégration Tiers](docs/THIRD-PARTY-INTEGRATION-GUIDE.md)**
- **[Spécification d'Interface Externe (INTERFACE.md)](docs/INTERFACE.md)**
- **[Spécification du Schéma Graphe (SCHEMA.md)](docs/SCHEMA.md)**
- **[Architecture Logicielle (ADR-0014 / ADR-0015)](docs/architecture.md)**
- **[Manuel Utilisateur](docs/user_manual.md)**

---

## Licence

Sous licence MIT. Voir `LICENSE` pour plus de détails.
