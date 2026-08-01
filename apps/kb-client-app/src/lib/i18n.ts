/**
 * svelte-i18n initialization module.
 *
 * CRITICAL: All `register()` calls MUST happen before `init()`.
 *
 * @architecture
 * - The default locale ('en') is statically imported to ensure 
 *   instant availability during SSR (minimizing TTFB).
 * - Other locales are lazily loaded via dynamic imports to keep
 *   the initial bundle small.
 */

import { register, init, getLocaleFromNavigator, waitLocale } from 'svelte-i18n';
import en from './locales/en.json';

// ── Step 1: Register locales ───────────────────────────────────────────────
// Static for default locale (best for SSR speed)
register('en',    () => Promise.resolve(en));
register('en-US', () => Promise.resolve(en));

// Dynamic for others (best for bundle size)
register('fr',    () => import('./locales/fr-FR.json'));
register('fr-FR', () => import('./locales/fr-FR.json'));
register('es',    () => import('./locales/es.json'));
register('en-UK', () => import('./locales/en-UK.json'));
register('en-GB', () => import('./locales/en-UK.json'));

// ── Step 2: Initialize ─────────────────────────────────────────────────────
init({
  fallbackLocale: 'en',
  initialLocale: 'en', // Force 'en' during SSR for maximum speed
});

export { waitLocale };