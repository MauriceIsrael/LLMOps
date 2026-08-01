import { checkPermission } from '$lib/server/casbin';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
  const session = locals.session;
  
  const abacStatus = {
    canManageUsers: false,
    canEditSettings: false,
    canAccessSecretAPI: false,
  };

  if (session) {
    const sub = {
      id: session.user.id,
      role: session.user.role,
      ...session.user.attributes
    };

    abacStatus.canManageUsers = await checkPermission(sub, { type: 'ui:users' }, 'read');
    abacStatus.canEditSettings = await checkPermission(sub, { type: 'ui:settings' }, 'read');
    abacStatus.canAccessSecretAPI = await checkPermission(sub, { type: 'api:secret' }, 'access');
  }

  return {
    abacStatus
  };
};
