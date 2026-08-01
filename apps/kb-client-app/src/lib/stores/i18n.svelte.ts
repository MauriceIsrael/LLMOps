/**
 * i18n Store — Locale persistence layer on top of svelte-i18n.
 *
 * This module:
 * 1. Restores the user's saved locale from localStorage on startup (client-only).
 * 2. Exports `setLocale()` to change locale + persist the choice.
 * 3. Re-exports svelte-i18n's `locale` and `locales` stores for direct use in components.
 *
 * @usage
 * In components, import from svelte-i18n for reactive `$locale` / `$t()`:
 *   import { t, locale } from 'svelte-i18n';
 *
 * Use `setLocale()` from this module when you need to change the locale
 * and have it persisted to localStorage:
 *   import { setLocale } from '$lib/stores/i18n.svelte';
 *   setLocale('fr');
 *
 * @extension
 * To add a new locale:
 *  1. Add JSON file to src/lib/locales/
 *  2. Register it in src/lib/i18n.ts (BEFORE the init() call)
 *  3. Add its display name to LanguageSwitcher.svelte's languageNames map
 */

import { locale as i18nLocale, locales as i18nLocales } from 'svelte-i18n';
import { get } from 'svelte/store';

const LOCALE_KEY = 'preferredLocale';

function getSavedLocale(): string {
  if (typeof window !== 'undefined') {
    return window.localStorage.getItem(LOCALE_KEY) ?? 'en';
  }
  return 'en';
}

function saveLocale(locale: string): void {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(LOCALE_KEY, locale);
  }
}

// Restore saved locale on startup (client-side only).
// Must use module-scope `if` (not $effect) because this runs before component lifecycle.
if (typeof window !== 'undefined') {
  const saved = getSavedLocale();
  i18nLocale.set(saved);
}

/**
 * Set the application locale. Updates svelte-i18n and persists to localStorage.
 * @param newLocale — BCP 47 locale code, e.g. 'en', 'fr', 'fr-FR'
 */
export function setLocale(newLocale: string): void {
  i18nLocale.set(newLocale);
  saveLocale(newLocale);
}

/**
 * The svelte-i18n locale store.
 * In components, use `$locale` for reactive access.
 */
export { i18nLocale as locale, i18nLocales as availableLocales };
