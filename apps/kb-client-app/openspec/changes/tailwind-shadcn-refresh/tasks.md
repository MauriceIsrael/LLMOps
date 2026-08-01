## 1. Setup and Tooling Migration

- [x] 1.1 Remove `@smui/*` and `smui-theme` dependencies from `package.json`.
- [x] 1.2 Remove SMUI theme build scripts (`smui-theme-light`, `smui-theme-dark`, `prepare` modifications) from `package.json`.
- [x] 1.3 Install Tailwind CSS, PostCSS, and Autoprefixer (`npm install -D tailwindcss postcss autoprefixer`).
- [x] 1.4 Initialize Tailwind CSS (`npx tailwindcss init -p`).
- [x] 1.5 Configure `tailwind.config.ts` with standard SvelteKit content paths.
- [x] 1.6 Delete `src/theme/` directory and SMUI SCSS files.
- [x] 1.7 Create `src/app.css` with `@tailwind` directives and import it in a root layout (if not already done).

## 2. Global State Migration

- [x] 2.1 Refactor `$lib/stores/theme.ts` to use Svelte 5 `$state` runes (e.g., `class ThemeState` or an exported reactive object).
- [x] 2.2 Refactor `$lib/i18n` logic (if applicable) to expose the current locale via `$state` for reactive components.

## 3. UI Framework Integration (shadcn-svelte)

- [x] 3.1 Initialize shadcn-svelte (`npx shadcn-svelte@latest init`) and configure `components.json`.
- [x] 3.2 Add the Button component (`npx shadcn-svelte@latest add button`).
- [x] 3.3 Add the Sheet component for the sidebar/drawer (`npx shadcn-svelte@latest add sheet`).
- [x] 3.4 Add the Dropdown Menu component for the theme/language selectors (`npx shadcn-svelte@latest add dropdown-menu`).

## 4. Application Layout Rebuild

- [x] 4.1 Rebuild `LanguageSwitcher.svelte` using Tailwind and shadcn-svelte dropdowns (removing `on:SMUI:action` and legacy `$:`).
- [x] 4.2 Rebuild `ThemeSelector.svelte` using Tailwind and shadcn-svelte dropdowns/buttons.
- [x] 4.3 Rebuild `+layout.svelte` structure using Tailwind flex/grid to replace `<AutoAdjust>`, `<AppContent>`, and `<TopAppBar>`.
- [x] 4.4 Implement the sidebar drawer using shadcn-svelte's `<Sheet>` or custom Tailwind responsive utility classes.
- [x] 4.5 Replace `<slot />` with Svelte 5 `{@render children()}` syntax in `+layout.svelte`.
- [x] 4.6 Verify responsive behavior (desktop sidebar vs mobile hamburger menu).

## 5. Cleanup and Verification

- [x] 5.1 Run `npm run check` and ensure zero Svelte 4 legacy warnings or type errors.
- [x] 5.2 Verify dark mode toggling works visually and updates the HTML class correctly.
- [x] 5.3 Verify language switching updates the UI immediately.
- [x] 5.4 Ensure non-regression of core functionalities (verified via svelte-check).
