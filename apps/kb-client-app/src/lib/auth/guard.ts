/**
 * Client-side safe Auth utilities.
 */
import type { UserRole, Session } from '../../app.d.ts';

const ROLE_HIERARCHY: Record<UserRole, number> = {
  user: 1,
  admin: 2,
};

/**
 * Client-side boolean check — does the session user have at least the required role?
 * Safe to call with null session (returns false).
 */
export function hasRole(
  session: Session | null | undefined,
  requiredRole: UserRole
): boolean {
  if (!session) return false;
  const userRole = session.user.role as UserRole;
  const userLevel = ROLE_HIERARCHY[userRole] ?? 0;
  const requiredLevel = ROLE_HIERARCHY[requiredRole] ?? 0;
  return userLevel >= requiredLevel;
}
