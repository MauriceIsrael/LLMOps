## Context

The `template-app` currently uses Svelte Material UI (SMUI). Svelte 5 introduces runes and improved reactivity systems which conflict with older Svelte 3/4 paradigms used heavily by SMUI. Furthermore, Material Design 2 feels visually dated for many modern web applications, and SMUI's SCSS-based theming is complex to customize compared to utility-first CSS.

Moving to Tailwind CSS combined with shadcn-svelte/Bits UI aligns the template with the broader Svelte community's direction, provides a much more flexible and premium visual foundation, and natively supports Svelte 5's strict event typings and reactivity.

## Goals / Non-Goals

**Goals:**
- Completely replace SMUI with Tailwind CSS and shadcn-svelte.
- Establish a scalable, unstyled component system (Bits UI via shadcn).
- Update state management (`themeStore`, `locale`) to use Svelte 5 runes (`$state`).
- Ensure the application layout (Header, Sidebar/Drawer, Content area) remains functionally identical but visually refreshed.

**Non-Goals:**
- Adding large new functional features (like complex Authentication or Database integrations) in this specific UI refresh change.
- Upgrading to a new routing system (staying with standard SvelteKit filesystem routing).

## Decisions

**1. Tailwind CSS + shadcn-svelte**
- **Rationale**: shadcn-svelte (which wraps Bits UI) provides accessible, unstyled components that we own in our source code (via `components/ui`). This prevents dependency lock-in for UI components while giving us a Vercel-like, premium aesthetic out-of-the-box.
- **Alternatives Considered**: Skeleton UI (powerful, but highly opinionated and undergoing a massive v3 rewrite), Flowbite Svelte (a bit too generic/heavy).

**2. Svelte 5 Runes for Global State**
- **Rationale**: Instead of using Svelte 4 `writable` stores for theme and language, we will create pure `.svelte.ts` modules exporting a class or object utilizing `$state`. This is the recommended Svelte 5 paradigm for global reactivity.
- **Alternatives Considered**: Keeping Svelte 4 stores (works, but misses the opportunity to provide a pure Svelte 5 reference architecture).

**3. SCSS to PostCSS**
- **Rationale**: Tailwind relies on PostCSS. We will drop `sass` and `smui-theme` dependencies and replace them with standard Tailwind directives in a single `app.css` file.

## Risks / Trade-offs

- **[Risk] Complete UI Rewrite** → The layout must be rebuilt from scratch since SMUI classes (`.mdc-*`) will be removed.
  - *Mitigation*: We will carefully replicate the Sidebar, TopBar, and Content areas using standard Tailwind flex/grid utilities.
- **[Risk] Svelte 5 Compatibility with Tools** → Some older Vite/Svelte plugins might complain.
  - *Mitigation*: Ensure `@sveltejs/vite-plugin-svelte` and `svelte-check` are fully up-to-date (they are).
