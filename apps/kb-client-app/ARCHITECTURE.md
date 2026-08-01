# Software Architecture Documentation

This document describes the high-level architecture, data flow, and design patterns used in the SvelteKit Admin Boilerplate.

## 1. High-Level Overview

The application follows a modern full-stack architecture using SvelteKit, where the frontend and backend are tightly integrated but maintain clear boundaries for security-critical logic.

```mermaid
graph TD
    User((User / Browser))
    
    subgraph "Frontend (Svelte 5)"
        UI[UI Components]
        Runes[Svelte Runes State]
        I18n[svelte-i18n]
    end
    
    subgraph "SvelteKit Layer"
        Hooks[hooks.server.ts]
        Routes[Page & API Routes]
        Guards[Auth Guards]
    end
    
    subgraph "Backend Services"
        Casbin[Casbin ABAC Engine]
        JWT[JWT Service]
        Prisma[Prisma ORM]
    end
    
    DB[(SQLite Database)]

    User <--> UI
    UI <--> Routes
    Routes --> Guards
    Hooks --> JWT
    Guards --> Casbin
    Casbin --> Prisma
    Prisma <--> DB
    JWT --> Prisma
```

---

## 2. Authentication & Session Management

We use a stateless JWT-based authentication system with secure HTTP-only cookies.

```mermaid
sequenceDiagram
    participant U as User
    participant A as API (/login)
    participant J as JWT Service
    participant H as Server Hook
    participant P as Prisma / DB

    U->>A: POST credentials
    A->>P: Find user & verify password
    P-->>A: User object (Attributes)
    A->>J: signAccessToken(user)
    J-->>A: JWT string
    A->>U: Set HTTP-only Cookie (accessToken)
    
    Note over U,H: Subsequent Requests
    U->>H: GET /dashboard (with Cookie)
    H->>J: verifyAccessToken(token)
    J-->>H: Payload (userId)
    H->>P: Fetch fresh User + Attributes
    P-->>H: User data
    H->>H: Populate event.locals.session
```

---

## 3. Authorization (ABAC) Flow

Authorization is enforced using **Casbin**, allowing for both Role-Based (RBAC) and Attribute-Based (ABAC) Access Control.

```mermaid
sequenceDiagram
    participant L as Page / API Load
    participant G as Guard (requirePermission)
    participant C as Casbin Enforcer
    participant P as PrismaAdapter
    participant DB as SQLite

    L->>G: requirePermission(obj, act)
    G->>G: Get User Attributes from session
    G->>C: enforce(sub, obj, act)
    C->>P: Load Policy
    P->>DB: SELECT from CasbinRule
    DB-->>P: Policy Rules
    P-->>C: Policies
    C->>C: Evaluate Matcher (ABAC logic)
    C-->>G: allow / deny
    G-->>L: Proceed / throw error(403)
```

---

## 4. Database Schema (ERD)

Managed via Prisma, the schema supports users, their dynamic attributes, and persistent authorization policies.

```mermaid
erDiagram
    User {
        string id PK
        string email
        string passwordHash
        string name
        string role
        string attributes "JSON"
        datetime createdAt
    }
    
    CasbinRule {
        int id PK
        string ptype
        string v0
        string v1
        string v2
        string v3
        string v4
        string v5
    }

    Resource {
        string id PK
        string name
        string type
        string ownerId FK
        string tags "JSON"
    }

    User ||--o{ Resource : owns
```

---

## 5. Technical Stack

| Layer | Component | Description |
|---|---|---|
| **Framework** | SvelteKit / Svelte 5 | Reactive UI with Runes and SSR capabilities. |
| **Persistence** | Prisma / SQLite | Type-safe database access with easy migrations. |
| **Auth Engine** | Casbin | Policy-based authorization (ABAC/RBAC). |
| **Security** | jose (JWT) | Secure token signing and verification. |
| **I18n** | svelte-i18n | Multi-language support with SSR hydration. |
| **Styling** | Tailwind CSS v4 | Utility-first styling with modern CSS variables. |

---

## 6. Key Design Patterns

### 6.1 Server-Side Guards
To prevent sensitive logic from leaking to the client, we use `.server.ts` files for guards. `requirePermission` and `requireRole` are exclusively server-side.

### 6.2 Global Hooks
`hooks.server.ts` acts as a centralized middleware that validates the session on every request and populates `locals`, ensuring security context is available to all routes.

### 6.3 Example Routes
The `/users` and `/settings` routes are provided as architectural examples of CRUD and profile management. They demonstrate how to use Casbin guards and Prisma together. They can be safely removed or adapted for specific business needs.

### 6.4 ABAC Matchers
Casbin is configured with a custom matcher that evaluates user attributes (e.g., `clearance`) against resource requirements, enabling dynamic access control without hardcoding roles.

> [!IMPORTANT]
> **Initial Access**: After pushing the Prisma schema, you **MUST** run `npx prisma db seed` to create the initial admin user and Casbin policies. Without this step, you will not be able to log in to the administrative dashboard.

### 6.4 Admin Management Suite
The template includes a pre-built Admin Management Suite that abstracts raw Casbin rules (`p` and `g`) into a classical **Groups & Roles** UI. 
- **Groups**: Casbin roles are dynamically inferred. Users can be assigned to groups.
- **Permissions**: Casbin policies are assigned to groups, linking Resources and Actions.
- **Validation**: All API endpoints (`/api/admin/*`) strictly validate relational integrity (e.g., verifying user existence in Prisma before adding grouping policies).
