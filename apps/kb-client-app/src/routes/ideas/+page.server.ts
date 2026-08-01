import { fail, error } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { prisma } from '$lib/server/prisma';
import { requireAuth } from '$lib/auth/guard.server';

export const load: PageServerLoad = async ({ locals }) => {
  // Require auth to view ideas
  requireAuth(locals);

  try {
    const ideas = await prisma.idea.findMany({
      orderBy: { createdAt: 'desc' }
    });

    return {
      ideas
    };
  } catch (err) {
    console.error('Error loading ideas:', err);
    throw error(500, 'Erreur lors du chargement des idées');
  }
};

export const actions: Actions = {
  createIdea: async ({ request, locals }) => {
    requireAuth(locals);
    const session = locals.session;
    const formData = await request.formData();
    const title = formData.get('title') as string;
    const content = formData.get('content') as string;

    if (!title || !content) {
      return fail(400, { error: 'Le titre et la description sont obligatoires.' });
    }

    try {
      await prisma.idea.create({
        data: {
          title,
          content,
          authorId: session.user.id,
          authorName: session.user.name
        }
      });
      return { success: true };
    } catch (err) {
      console.error('Failed to create idea:', err);
      return fail(500, { error: 'Erreur lors de la création de l\'idée.' });
    }
  },

  deleteIdea: async ({ request, locals }) => {
    requireAuth(locals);
    const session = locals.session;
    const formData = await request.formData();
    const id = formData.get('id') as string;

    if (!id) {
      return fail(400, { error: 'ID manquant.' });
    }

    try {
      // Find idea to check owner or admin role
      const idea = await prisma.idea.findUnique({ where: { id } });
      if (!idea) {
        return fail(404, { error: 'Idée introuvable.' });
      }

      const isAdmin = session.user.role === 'admin';
      const isOwner = idea.authorId === session.user.id;

      if (!isAdmin && !isOwner) {
        return fail(403, { error: 'Action non autorisée.' });
      }

      await prisma.idea.delete({
        where: { id }
      });
      return { success: true };
    } catch (err) {
      console.error('Failed to delete idea:', err);
      return fail(500, { error: 'Erreur lors de la suppression.' });
    }
  }
};
