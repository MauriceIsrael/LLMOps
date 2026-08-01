/**
 * Root layout server load — Forward session from locals to client.
 */

import type { LayoutServerLoad } from './$types';
import { waitLocale } from '$lib/i18n';

export const load: LayoutServerLoad = async (event) => {
  // Ensure i18n is ready (still needed here for SSR translations)
  await waitLocale();

  // Return session already populated by src/hooks.server.ts
  return {
    session: event.locals.session
  };
};
