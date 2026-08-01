import { requireRole } from '$lib/auth/guard.server';
import { prisma } from '$lib/server/prisma';
import { getEnforcer } from '$lib/server/casbin';
import type { PageServerLoad } from './$types';

/**
 * Admin Load — RBAC/ABAC protected user and policy list.
 */
export const load: PageServerLoad = async ({ locals }) => {
  // Enforce role
  requireRole(locals, 'admin');

  // Fetch all users from DB
  const users = await prisma.user.findMany({
    orderBy: { createdAt: 'desc' }
  });

  // Fetch Casbin policies
  const ef = await getEnforcer();
  const policies = await ef.getPolicy();
  const groups = await ef.getGroupingPolicy();

  return {
    users: users.map(u => ({
      id: u.id,
      name: u.name,
      email: u.email,
      role: u.role,
      // @ts-ignore
      attributes: JSON.parse(u.attributes || '{}')
    })),
    policies,
    groups
  };
};
