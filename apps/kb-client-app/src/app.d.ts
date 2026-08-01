// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces

/**
 * Session shape — intentionally OAuth-compatible (matches Auth.js / NextAuth Session).
 * Swap to Auth.js: replace the JWT logic in +layout.server.ts with SvelteKitAuth()
 * and Auth.js will populate event.locals.session with the same shape.
 *
 * @alternative Auth.js v5
 *   import { SvelteKitAuth } from '@auth/sveltekit';
 *   export const { handle } = SvelteKitAuth({ providers: [...] });
 *   // session is then available as event.locals.session (same type)
 */
export type UserRole = 'admin' | 'user';

export type SessionUser = {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  /** ABAC Attributes */
  attributes?: Record<string, any>;
  /** Optional — used for OAuth avatar URLs */
  image?: string;
};


export type Session = {
  user: SessionUser;
  /** ISO datetime string — token expiry */
  expires: string;
};

declare global {
  namespace App {
    // interface Error {}
    interface Locals {
      /** Populated by +layout.server.ts after JWT verification. Null if unauthenticated. */
      session: Session | null;
    }
    interface PageData {
      /** Forwarded from Locals so client-side layout can read the session. */
      session: Session | null;
    }
    // interface PageState {}
    // interface Platform {}
  }
}

export {};
