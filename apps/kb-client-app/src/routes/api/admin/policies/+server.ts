import { json, error } from '@sveltejs/kit';
import { getEnforcer } from '$lib/server/casbin';
import { requireRole } from '$lib/auth/guard.server';
import { prisma } from '$lib/server/prisma';
import type { RequestHandler } from './$types';

/**
 * Casbin Policy API — Admin Only.
 */

// GET: List all policies and groups
export const GET: RequestHandler = async ({ locals }) => {
  requireRole(locals, 'admin');
  
  const ef = await getEnforcer();
  const policies = await ef.getPolicy();
  const groups = await ef.getGroupingPolicy();
  
  return json({ policies, groups });
};

// POST: Add a policy or group
export const POST: RequestHandler = async ({ request, locals }) => {
  requireRole(locals, 'admin');
  
  const { type, params } = await request.json(); // type: 'p' or 'g', params: [v0, v1, v2...]
  
  if (type === 'g' && params.length > 0) {
    const userId = params[0];
    const user = await prisma.user.findUnique({ where: { id: userId } });
    if (!user) {
      throw error(404, 'User not found');
    }
  }

  const ef = await getEnforcer();
  let success = false;
  
  if (type === 'p') {
    success = await ef.addPolicy(...params);
  } else if (type === 'g') {
    success = await ef.addGroupingPolicy(...params);
  }
  
  if (!success) {
    throw error(409, 'Policy already exists');
  }
  
  await ef.savePolicy();
  return json({ success: true });
};

// DELETE: Remove a policy or group
export const DELETE: RequestHandler = async ({ url, locals }) => {
  requireRole(locals, 'admin');
  
  const type = url.searchParams.get('type'); // 'p' or 'g'
  const params = JSON.parse(url.searchParams.get('params') || '[]');
  
  const ef = await getEnforcer();
  let success = false;
  
  if (type === 'p') {
    success = await ef.removePolicy(...params);
  } else if (type === 'g') {
    success = await ef.removeGroupingPolicy(...params);
  }
  
  if (!success) {
    throw error(404, 'Policy not found');
  }
  
  await ef.savePolicy();
  return json({ success: true });
};
