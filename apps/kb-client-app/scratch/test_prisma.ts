import { PrismaClient } from '@prisma/client';
import { PrismaBetterSqlite3 } from '@prisma/adapter-better-sqlite3';
import 'dotenv/config';

const url = process.env.DATABASE_URL || 'file:./dev.db';
const adapter = new PrismaBetterSqlite3({ url });
const prisma = new PrismaClient({ adapter });

async function main() {
  console.log('Testing Prisma connection...');
  const count = await prisma.user.count();
  console.log('User count:', count);
}

main().catch(console.error).finally(() => prisma.$disconnect());
