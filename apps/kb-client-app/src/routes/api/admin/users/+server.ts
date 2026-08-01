import { json, error } from '@sveltejs/kit';
import { prisma } from '$lib/server/prisma';
import { requireRole } from '$lib/auth/guard.server';
import type { RequestHandler } from './$types';
import bcrypt from 'bcryptjs';
import { z } from 'zod';

const UserSchema = z.object({
  name: z.string().min(2),
  email: z.string().email(),
  password: z.string().min(6).optional(),
  role: z.enum(['admin', 'user']),
  attributes: z.record(z.string(), z.any()).optional()
});

/**
 * User CRUD API — Admin Only.
 */

// POST: Create a new user
export const POST: RequestHandler = async ({ request, locals }) => {
  requireRole(locals, 'admin');
  
  const body = await request.json();
  const result = UserSchema.safeParse(body);
  if (!result.success) {
    const message = result.error.issues.map((e: z.ZodIssue) => `${e.path.join('.')}: ${e.message}`).join(', ');
    throw error(400, message);
  }

  const { name, email, password, role, attributes } = result.data;
  
  if (!password) {
    throw error(400, 'Password is required for new users');
  }

  try {
    const passwordHash = await bcrypt.hash(password, 10);
    const user = await prisma.user.create({
      data: {
        name,
        email: email.toLowerCase(),
        passwordHash,
        role,
        attributes: JSON.stringify(attributes || {}),
      }
    });
    return json(user);
  } catch (err: any) {
    if (err.code === 'P2002') {
      throw error(409, 'User with this email already exists');
    }
    throw error(500, 'Failed to create user');
  }
};

// PATCH: Update user
export const PATCH: RequestHandler = async ({ request, locals }) => {
  requireRole(locals, 'admin');
  
  const body = await request.json();
  const { id, ...rest } = body;
  
  if (!id) throw error(400, 'Missing user ID');

  const result = UserSchema.partial().safeParse(rest);
  if (!result.success) {
    const message = result.error.issues.map((e: z.ZodIssue) => `${e.path.join('.')}: ${e.message}`).join(', ');
    throw error(400, message);
  }

  const { name, role, attributes } = result.data;

  const updatedUser = await prisma.user.update({
    where: { id },
    data: {
      name,
      role,
      attributes: attributes ? JSON.stringify(attributes) : undefined,
    }
  });

  return json(updatedUser);
};

// DELETE: Remove user
export const DELETE: RequestHandler = async ({ url, locals }) => {
  requireRole(locals, 'admin');
  
  const id = url.searchParams.get('id');
  if (!id) throw error(400, 'Missing user ID');

  await prisma.user.delete({ where: { id } });
  
  return json({ success: true });
};
