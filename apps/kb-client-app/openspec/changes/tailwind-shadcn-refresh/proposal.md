## Why

The current `template-app` relies on Svelte Material UI (SMUI), which uses legacy Svelte 3/4 syntax, older Material Design specifications, and requires complex SCSS compilations for theming. To provide a modern, fast, and highly customizable baseline for future projects in Svelte 5, we need to migrate the UI foundation to Tailwind CSS paired with a headless component library like shadcn-svelte or Bits UI.

Beyond the visual layer, a production-grade template also requires solved patterns for authentication, server communication, client-side persistence, user feedback, and color-scheme management. This proposal bundles those concerns into the same refresh so every project derived from this template starts from a robust, opinionated foundation.

---

## What Changes

### Breaking changes

- **BREAKING**: Complete removal of all `@smui/*` dependencies and SMUI-specific SCSS compilations.
- **BREAKING**: Migration of existing UI layout (`+layout.svelte`, Drawer, TopAppBar) from SMUI to standard HTML/Tailwind styling.
- **BREAKING**: Global state (`theme`, `language`) migrated from Svelte 4 `writable` stores to Svelte 5 `$state` runes; consuming components must drop the `$` store auto-subscription syntax.

### Additions

- Tailwind CSS as primary styling engine (utility-first, design-token-driven).
- shadcn-svelte + Bits UI for accessible, headless core components.
- Auth capability: pluggable Auth.js (NextAuth v5) adapter **or** a lightweight custom JWT flow, selectable via a feature flag in `src/lib/config.ts`.
- SvelteKit API route conventions: typed `+server.ts` handlers with a thin fetch wrapper; optional tRPC adapter wired on the same routes.
- `UserPreferences` store: Svelte 5 `$state` backed by `localStorage`, replays on first hydration, avoids SSR mismatch.
- Global `Toast` notification queue: a single `<Toaster>` component in `+layout.svelte`, callable from anywhere via a `toast()` helper.
- Flash-free dark mode: OS-aware via `prefers-color-scheme`, persisted in `localStorage`, injected via a blocking inline `<script>` in `app.html` before page paint.

---

## Capabilities

### New Capabilities

| ID | Capability | À quoi ça sert | Use cases typiques |
|---|---|---|---|
| `ui-foundation` | Core Tailwind + shadcn-svelte | Fournit le système de design de base : tokens de couleur, typographie, espacements, et des composants UI headless et accessibles prêts à styler. | Créer rapidement des formulaires, modales, menus et tableaux cohérents ; rebrandir l'app en changeant quelques variables CSS. |
| `state-management` | Svelte 5 rune state | Centralise l'état global de l'application (thème, langue) sous forme de `$state` réactif, partageable entre composants sans boilerplate de stores. | Changer la langue dynamiquement sans rechargement ; lire le thème actif dans n'importe quel composant sans `import` de store. |
| `auth` | Authentication | Gère l'identité de l'utilisateur : connexion, déconnexion, gestion des sessions et protection des routes côté serveur. | Login OAuth (Google, GitHub) pour un back-office ; magic-link email pour un SaaS sans mot de passe ; JWT léger pour une API mobile. |
| `api-integration` | Typed API layer | Expose des routes serveur SvelteKit avec validation de schéma (Zod) et un client `fetch` typé ; option tRPC pour un contrat strict client-serveur full-TypeScript. | CRUD d'une ressource (articles, projets…) ; mutation déclenchée depuis un formulaire Svelte avec feedback d'erreur automatique ; appel tRPC depuis un composant avec autocomplétion des paramètres. |
| `state-persistence` | LocalStorage sync | Conserve les préférences utilisateur entre les sessions (thème, langue, état des panneaux) sans base de données ni compte. | Retrouver sa sidebar ouverte après un rafraîchissement ; mémoriser la langue choisie pour la prochaine visite ; sauvegarder le mode sombre préféré indépendamment de l'OS. |
| `notifications` | Toast queue | Fournit un canal de feedback global et non-bloquant pour informer l'utilisateur du résultat d'une action sans interrompre son flux de travail. | Confirmer une sauvegarde réussie ; signaler une erreur réseau ; avertir d'un timeout de session imminent. |
| `dark-mode` | Flash-free dark mode | Détecte et applique le thème sombre/clair avant le premier rendu afin d'éviter le flash de contenu mal coloré (FOUC), tout en respectant la préférence OS et le choix manuel. | Appli consultée la nuit sur mobile (thème système) ; toggle manuel dans les settings ; dashboard pro qui mémorise le mode sombre entre les onglets. |

### Modified Capabilities

- `ui-foundation` (was: SMUI layout) → rebuilt on Tailwind primitives.
- `state-management` (was: Svelte 4 stores) → Svelte 5 `$state` + `$derived`.

---

## Technical Design

### Authentication (`auth`)

Two selectable strategies, both exposing the same `session` shape:

**Strategy A — Auth.js v5 (recommended for OAuth)**

```
src/
  lib/auth/
    index.ts          ← SvelteKitAuth() config (providers, callbacks, adapter)
  routes/
    auth/[...nextauth]/
      +server.ts      ← { GET, POST } = handle (Auth.js catch-all)
    +layout.server.ts ← inject session into page data via event.locals
```

Providers pre-configured: `GitHub`, `Google`, `Resend` (magic link).  
DB adapter: `@auth/drizzle-adapter` wired to SQLite (dev) / Postgres (prod) via env.

**Strategy B — Custom JWT (lightweight, no DB)**

```
src/
  lib/auth/
    jwt.server.ts     ← sign / verify / refresh (jose library)
    session.ts        ← $state session store, populated from cookie on hydration
  routes/
    api/auth/
      login/+server.ts
      refresh/+server.ts
      logout/+server.ts
```

