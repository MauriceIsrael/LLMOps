/**
 * Unified User Preferences Store
 *
 * Single source of truth for all persisted user preferences.
 * Uses Svelte 5 `$state` runes — reactive without boilerplate.
 *
 * Storage key: 'app:preferences' (matches the blocking script in app.html)
 *
 * @usage
 *   import { preferences } from '$lib/stores/preferences.svelte';
 *   preferences.themeOverride = 'dark';   // reactive + auto-persisted
 *   preferences.sidebarCollapsed = true;
 *
 * @extension
 *   Add a new field to the `Preferences` type, initialise it in `defaults`,
 *   and it will be automatically persisted on next change.
 *
 * @alternative Auth.js / NextAuth
 *   The themeOverride field intentionally matches the pattern used by
 *   next-themes. Swapping to Auth.js + next-themes: replace this store's
 *   themeOverride logic with the ThemeProvider from next-themes.
 */

import { browser } from '$app/environment';

export const PREFERENCES_KEY = 'app:preferences';

export type ThemeOverride = 'light' | 'dark' | 'system';

export type Preferences = {
  /** 'light' | 'dark' | 'system' (follows OS preference) */
  themeOverride: ThemeOverride;
  /** BCP 47 locale, e.g. 'en', 'fr' */
  locale: string;
  /** Desktop sidebar collapsed state */
  sidebarCollapsed: boolean;
};

const defaults: Preferences = {
  themeOverride: 'system',
  locale: 'en',
  sidebarCollapsed: false,
};

function loadFromStorage(): Preferences {
  if (!browser) return defaults;
  try {
    const raw = localStorage.getItem(PREFERENCES_KEY);
    return raw ? { ...defaults, ...JSON.parse(raw) } : defaults;
  } catch {
    return defaults;
  }
}

/**
 * Reactive singleton preferences object.
 * Mutations are automatically persisted to localStorage via $effect.
 */
export const preferences = $state<Preferences>(loadFromStorage());

// Persist on every change (browser-only — SSR safe).
if (browser) {
  $effect.root(() => {
    $effect(() => {
      localStorage.setItem(PREFERENCES_KEY, JSON.stringify({ ...preferences }));
    });
  });
}

/** Reset all preferences to factory defaults. */
export function resetPreferences(): void {
  preferences.themeOverride = defaults.themeOverride;
  preferences.locale = defaults.locale;
  preferences.sidebarCollapsed = defaults.sidebarCollapsed;
}
