import { json } from '@sveltejs/kit';
import { signAccessToken, signRefreshToken } from '$lib/auth/jwt.server';
import { prisma } from '$lib/server/prisma';
import type { RequestHandler } from './$types';
import bcrypt from 'bcryptjs';

/**
 * Login Handler — DB-backed authentication with bcrypt.
 */
export const POST: RequestHandler = async ({ request, cookies }) => {
  try {
    const { email, password } = await request.json();

    if (!email || !password) {
      return json({ message: 'Email and password are required' }, { status: 400 });
    }

    // 1. Find user in DB
    const user = await prisma.user.findUnique({
      where: { email: email.toLowerCase() }
    });

    if (!user) {
      return json({ message: 'Invalid email or password' }, { status: 401 });
    }

    // 2. Check credentials with bcrypt
    const passwordMatch = await bcrypt.compare(password, user.passwordHash);
    
    // Fallback for demo users with plain text (optional, but safer to migrate)
    const isPlainTextMatch = user.passwordHash === password;
    
    if (!passwordMatch && !isPlainTextMatch) {
      return json({ message: 'Invalid email or password' }, { status: 401 });
    }

    // 3. Create tokens
    const accessToken = await signAccessToken({
      id: user.id,
      email: user.email,
      name: user.name,
      role: user.role as 'admin' | 'user',
    });

    const refreshToken = await signRefreshToken(user.id);

    // 4. Set cookies
    cookies.set('accessToken', accessToken, {
      path: '/',
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: 60 * 15, // 15 mins
    });

    cookies.set('refreshToken', refreshToken, {
      path: '/',
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: 60 * 60 * 24 * 7, // 7 days
    });

    return json({
      user: {
        id: user.id,
        email: user.email,
        name: user.name,
        role: user.role,
      }
    });
  } catch (err) {
    console.error('[Login Error]', err);
    return json({ message: 'Internal server error' }, { status: 500 });
  }
};
