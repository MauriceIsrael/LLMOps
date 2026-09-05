# Architecture Knowledge Base & Governance Console

Interface web full-stack développée avec **Svelte 5** et **SvelteKit**, servant de console d'administration, d'exploration visuelle et de gouvernance des retours d'expérience (REX) pour la plateforme LLMOps d'architecture neuro-symbolique.

---

## Fonctionnalités Principales

### 1. Exploration du Référentiel d'Architecture
- Consultation et filtrage des actifs d'architecture (Patterns `PAT-*`, Décisions `ADR-*`, Principes `PRN-*`).
- Visualisation du graphe de dépendances et de conformité réglementaire (ECharts, Threlte 3D).
- Inspection de la traçabilité des décisions et de la matrice de conformité (NIS2, DORA, 3GPP MCX).

### 2. Gouvernance & Arbitrage des Suggestions REX (`/governance/suggestions`)
- Réception et examen des propositions d'amélioration issues des moissonnages de projets (`elicit harvest`).
- Détection sémantique automatique des contrôles réglementaires impactés (Bottom-Up).
- Workflow d'arbitrage par le Lead Architect : approbation (promotion automatique en pattern), demande de réétude, ou rejet.
- Dispatch d'alertes événementielles (Discord Webhook, push mobile ntfy.sh).

### 3. Gestion des Identités & Contrôle d'Accès (ABAC)
- Authentification par session JWT (Access & Refresh tokens) avec hachage sécurisé bcrypt.
- Moteur d'autorisation fine basé sur les attributs (**Casbin ABAC**).
- Persistance locale des politiques et utilisateurs via **Prisma ORM** et SQLite (`dev.db`).

---

## Architecture Technique

```
apps/kb-client-app/
├── src/
│   ├── lib/
│   │   ├── components/      # Composants UI Svelte 5 (Runes, Bits UI, Tailwind CSS)
│   │   └── server/          # Services backend (Casbin, JWT, Compliance matcher)
│   └── routes/
│       ├── +layout.svelte   # Navigation et état global de session
│       ├── assets/          # Consultation des actifs de connaissances
│       ├── explorer/        # Visualiseur interactif de graphe
│       ├── governance/      # Tableau de bord d'arbitrage des REX
│       ├── admin/           # Gestion des utilisateurs et politiques Casbin
│       └── api/             # Endpoints API (proxy MCP, suggestions, auth)
├── prisma/
│   ├── schema.prisma        # Modèle de données utilisateurs & Casbin
│   └── seed.ts              # Données de démonstration initiales
└── static/                  # Assets statiques
```

---

## Configuration & Démarrage

### Variables d'environnement (`.env`)

Créez un fichier `.env` à la racine de `apps/kb-client-app/` à partir de `.env.example` :

```bash
cp .env.example .env
```

| Variable | Description | Exemple |
|---|---|---|
| `DATABASE_URL` | Chaîne de connexion SQLite pour Prisma | `file:./dev.db` |
| `SERVER_TOKEN` | Jeton d'authentification pour le serveur FastMCP | `llmops-token-...` |
| `GCP_KB_ENDPOINT` | URL du serveur FastMCP LLMOps | `https://llmops-mcp-server-...run.app` |
| `OWNER_NOTIFICATION_WEBHOOK` | (Optionnel) URL Webhook Discord pour notifications | `https://discord.com/api/webhooks/...` |

### Commandes de Développement

```bash
# 1. Installer les dépendances
npm install

# 2. Initialiser la base de données SQLite et charger le seed
npx prisma db push
npx prisma db seed

# 3. Lancer le serveur de développement Vite
npm run dev

# 4. Vérifier les types Svelte et TypeScript
npm run check

# 5. Compiler pour la production
npm run build
```
