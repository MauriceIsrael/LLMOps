# SvelteKit Admin Boilerplate — Developer & AI Guide

> **Purpose**: This guide is the canonical reference for AI assistants and developers working with this boilerplate. Read it before making changes to understand the architecture, conventions, and where every extension point lives.

---

## Table of Contents
1. [Stack & Philosophy](#1-stack--philosophy)
2. [Project Structure](#2-project-structure)
3. [Core Architecture](#3-core-architecture)
4. [Extension Points](#4-extension-points)
5. [Global State — Theme & Locale](#5-global-state--theme--locale)
6. [Internationalization i18n](#6-internationalization-i18n)
7. [UI Component System](#7-ui-component-system)
8. [Pages & Routing](#8-pages--routing)
9. [Styling & Theming](#9-styling--theming)
10. [Adding New Features — Recipes](#10-adding-new-features--recipes)
11. [Conventions & Rules](#11-conventions--rules)
12. [Known Gotchas](#12-known-gotchas)

---

## 1. Stack & Philosophy

| Layer | Technology | Version |
|---|---|---|
| Framework | SvelteKit | ^2.16 |
| Language | Svelte | **5** (Runes mode) |
| Styling | Tailwind CSS | **v4** |
| UI Components | shadcn-svelte (via bits-ui) | ^1.2 |
| Icons | lucide-svelte | ^1.0 |
| i18n | svelte-i18n | ^4.0 |
| Build | Vite + @tailwindcss/vite | ^6 / ^4.2 |

**⚠️ Svelte 5 Runes are mandatory.** Never use `$:` reactive statements, `<slot>`, `on:event` directives, or `writable()` stores. Use `$state`, `$derived`, `$effect`, `{@render children()}`, and `$props()` throughout.

**⚠️ Tailwind v4 syntax.** The CSS entry point uses `@import "tailwindcss"` (not the old `@tailwind base/components/utilities` directives). Design tokens are configured via `@theme inline {}` blocks.

**⚠️ All static text must be internationalized.** No hardcoded user-visible strings are allowed anywhere in `.svelte` files. Every label, title, description, button text, placeholder, aria-label, tooltip, empty-state message, and error message must go through `$t('some.key')`. The only exceptions are: developer console logs, code comments, and data that comes from the backend (already localized server-side).

---

## 2. Project Structure

```
src/
├── app.css               # Global CSS — Tailwind v4 + shadcn theme tokens
├── app.html              # HTML shell — includes flash-free dark mode blocking script
├── hooks.server.ts       # Auth interceptor — populates event.locals.session (JWT + Casbin)
├── lib/
│   ├── utils.ts          # cn() helper + shadcn-svelte shared types
│   ├── i18n.ts           # svelte-i18n setup
│   ├── components/       # App-specific components
│   │   ├── LanguageSwitcher.svelte
│   │   ├── ThemeSelector.svelte
│   │   └── ui/           # shadcn-svelte generated components (DO NOT EDIT)
│   ├── auth/             # Security stack: JWT, Guards, Casbin logic
│   ├── stores/           
│   │   ├── preferences.svelte.ts  # Unified state for theme, locale, and UI state
│   │   └── i18n.svelte.ts         # Locale helpers
│   ├── toast/            # Imperative toast system
│   └── locales/          # Translation JSON files
└── routes/
    ├── +layout.svelte    # Main shell with sidebar and topbar
    ├── +page.svelte      # Dashboard overview
    ├── admin/            # Admin Management Suite (Users, Roles, Policies)
    ├── login/            # Auth pages
    ├── users/            # User listing example
    └── settings/         # User preferences form
```

---

## 3. Core Architecture

### 3.1 Layout Shell
```
┌──────────────────────────────────────────────────────────────┐
│                       +layout.svelte                         │
│  ┌───────────────────────────────────────────────────────┐   │
│  │  <header>  (sticky, z-30)                             │   │
│  │   [☰ Mobile]  [App Title]   [🌐] [☀/🌙] [👤 Avatar]  │   │
│  └───────────────────────────────────────────────────────┘   │
│  ┌──────────┐  ┌─────────────────────────────────────────┐   │
│  │          │  │                                         │   │
│  │ Sidebar  │  │  <main>  {@render children()}           │   │
│  │ (md+)    │  │  ← your page content goes here          │   │
│  │          │  │                                         │   │
│  └──────────┘  └─────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Security Stack (Auth & ABAC)
The application uses a multilayered security approach:

1. **Authentication**: JWT-based session management using `jose`. Tokens are stored in HTTP-only cookies.
2. **Session Context**: `hooks.server.ts` interceptor that populates `event.locals.session` on every request by validating the JWT and fetching fresh user attributes from **Prisma**.
3. **Authorization**: Fine-grained ABAC (Attribute-Based Access Control) powered by **Casbin**. 
4. **Guards**: Server-side functions in `src/lib/auth/guard.server.ts` (e.g., `requirePermission`) that enforce Casbin policies before page or API execution.

### 3.3 Persistence
- **ORM**: Prisma 6
- **Database**: SQLite (default, `dev.db` at root)
- **Policy Storage**: Casbin policies are stored in the database via `CasbinRule` model.

For detailed diagrams and data flow, see [**`ARCHITECTURE.md`**](./ARCHITECTURE.md).


---

## 4. Extension Points

### 4.1 Add a New Page / Route

1. Create `src/routes/<your-page>/+page.svelte`
2. Add it to the `menuItems` array in `src/routes/+layout.svelte`:

```ts
// In <script> of +layout.svelte
import { BarChart } from 'lucide-svelte';

const menuItems = [
  { href: '/',           labelKey: 'nav.dashboard', icon: LayoutDashboard },
  { href: '/users',      labelKey: 'nav.users',     icon: Users },
  { href: '/settings',   labelKey: 'nav.settings',  icon: Settings },
  // ↓ ADD HERE — labelKey must exist in all locale JSON files
  { href: '/analytics',  labelKey: 'nav.analytics', icon: BarChart },
];
```

Both the desktop sidebar and the mobile Sheet drawer read from this single array automatically.

> **i18n rule**: Add `"analytics": "Analytics"` (and translations) under the `"nav"` key in **all** locale files before adding the menu item.

---

### 4.2 Add a New Translation Key

> **Mandatory**: Every user-visible string must have a translation key. This includes page titles, headings, button labels, table column headers, form labels, placeholders, `aria-label` attributes, `title` tooltips, empty-state messages, and error messages.

1. Add the key to **all** locale files in `src/lib/locales/`. The structure must be **identical** across all files:

```json
// en.json
{
  "analytics": {
    "title": "Analytics",
    "noData": "No data available yet.",
    "downloadBtn": "Download report"
  }
}
```

```json
// fr-FR.json
{
  "analytics": {
    "title": "Analytiques",
    "noData": "Aucune donnée disponible pour le moment.",
    "downloadBtn": "Télécharger le rapport"
  }
}
```

2. Use in any component — **never** use raw strings:

```svelte
<script lang="ts">
  import { t } from 'svelte-i18n';
</script>

<!-- ✅ Correct -->
<h1>{$t('analytics.title')}</h1>
<p>{$t('analytics.noData')}</p>
<Button aria-label={$t('analytics.downloadBtn')}>
  {$t('analytics.downloadBtn')}
</Button>

<!-- ❌ Wrong — never hardcode user-visible strings -->
<h1>Analytics</h1>
<Button>Download report</Button>
```

> Always provide `{ default: 'Fallback text' }` for keys used during **layout initialization** (e.g. in `+layout.svelte`) to prevent raw keys during SSR hydration:
> ```svelte
> {$t('menu.title', { default: 'Navigation' })}
> ```

---

### 4.3 Add a New Language

1. Create `src/lib/locales/<lang>.json` with all keys matching `en.json`.
2. Register in `src/lib/i18n.ts` **before** the `init()` call:

```ts
import myLang from './locales/<lang>.json';
// Register both short and full BCP 47 codes:
register('<lang>',         () => Promise.resolve(myLang));
register('<lang>-<REGION>', () => Promise.resolve(myLang));
```

3. Add an entry to the `DISPLAY_LOCALES` array in `src/lib/components/LanguageSwitcher.svelte`:

```ts
// LanguageSwitcher.svelte — DISPLAY_LOCALES controls what appears in the picker
const DISPLAY_LOCALES = [
  { code: 'en',    name: 'English' },
  { code: 'fr',    name: 'Français' },
  { code: 'es',    name: 'Español' },
  { code: 'en-UK', name: 'English (UK)' },
  { code: '<lang>', name: 'Your Language' }, // ← ADD HERE
];
```

> **Do NOT iterate over `$availableLocales`** from svelte-i18n — it contains all registered BCP47 aliases (en, en-US, fr, fr-FR…) which creates duplicate entries in the dropdown.

---

### 4.4 Add a New shadcn-svelte Component

```bash
npx shadcn-svelte@latest add <component-name> -y
```

Installed to `src/lib/components/ui/<component-name>/`. Import pattern:

```svelte
<script>
  // Namespace imports (multi-export components):
  import * as Card from '$lib/components/ui/card';

  // Named imports (single-export components):
  import { Button } from '$lib/components/ui/button';
  import { Input }  from '$lib/components/ui/input';
</script>
```

> **Do not edit files in `src/lib/components/ui/` manually.** Re-run the CLI with `-o` after updates.

Browse all: https://shadcn-svelte.com/docs/components

---

### 4.5 Change the Brand Color / Color Palette

Edit CSS variable values in `src/app.css`. Only change the `:root` and `.dark` blocks:

```css
:root {
  --primary: 262 83% 58%;   /* Change to your brand color (HSL without hsl()) */
}
.dark {
  --primary: 263 70% 65%;
}
```

> Use the theme generator at https://shadcn-svelte.com/themes for a full palette.

---

### 4.6 Add Application-Level Global State

Follow the pattern in `src/lib/stores/theme.svelte.ts`:

```ts
// src/lib/stores/myFeature.svelte.ts
// ⚠️ File MUST have .svelte.ts extension for runes to work

class MyFeatureState {
  count = $state(0);                        // reactive primitive
  items = $state<string[]>([]);             // reactive array
  doubled = $derived(this.count * 2);       // computed value

  increment() {
    this.count++;
  }

  addItem(item: string) {
    this.items = [...this.items, item];     // always replace, never mutate
  }
}

export const myFeature = new MyFeatureState(); // singleton
```

Usage anywhere:
```svelte
<script>
  import { myFeature } from '$lib/stores/myFeature.svelte';
</script>

<p>{myFeature.count} (doubled: {myFeature.doubled})</p>
<button onclick={() => myFeature.increment()}>+1</button>
```

---

### 4.7 Add Server-Side Data Loading to a Page

```ts
// src/routes/products/+page.ts
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
  const res = await fetch(`/api/products`);
  const products = await res.json();
  return { products };
};
```

```svelte
<!-- src/routes/products/+page.svelte -->
<script lang="ts">
  import type { PageData } from './$types';
  let { data }: { data: PageData } = $props();
</script>

{#each data.products as p (p.id)}
  <p>{p.name}</p>
{/each}
```

---

### 4.8 Add an API Route

```ts
// src/routes/api/products/+server.ts
import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ url }) => {
  const id = url.searchParams.get('id');
  if (!id) throw error(400, 'Missing id');
  // ... query DB
  return json({ id, name: 'Widget' });
};
```

---

## 5. Global State — Unified Preferences

### Preferences (`src/lib/stores/preferences.svelte.ts`)

All persisted user settings (Theme, Locale, Sidebar state) are managed in a single reactive object.

```ts
type Preferences = {
  themeOverride: 'light' | 'dark' | 'system';
  locale: string;
  sidebarCollapsed: boolean;
};

export const preferences = $state<Preferences>(...);
```

**Key Features**:
- **Auto-Persistence**: Any mutation (e.g., `preferences.themeOverride = 'dark'`) is automatically saved to `localStorage`.
- **Flash-Free Theme**: A small blocking script in `app.html` reads these preferences before the app loads to apply the correct theme class instantly.
- **Reactive Locale**: Changing `preferences.locale` automatically triggers the `svelte-i18n` locale update.

**Wiring**: `+layout.svelte` handles the visual sync:
```ts
$effect(() => {
  const isDark = preferences.themeOverride === 'dark' || 
               (preferences.themeOverride === 'system' && window.matchMedia(...).matches);
  document.documentElement.classList.toggle('dark', isDark);
});
```

---

## 6. Internationalization i18n

### The Golden Rule: 100% Static Text Coverage

> **Every user-visible string in the application must be internationalized via `$t()`.** This is a non-negotiable architectural rule, not a preference.

**What must be translated:**

| Element | Example | How |
|---|---|---|
| Page titles / headings | `<h1>Dashboard</h1>` | `{$t('nav.dashboard')}` |
| Button labels | `<Button>Save</Button>` | `{$t('actions.save')}` |
| Table column headers | `<Table.Head>Status</Table.Head>` | `{$t('table.status')}` |
| Form labels & placeholders | `placeholder="Enter email"` | `placeholder={$t('form.emailPlaceholder')}` |
| `aria-label` attributes | `aria-label="Close"` | `aria-label={$t('a11y.close')}` |
| `title` tooltip text | `title="Expand sidebar"` | `title={$t('sidebar.expand')}` |
| Empty states | `<p>No results found.</p>` | `{$t('common.noResults')}` |
| Error / success messages | `<p>Saved successfully.</p>` | `{$t('feedback.saved')}` |
| Card descriptions | `<Card.Description>...</Card.Description>` | `{$t('dashboard.recentSalesDesc')}` |

**What does NOT need translation:**
- Developer console logs
- Code comments
- Data values from the backend (already localized server-side)
- Internal IDs / keys

**Naming convention for keys:**
```
<section>.<element>         → nav.dashboard, nav.users
<page>.<element>            → dashboard.title, settings.profileDesc
<component>.<element>       → themeSelector.switchToDark
actions.<verb>              → actions.save, actions.cancel, actions.delete
common.<element>            → common.noResults, common.loading
a11y.<element>              → a11y.close, a11y.openMenu
feedback.<state>            → feedback.saved, feedback.error
table.<column>              → table.status, table.amount
form.<field>                → form.username, form.emailPlaceholder
```

---

### Boot Order in `src/lib/i18n.ts` (strict)

```
1. register('en', loader)      ← ALL locales first
2. register('fr', loader)
3. register('fr-FR', loader)   ← Register both short + full BCP47 codes
4. ...
5. init({ fallbackLocale, initialLocale })   ← init LAST
```

### SSR Hydration (`src/routes/+layout.ts`)

```ts
import { waitLocale } from '$lib/i18n';
export const load = async () => { await waitLocale(); };
```

Without this, SSR renders the page before translation JSON is fetched, causing a brief flash of raw keys.

### Translation File Structure

All JSON files must have **identical key hierarchies**. Missing keys fall back to `en`.
The current key structure (extend as needed):

```json
{
  "app":    { "title": "..." },
  "nav":    { "dashboard": "...", "users": "...", "settings": "...", "language": "..." },
  "sidebar": { "collapse": "...", "expand": "..." },
  "menu":   { "title": "...", "subtitle": "...", "items": { ... } },
  "themeSelector": { "switchToDark": "...", "switchToClassic": "..." },
  "actions":  { "save": "...", "cancel": "...", "delete": "..." },
  "common":   { "noResults": "...", "loading": "..." },
  "a11y":     { "close": "...", "openMenu": "..." },
  "feedback": { "saved": "...", "error": "..." }
}
```

> `en.json` is the **source of truth**. When you add a key to `en.json`, immediately add it to all other locale files. CI should fail if any locale file has missing keys (enforce with a lint script).

---

## 7. UI Component System

### Component Import Patterns

```svelte
<!-- Namespace (multi-part components) -->
import * as Card from '$lib/components/ui/card';
<Card.Root> <Card.Header> <Card.Title> ... </Card.Root>

<!-- Named (single component) -->
import { Button } from '$lib/components/ui/button';
<Button variant="outline" size="sm">Click me</Button>

<!-- Button variants: default | outline | secondary | ghost | destructive | link -->
<!-- Button sizes:    default | xs | sm | lg | icon | icon-xs | icon-sm | icon-lg -->
```

### `cn()` Utility

Safely merge Tailwind classes (handles duplicates and conflicts):

```ts
import { cn } from '$lib/utils';
const classes = cn('px-4 py-2 rounded', isActive && 'bg-primary text-white');
```

### Icons

```svelte
<script>
  import { Rocket, Globe, Settings } from 'lucide-svelte';
</script>
<Rocket class="h-4 w-4 text-muted-foreground" />
```

---

## 8. Pages & Routing

### Standard Page Wrapper Pattern

```svelte
<div class="flex-1 space-y-4 p-4 md:p-8 pt-6">
  <!-- Page header -->
  <div class="flex items-center justify-between space-y-2">
    <h2 class="text-3xl font-bold tracking-tight">Page Title</h2>
    <div class="flex items-center space-x-2">
      <!-- Action buttons -->
    </div>
  </div>

  <!-- Content grid -->
  <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
    <!-- Cards, tables, forms... -->
  </div>
</div>
```

### SvelteKit File Conventions

| File | Runs on | Purpose |
|---|---|---|
| `+page.svelte` | Client | Page UI |
| `+page.ts` | Both | Universal data loading |
| `+page.server.ts` | Server | Server-only data / auth guards |
| `+layout.svelte` | Client | Persistent UI wrapper |
| `+layout.ts` | Both | Layout-level data (e.g. `waitLocale`) |
| `+layout.server.ts` | Server | Auth checks for all child routes |
| `+server.ts` | Server | REST API endpoint |
| `+error.svelte` | Client | Error boundary |

---

## 9. Styling & Theming

### Tailwind v4 Rules

- Entry point: `@import "tailwindcss"` in `src/app.css`
- No `tailwind.config.js` — plugin configured in `vite.config.ts`
- Custom tokens: use `@theme inline { --color-xxx: ...; }` in CSS

### Semantic Color Classes (prefer these over arbitrary values)

| Tailwind Class | Light | Dark | Usage |
|---|---|---|---|
| `bg-background` | white | near-black | Page background |
| `text-foreground` | near-black | near-white | Primary text |
| `bg-muted` | light gray | dark gray | Subtle sections |
| `text-muted-foreground` | gray | light gray | Secondary text |
| `bg-primary` | blue | lighter blue | Brand / CTAs |
| `bg-card` | white | dark | Card surfaces |
| `border-border` | light gray | dark gray | All borders |

---

## 10. Core Features & Recipes

### 10.1 Admin Management Suite

The app includes a full-featured admin dashboard (`/admin`) for managing the RBAC/ABAC system:
- **User Management**: List, search, and edit users stored in Prisma.
- **Policy Editor**: Real-time management of Casbin policies (Subject, Object, Action).
- **Permissions**: Visual assignment of roles and attributes to users.

### 10.2 Toast System (`src/lib/toast`)

A globally accessible, imperative notification system using Svelte 5 runes.

**Usage**:
```ts
import { toast } from '$lib/toast/index.svelte';

toast.success('Settings saved!');
toast.error('Failed to update profile', { duration: 5000 });
```

### 10.3 Recipe: Protected Route with Guards

Use the server-side guards to enforce permissions based on Casbin policies:

```ts
// src/routes/admin/secrets/+page.server.ts
import { requirePermission } from '$lib/auth/guard.server';

export const load = async (event) => {
  // Throws 403 if the user lacks 'read' on 'admin_secrets'
  await requirePermission(event, 'admin_secrets', 'read');
  
  return { /* ... */ };
};
```

---

## 11. Conventions & Rules

### i18n Rules (mandatory)

| ❌ Forbidden | ✅ Required |
|---|---|
| `<h1>Dashboard</h1>` | `<h1>{$t('nav.dashboard')}</h1>` |
| `<Button>Save</Button>` | `<Button>{$t('actions.save')}</Button>` |
| `placeholder="Enter name"` | `placeholder={$t('form.namePlaceholder')}` |
| `aria-label="Close"` | `aria-label={$t('a11y.close')}` |
| `title="Expand sidebar"` | `title={$t('sidebar.expand')}` |
| `<p>No data available.</p>` | `<p>{$t('common.noResults')}</p>` |
| `description="Recent sales this month."` | `description={$t('dashboard.recentSalesDesc')}` |

---

## 9. Dashboard Engine

The template provides a powerful, highly-customizable Dashboard Engine powered by **GridStack.js** and **Apache ECharts**. Instantiated apps should use this engine to build their main overview pages.

### Key Features
- **Drag & Drop / Resizable Grid**: Widgets can be freely arranged by users.
- **Local Persistence**: Layout is automatically saved to `localStorage` per user.
- **ECharts Integration**: High performance data visualization out-of-the-box.
- **Extensible Global Filters**: Apps can inject custom filter controls directly into the dashboard shell.

### Creating a Custom Dashboard

To build your dashboard in `src/routes/+page.svelte`:

1. **Define your ECharts options (if using charts)**
```typescript
const pieOptions = {
  tooltip: { trigger: 'item' },
  series: [{ type: 'pie', data: [ { value: 10, name: 'A' } ] }]
};
```

2. **Define the Widgets array**
```typescript
import type { WidgetDefinition } from '$lib/dashboard/types';
import { ChartWidget, StatWidget } from '$lib/dashboard/widgets';
import MyCustomWidget from './MyCustomWidget.svelte';

const widgets: WidgetDefinition[] = [
  { 
    id: 'kpi-1', type: 'stat', title: 'Revenue', defaultSize: 'sm', 
    component: StatWidget, props: { value: '$45k', trend: 'up' } 
  },
  { 
    id: 'chart-1', type: 'chart', title: 'Traffic', defaultSize: 'lg', 
    component: ChartWidget, props: { options: pieOptions } 
  },
  { 
    id: 'custom-1', type: 'custom', title: 'My Widget', defaultSize: 'md', 
    component: MyCustomWidget, props: { someData: 123 } 
  }
];
```

3. **Render the Engine with optional Filters snippet**
```svelte
<DashboardEngine 
  dashboardId="my-app-main"
  {widgets} 
  {editMode}
>
  {#snippet filters()}
    <FilterBar>
      <select><option>This Month</option></select>
    </FilterBar>
  {/snippet}
</DashboardEngine>
```

> **Note**: Custom components receive any values passed in the `props` object of their definition.

### Programmatic Widget Injection

You can allow users to add widgets to their dashboard from anywhere in your application (e.g., from a settings page, or a button next to a data table).

```svelte
<script lang="ts">
  import { dashboardStore } from '$lib/dashboard/widgetStore.svelte';
  import { StatWidget } from '$lib/dashboard/widgets';

  function addToDashboard() {
    dashboardStore.addWidget({
      id: 'dynamic-kpi-' + Date.now(),
      type: 'stat',
      title: 'Dynamic KPI',
      defaultSize: 'sm',
      component: StatWidget,
      props: { value: '42', trend: 'up' }
    });
  }
</script>

<button onclick={addToDashboard}>Add to Dashboard</button>
```

### Svelte 5 Rune Patterns

| ❌ Svelte 4 (forbidden) | ✅ Svelte 5 (required) |
|---|---|
| `$: value = x * 2` | `let value = $derived(x * 2)` |
| `$: { doEffect() }` | `$effect(() => { doEffect() })` |
| `let n = 0` (reactive) | `let n = $state(0)` |
| `<slot />` | `{@render children()}` |
| `export let prop` | `let { prop } = $props()` |
| `on:click={fn}` | `onclick={fn}` |
| `writable(val)` | `$state` in class / component |
| `<svelte:component this={C} />` | `{@const Comp = C}<Comp />` |

### File Naming

| Type | Convention | Example |
|---|---|---|
| Svelte components | PascalCase | `UserCard.svelte` |
| Route directories | kebab-case | `src/routes/user-profile/` |
| Stores with runes | camelCase + `.svelte.ts` | `myFeature.svelte.ts` |
| Plain TS utilities | camelCase + `.ts` | `dateUtils.ts` |

---

## 12. Known Gotchas

### i18n

- **`register()` must come before `init()`** — reversing the order causes all `$t()` calls to return the raw key string silently.
- **Always register both short and full locale codes** — `fr` AND `fr-FR`, `en` AND `en-US` — because `getLocaleFromNavigator()` may return either form.
- **Without `waitLocale()` in `+layout.ts`** — first SSR render will flash raw key strings before JavaScript hydrates.
- **Do not iterate `$availableLocales` in the language picker** — it contains all registered BCP47 aliases and produces duplicates. Use the hardcoded `DISPLAY_LOCALES` array in `LanguageSwitcher.svelte` instead.
- **Missing keys in non-`en` locales** fall back silently to `en`. Always add keys to all locale files at the same time to avoid invisible regressions.

### Tailwind v4

- **Never mix `@tailwind` directives with `@import "tailwindcss"`** — these are mutually exclusive syntaxes.
- **`@apply` works** inside `@layer base {}` but use sparingly. Prefer component-level Tailwind classes.

### shadcn-svelte

- **`components.json` style `"new-york"` → auto-upgraded to `"nova"`** by CLI v1.2+. This warning is expected, not an error.
- **shadcn-svelte v1.2 requires Tailwind v4**. For Tailwind v3 use `shadcn-svelte@1.0.0-next.10`.

### Svelte 5 State in Stores

- **`.svelte.ts` extension required** for `$state`, `$derived`, `$effect` to be recognized outside `.svelte` files.
- **Never mutate arrays/objects in place**: use `this.items = [...this.items, newItem]` instead of `this.items.push(newItem)` — Svelte 5 tracks assignment, not mutation (unless using `$state.raw`).
- **`$effect` in a class constructor** only runs if the class is instantiated inside a component lifecycle. For module-level side effects (e.g. restoring localStorage), use `if (typeof window !== 'undefined')` at module scope.

---

## 13. AI Architect Mode (MCP Server)

This project includes a dedicated **Model Context Protocol (MCP)** server to help AI assistants instantiate and extend the application.

### Activation
Add this to your MCP settings (e.g., `claude_desktop_config.json`):

```json
"template-app": {
  "command": "node",
  "args": ["/home/momo/Dev/template-app/mcp-server/dist/index.js"]
}
```

### Available Tools
- `instantiate_app`: Scaffolding for new projects.
- `generate_resource`: CRUD generator (Prisma + API + UI + i18n).
- `check_conventions`: Audit for i18n and Svelte 5 runes compliance.
