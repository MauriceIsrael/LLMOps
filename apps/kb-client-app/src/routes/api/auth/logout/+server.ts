import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

/** POST /api/auth/logout — clear both auth cookies */
export const POST: RequestHandler = async ({ cookies }) => {
  cookies.delete('accessToken', { path: '/' });
  cookies.delete('refreshToken', { path: '/' });
  return json({ ok: true });
};
