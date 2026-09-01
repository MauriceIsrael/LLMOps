# 🎨 Guide d'Intégration du Moteur de Rendu (Renderer)

Ce document fournit toutes les spécifications techniques et les interfaces nécessaires pour connecter un moteur de rendu externe (UI Web, React, Vue, Canvas interactive, générateur de PDF ou de diagrammes) à la plateforme d'architecture **LLMOps**.

---

## 🎯 1. Point d'Entrée & Architecture d'Intégration

Le point d'entrée naturel et standard de la plateforme est le **Serveur FastMCP** (`mcp_server`).

Le serveur expose :
1. **Mode MCP (Model Context Protocol) :** Via SSE (`/sse`) ou STDOUT (JSON-RPC 2.0 standard).
2. **Mode Python Native SDK :** Import direct des contrats Python via `mcp_server.renderer_interface.RendererClient`.

```mermaid
graph LR
    SubGraph["Moteur de Rendu (UI / React / PDF / Mermaid)"]
    SubGraph -->|JSON-RPC via MCP (SSE / STDIO)| FastMCP["Serveur FastMCP (mcp_server)"]
    SubGraph -->|Import Python Direct| SDK["RendererClient (renderer_interface.py)"]
    FastMCP --> Repo["ElicitationRepository & LadybugDB"]
    SDK --> Repo
```

---

## 🛠 2. Outils MCP Dédiés au Renderer

Le serveur FastMCP expose 3 outils spécialement conçus pour alimenter les moteurs de rendu :

### A. `get_render_payload(engagement: str)`
Récupère un **payload JSON d'affichage complet** contenant la synthèse du document, l'état de maturité, les énoncés d'architecture actifs, les conflits ouverts et les incertitudes.

**Signature JSON-RPC (MCP) :**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_render_payload",
    "arguments": {
      "engagement": "nordwave-mcx-2027"
    }
  },
  "id": 1
}
```

**Structure de la Réponse Payload :**
```json
{
  "engagement": "nordwave-mcx-2027",
  "status": "provisional", // "provisional" ou "final"
  "is_provisional": true,
  "maturity_board": [
    {
      "subject": "mcx-services",
      "name": "MCX Services",
      "level": "L2_decomposed",
      "origin": "blueprint",
      "updated_at": "2026-07-29T04:00:00Z"
    }
  ],
  "active_statements": [
    {
      "id": "S-0001",
      "section": "4.1",
      "subject": "mcx-services",
      "predicate": "runs_on",
      "value": "Kubernetes site dual-homed",
      "author": "amina",
      "role": "mcx-service-architect",
      "confidence": "designed",
      "status": "active"
    }
  ],
  "open_conflicts": [
    {
      "id": "C-0001",
      "kind": "contradiction",
      "detail": "Contradiction de stockage",
      "status": "open",
      "statement_ids": ["S-0001", "S-0002"]
    }
  ],
  "unripe_subjects": ["floor-control"]
}
```

---

### B. `get_diagram_graph(engagement: str, format: str)`
Génère la structure graphique de l'architecture (nœuds, arêtes, statut des conflits) et le code **Mermaid** prêt à être interprété par un visualiseur (Mermaid.js, Draw.io, D3.js).

**Signature JSON-RPC (MCP) :**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_diagram_graph",
    "arguments": {
      "engagement": "nordwave-mcx-2027",
      "format": "mermaid"
    }
  },
  "id": 2
}
```

**Structure de la Réponse :**
```json
{
  "engagement": "nordwave-mcx-2027",
  "format": "mermaid",
  "nodes": [
    { "id": "mcx-services", "label": "mcx-services", "type": "Subject", "level": "L2_decomposed" }
  ],
  "edges": [
    { "id": "S-0001-floor-control", "source": "mcx-services", "target": "floor-control", "predicate": "decomposes_into" }
  ],
  "mermaid": "flowchart TD\n    mcx-services[\"mcx-services (L2_decomposed)\"]\n    mcx-services -->|\"decomposes_into\"| floor-control"
}
```

---

### C. `get_subject_trajectory(engagement: str, subject: str)`
Fournit la trajectoire historique des niveaux de maturité franchis par un sujet pour afficher une timeline interactive ou un histogramme d'avancement.

**Signature JSON-RPC (MCP) :**
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_subject_trajectory",
    "arguments": {
      "engagement": "nordwave-mcx-2027",
      "subject": "mcx-services"
    }
  },
  "id": 3
}
```

**Exemple de retour :**
```json
{
  "status": "ok",
  "count": 2,
  "data": [
    { "level": "L1_framed", "question": "Cadrage des services MCX", "answer_excerpt": "Services hébergés sur Kubernetes" },
    { "level": "L2_decomposed", "question": "Décomposition en sous-composants", "answer_excerpt": "Contrôle de plancher et dispatch" }
  ]
}
```

---

## 🐍 3. Intégration Directe en Python (Client SDK)

Si votre renderer est développé en Python, vous pouvez importer directement `RendererClient` depuis [mcp_server/renderer_interface.py](../mcp_server/renderer_interface.py) :

```python
from mcp_server.renderer_interface import RendererClient

# 1. Initialiser le client pour un engagement
client = RendererClient(engagement="nordwave-mcx-2027")

# 2. Récupérer les données de document
payload = client.fetch_render_payload()
print(f"Statut du document: {payload.status}")
print(f"Nombre de sujets: {len(payload.maturity_board)}")

# 3. Récupérer le code Mermaid pour l'affichage de diagramme
diagram = client.fetch_diagram_graph(format="mermaid")
print(diagram.mermaid)

# 4. Récupérer la timeline d'un sujet
trajectory = client.fetch_subject_trajectory(subject="mcx-services")
for step in trajectory:
    print(f"[{step.level}] {step.question} -> {step.answer_excerpt}")
```

---

## 🌐 4. Intégration via Endpoint HTTP / SSE (Web Renderer / TS / JS)

Pour un renderer Web en Javascript/TypeScript (React, Vue, Web Component), connectez-vous au serveur FastMCP en SSE :

```typescript
// Exemple de connexion SSE en TypeScript / Web
const token = "demo-public-2026-08";
const sseUrl = `https://llmops-mcp-server-344571265365.europe-west1.run.app/sse?token=${token}`;

const eventSource = new EventSource(sseUrl);

eventSource.addEventListener("endpoint", (event) => {
  const messageEndpoint = event.data;
  console.log("Endpoint de message MCP prêt :", messageEndpoint);

  // Appeler l'outil get_render_payload via POST JSON-RPC sur l'endpoint de message
  fetch(messageEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      method: "tools/call",
      params: {
        name: "get_render_payload",
        arguments: { engagement: "nordwave-mcx-2027" }
      },
      id: 1
    })
  });
});
```

---

## 🧪 5. Validation & Tests d'Intégration

Un test unitaire d'intégration d'interface est disponible sous [tests/unit/test_renderer_interface.py](../tests/unit/test_renderer_interface.py). Vous pouvez l'exécuter à tout moment pour vérifier le bon fonctionnement de l'interface :

```bash
poetry run pytest tests/unit/test_renderer_interface.py -v
```
