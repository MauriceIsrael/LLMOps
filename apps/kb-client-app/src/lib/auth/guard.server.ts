import { redirect, error } from '@sveltejs/kit';
import type { UserRole, Session } from '../../app.d.ts';
import { checkPermission as casbinCheck } from '$lib/server/casbin';

const ROLE_HIERARCHY: Record<UserRole, number> = {
  user: 1,
  admin: 2,
};

/**
 * Ensure the request is authenticated.
 */
export function requireAuth(
  locals: App.Locals,
  redirectTo = '/login'
): asserts locals is App.Locals & { session: Session } {
  if (!locals.session) {
    redirect(302, redirectTo);
  }
}

/**
 * Ensure the user has at least the required role (legacy RBAC).
 */
export function requireRole(locals: App.Locals, requiredRole: UserRole): void {
  requireAuth(locals);
  const userLevel = ROLE_HIERARCHY[locals.session!.user.role] ?? 0;
  const requiredLevel = ROLE_HIERARCHY[requiredRole] ?? 0;
  if (userLevel < requiredLevel) {
    error(403, { message: 'Insufficient permissions' });
  }
}

/**
 * Generic ABAC/RBAC guard using Casbin.
 */
export async function requirePermission(locals: App.Locals, obj: string, act: string) {
  requireAuth(locals);
  
  const sub = {
    id: locals.session!.user.id,
    role: locals.session!.user.role,
    ...locals.session!.user.attributes
  };
  
  const resource = { type: obj };
  
  const allowed = await casbinCheck(sub, resource, act);
  
  if (!allowed) {
    error(403, { message: `Permission denied: ${act} on ${obj}` });
  }
}
