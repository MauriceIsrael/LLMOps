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

> **Avertissement Instance de Démonstration Publique :** Plan connaissances uniquement, lecture seule, taux limité, pas de SLA. Le jeton ci-dessus (`demo-public-2026-08`) est intentionnellement public et renouvelé périodiquement. Ne l'utilisez pas pour des données privées.

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
---

## Points Clés & Différenciateurs

1. **Cœur Déterministe et Auditable (0 Coût LLM Serveur)**  
   Aucun appel LLM non-déterministe côté serveur. La base est orchestrée par une base graphe typée (LadybugDB). Les règles d'élicitation, de level gate et de détection de contradictions reposent sur une logique symbolique pure.
2. **Gestion de l'Épistémique et de la Confiance**  
   Chaque énoncé architectural porte explicitement sa confiance (`verified`, `designed`, `vendor-stated`, `stated-by-client`, `assumed`) et son niveau de maturité (`L0_named` à `L4_specified`). Les documents générés indiquent s'ils sont provisoires (`is_provisional: true`, `unripe_subjects`, `open_conflicts`).
3. **Isolation Physique Dual-Plane (ADR-0015)**  
   Les connaissances transverses (`data/knowledge.lbug`) sont strictement séparées des engagements projets (`data/engagements/<id>.lbug`).
4. **Canal d'Instantané Scellé (Sealed Snapshot)**  
   Publication d'exports JSON scellés par SHA-256 (`fixtures/sealed_snapshot.json` ou `GET /snapshot/latest`) avec identifiants typés (`decision:ADR-0014`, `principle:P-002`) et index d'applicabilité pour une intégration résiliente et sans latence (ex. *Architecture Studio*).

---

## Liens vers la Documentation

- **[Guide d'Intégration Tiers](docs/THIRD-PARTY-INTEGRATION-GUIDE.md)**
- **[Spécification d'Interface Externe (INTERFACE.md)](docs/INTERFACE.md)**
- **[Guide d'Alignement Épistémique (EPISTEMIC-ALIGNMENT.md)](docs/EPISTEMIC-ALIGNMENT.md)**
- **[Spécification du Schéma Graphe (SCHEMA.md)](docs/SCHEMA.md)**
- **[Architecture Logicielle (ADR-0014 / ADR-0015)](docs/architecture.md)**
- **[Manuel Utilisateur](docs/user_manual.md)**

---

## Licence

Sous licence MIT. Voir `LICENSE` pour plus de détails.
