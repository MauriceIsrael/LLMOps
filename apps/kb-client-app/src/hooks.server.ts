import { verifyAccessToken } from '$lib/auth/jwt.server';
import type { Handle } from '@sveltejs/kit';
import type { Session } from './app.d.ts';
import { prisma } from '$lib/server/prisma';
import { getEnforcer } from '$lib/server/casbin';

/**
 * Global Server Hook — Session Management & ABAC Context.
 *
 * Warm-up : Casbin est initialisé au démarrage du serveur (fire-and-forget)
 * pour éviter le coût d'initialisation sur la première requête utilisateur.
 */
getEnforcer().catch((err) =>
  console.warn('[Casbin Warm-up] Initialisation échouée :', err)
);

export const handle: Handle = async ({ event, resolve }) => {
  const accessToken = event.cookies.get('accessToken');
  let session: Session | null = null;

  try {
    if (accessToken) {
      const payload = await verifyAccessToken(accessToken);
      if (payload && payload.sub) {
        // Fetch fresh user data + ABAC attributes from DB
        const user = await prisma.user.findUnique({
          where: { id: payload.sub }
        });

        if (user) {
          session = {
            user: {
              id: user.id,
              email: user.email,
              name: user.name,
              role: user.role as 'admin' | 'user',
              // @ts-ignore
              attributes: JSON.parse(user.attributes || '{}'),
            },
            expires: new Date((payload.exp ?? 0) * 1000).toISOString(),
          };
        }
      }
    }
  } catch (err) {
    console.error('[Hook Error] Session population failed:', err);
    // Continue without session if DB is down or error occurred
  }

  event.locals.session = session;

  const response = await resolve(event);
  return response;
};
