/**
 * JWT utilities — server-side only.
 *
 * Uses `jose` (Web Crypto API, edge-compatible).
 * Algorithm: HS256 (symmetric — suitable for same-server auth).
 *
 * @alternative Auth.js v5
 *   Replace this file entirely with @auth/sveltekit.
 *   The session shape in app.d.ts remains the same.
 *
 * Environment variables required:
 *   JWT_SECRET      — min 32-char random string (openssl rand -base64 32)
 *   (fallback to a dev secret if not set — NEVER use in production)
 */

import { SignJWT, jwtVerify, type JWTPayload } from 'jose';
import type { SessionUser } from '../../app.d.ts';

// @security Set JWT_SECRET in .env for production
const JWT_SECRET = new TextEncoder().encode(
  process.env.JWT_SECRET ?? 'dev-secret-change-me-in-production-min-32-chars!!'
);

const ACCESS_TOKEN_TTL = '15m';
const REFRESH_TOKEN_TTL = '7d';

export type AccessTokenPayload = JWTPayload & {
  sub: string;        // user id
  email: string;
  name: string;
  role: string;
  image?: string;
};

/**
 * Sign a short-lived access token (15 min).
 */
export async function signAccessToken(user: SessionUser): Promise<string> {
  return new SignJWT({
    email: user.email,
    name: user.name,
    role: user.role,
    image: user.image,
  })
    .setProtectedHeader({ alg: 'HS256' })
    .setSubject(user.id)
    .setIssuedAt()
    .setExpirationTime(ACCESS_TOKEN_TTL)
    .sign(JWT_SECRET);
}

/**
 * Sign a long-lived refresh token (7 days).
 * Only stores the user id — minimal surface area.
 */
export async function signRefreshToken(userId: string): Promise<string> {
  return new SignJWT({ type: 'refresh' })
    .setProtectedHeader({ alg: 'HS256' })
    .setSubject(userId)
    .setIssuedAt()
    .setExpirationTime(REFRESH_TOKEN_TTL)
    .sign(JWT_SECRET);
}

/**
 * Verify and decode an access token.
 * Returns the typed payload or null if invalid/expired.
 */
export async function verifyAccessToken(
  token: string
): Promise<AccessTokenPayload | null> {
  try {
    const { payload } = await jwtVerify(token, JWT_SECRET);
    return payload as AccessTokenPayload;
  } catch {
    return null;
  }
}

/**
 * Verify a refresh token and return the user id (sub) or null.
 */
export async function verifyRefreshToken(token: string): Promise<string | null> {
  try {
    const { payload } = await jwtVerify(token, JWT_SECRET);
    if (payload.type !== 'refresh' || !payload.sub) return null;
    return payload.sub;
  } catch {
    return null;
  }
}
