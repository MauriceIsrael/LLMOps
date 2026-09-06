import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { verifyRefreshToken, signAccessToken, signRefreshToken } from '$lib/auth/jwt.server';
import { prisma } from '$lib/server/prisma';

const COOKIE_OPTS = {
  httpOnly: true,
  secure: process.env.NODE_ENV === 'production',
  sameSite: 'lax' as const,
  path: '/',
};

/** POST /api/auth/refresh — rotate refresh token, issue new access token */
export const POST: RequestHandler = async ({ cookies }) => {
  const refreshToken = cookies.get('refreshToken');
  if (!refreshToken) {
    error(401, { message: 'No refresh token' });
  }

  const userId = await verifyRefreshToken(refreshToken!);
  if (!userId) {
    cookies.delete('refreshToken', { path: '/' });
    cookies.delete('accessToken', { path: '/' });
    error(401, { message: 'Refresh token invalid or expired' });
  }

  const dbUser = await prisma.user.findUnique({
    where: { id: userId! }
  });
  if (!dbUser) {
    error(401, { message: 'User not found' });
  }

  const user = {
    id: dbUser!.id,
    email: dbUser!.email,
    name: dbUser!.name,
    role: dbUser!.role as 'admin' | 'user',
  };

  // Rotate both tokens
  const [newAccessToken, newRefreshToken] = await Promise.all([
    signAccessToken(user!),
    signRefreshToken(userId!),
  ]);

  cookies.set('accessToken', newAccessToken, {
    ...COOKIE_OPTS,
    maxAge: 60 * 15,
  });
  cookies.set('refreshToken', newRefreshToken, {
    ...COOKIE_OPTS,
    maxAge: 60 * 60 * 24 * 7,
  });

  const expires = new Date(Date.now() + 15 * 60 * 1000).toISOString();
  return json({ expires });
};
