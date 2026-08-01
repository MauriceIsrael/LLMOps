/**
 * Hardcoded demo users — no database required.
 *
 * These are the only valid credentials for the template app.
 * @security In a real app, replace with a DB lookup and bcrypt password hashing.
 *
 * Demo credentials:
 *   admin@example.com / admin123  →  role: 'admin'
 *   user@example.com  / user123   →  role: 'user'
 */

import type { SessionUser, UserRole } from '../../app.d.ts';

// Internal user shape (includes password — never sent to client)
type StoredUser = SessionUser & { password: string };

const USERS: StoredUser[] = [
  {
    id: 'usr_admin_001',
    name: 'Admin User',
    email: 'admin@example.com',
    password: 'admin123',  // @security Replace with bcrypt hash in production
    role: 'admin' as UserRole,
    image: 'https://api.dicebear.com/7.x/avataaars/svg?seed=AdminUser',
  },
  {
    id: 'usr_user_002',
    name: 'Regular User',
    email: 'user@example.com',
    password: 'user123',   // @security Replace with bcrypt hash in production
    role: 'user' as UserRole,
    image: 'https://api.dicebear.com/7.x/avataaars/svg?seed=RegularUser',
  },
];

/**
 * Find a user by email/password.
 * Returns the public SessionUser (no password) or null.
 *
 * @extension Replace the in-memory comparison with:
 *   const user = await db.user.findUnique({ where: { email } });
 *   const valid = await bcrypt.compare(password, user.passwordHash);
 */
export function findUserByCredentials(
  email: string,
  password: string
): SessionUser | null {
  const user = USERS.find(
    (u) => u.email.toLowerCase() === email.toLowerCase() && u.password === password
  );
  if (!user) return null;
  const { password: _, ...publicUser } = user;
  return publicUser;
}

/** Get all users (public fields only) — used by admin panel. */
export function getAllUsers(): SessionUser[] {
  return USERS.map(({ password: _, ...u }) => u);
}

/** Get a single user by id (public fields). */
export function getUserById(id: string): SessionUser | null {
  const user = USERS.find((u) => u.id === id);
  if (!user) return null;
  const { password: _, ...publicUser } = user;
  return publicUser;
}
