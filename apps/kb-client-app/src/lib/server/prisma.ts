import { PrismaClient } from '@prisma/client';

/**
 * Prisma Client singleton.
 */
console.log('[Prisma Init] CWD:', process.cwd());
console.log('[Prisma Init] DATABASE_URL:', process.env.DATABASE_URL);
if (!process.env.DATABASE_URL) {
	process.env.DATABASE_URL = 'file:./dev.db';
}

const prisma = new PrismaClient();

export { prisma };