Access token: 15-min HS256 JWT in `HttpOnly` cookie.  
Refresh token: 7-day opaque token stored in `HttpOnly` cookie, rotated on use.

Both strategies expose `$session` (current user) and `requireAuth()` (server-side guard) as the public surface.

---

### API Integration (`api-integration`)

**Pattern 1 — Native `+server.ts` routes**

```ts
// src/routes/api/items/+server.ts
import { json, error } from '@sveltejs/kit';
import { z } from 'zod';
import type { RequestHandler } from './$types';

const CreateItemSchema = z.object({ name: z.string().min(1) });

export const POST: RequestHandler = async ({ request, locals }) => {
  const body = await request.json();
  const parsed = CreateItemSchema.safeParse(body);
  if (!parsed.success) error(400, parsed.error.flatten());

  const item = await locals.db.item.create({ data: parsed.data });
  return json(item, { status: 201 });
};
```

A typed `apiFetch<T>` client helper wraps `fetch` with auto-JSON, CSRF header injection, and error normalisation.

**Pattern 2 — tRPC (opt-in)**

```ts
// src/lib/trpc/router.ts  ← root router
// src/lib/trpc/context.ts ← RequestEvent → context (db, session)
// src/routes/api/trpc/[...procedure]/+server.ts ← fetchRequestHandler
```

Client: `createTRPCProxyClient` exposed as `$trpc` (Svelte 5 context).  
A `trpc.svelte.ts` helper provides `createQuery` / `createMutation` wrappers compatible with Svelte 5 reactivity.

---

### State Persistence (`state-persistence`)

```ts
// src/lib/stores/preferences.svelte.ts
import { browser } from '$app/environment';

const STORAGE_KEY = 'app:preferences';

type Preferences = {
  themeOverride: 'light' | 'dark' | 'system';
  locale: string;
  sidebarOpen: boolean;
};

const defaults: Preferences = {
  themeOverride: 'system',
  locale: 'en',
  sidebarOpen: true,
};

function loadFromStorage(): Preferences {
  if (!browser) return defaults;
  try {
    return { ...defaults, ...JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') };
  } catch {
    return defaults;
  }
}

export const preferences = $state<Preferences>(loadFromStorage());

$effect(() => {
  if (browser) localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
});
```

SSR safety: `browser` guard prevents `localStorage` access on the server. The hydration gap is invisible because the inline dark-mode script (see below) applies the correct class before paint.

---

### Toast / Notification System (`notifications`)

```ts
// src/lib/toast/index.svelte.ts

type Variant = 'default' | 'success' | 'error' | 'warning' | 'info';

type Toast = { id: string; message: string; variant: Variant; duration: number };

let queue = $state<Toast[]>([]);

export function toast(message: string, opts?: { variant?: Variant; duration?: number }) {
  const id = crypto.randomUUID();
  queue = [...queue, { id, message, variant: opts?.variant ?? 'default', duration: opts?.duration ?? 4000 }];
}

export function dismiss(id: string) {
  queue = queue.filter((t) => t.id !== id);
}

export { queue as toastQueue };
```

`<Toaster>` renders the queue from a fixed bottom-right portal; each toast auto-dismisses via `setTimeout` and uses a CSS `enter`/`exit` animation. Fully accessible (`role="status"`, `aria-live="polite"`).

Usage anywhere in the app:

```ts
import { toast } from '$lib/toast';
toast('Saved!', { variant: 'success' });
```

---

### Dark Mode (`dark-mode`)

**Tailwind config** — `darkMode: 'class'` (class on `<html>`).

**Blocking inline script in `app.html`** — runs synchronously before any CSS or JS:

```html
<script>
  (function () {
    var stored = localStorage.getItem('app:preferences');
    var override = stored ? JSON.parse(stored).themeOverride : 'system';
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    var isDark = override === 'dark' || (override !== 'light' && prefersDark);
    document.documentElement.classList.toggle('dark', isDark);
  })();
</script>
```

**Svelte 5 reactive sync** — `$effect` in the preferences store applies the class whenever `themeOverride` changes:

```ts
$effect(() => {
  if (browser) {
    document.documentElement.classList.toggle(
      'dark',
      preferences.themeOverride === 'dark' ||
        (preferences.themeOverride === 'system' &&
          window.matchMedia('(prefers-color-scheme: dark)').matches)
    );
  }
});
```

A `<ThemeToggle>` button component cycles `system → light → dark → system` and updates `preferences.themeOverride`.

---

## Impact

| Area | Impact |
|---|---|
| `package.json` | Add: `@auth/sveltekit`, `@auth/drizzle-adapter`, `jose`, `zod`, `@trpc/server`, `@trpc/client`, `bits-ui`, `svelte-sonner` (toast). Remove: all `@smui/*`. |
| `app.html` | Add blocking `<script>` for theme detection before first paint. |
| `src/lib/` | New subdirs: `auth/`, `toast/`, `trpc/`, `stores/preferences.svelte.ts`. |
| `src/routes/` | New: `auth/[...nextauth]/+server.ts`, `api/trpc/[...procedure]/+server.ts`, `api/` example routes. |
| `+layout.svelte` | Add `<Toaster>`, consume `$session`, apply dark-mode class reactively. |
| `+layout.server.ts` | Inject `session` into `locals` for SSR. |
| Configuration | Add: `drizzle.config.ts`, `.env.example` documenting all required env vars. |

## Non-Goals

- Implementing a specific business domain (users, products, etc.) — this is a template skeleton only.
- Database schema migrations — the drizzle adapter wiring is provided but no domain tables are defined.
- End-to-end test suite — unit tests for auth helpers and the toast store are in scope; Playwright e2e is out of scope for this change.
