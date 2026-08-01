import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

async function main() {
  console.log('🌱 Seeding database...');

  const adminPass = await bcrypt.hash('admin123', 10);
  const userPass = await bcrypt.hash('user123', 10);

  // 1. Create Demo Admin
  await prisma.user.upsert({
    where: { email: 'admin@example.com' },
    update: { passwordHash: adminPass },
    create: {
      id: 'usr_admin_001',
      name: 'Admin User',
      email: 'admin@example.com',
      passwordHash: adminPass,
      role: 'admin',
      attributes: JSON.stringify({
        clearance: 3,
        department: 'Security',
        tags: ['internal']
      })
    }
  });

  // 2. Create Demo User
  await prisma.user.upsert({
    where: { email: 'user@example.com' },
    update: { passwordHash: userPass },
    create: {
      id: 'usr_user_002',
      name: 'Regular User',
      email: 'user@example.com',
      passwordHash: userPass,
      role: 'user',
      attributes: JSON.stringify({
        clearance: 1,
        department: 'Support',
        tags: ['beta']
      })
    }
  });

  // 3. Add Casbin Rules
  await prisma.casbinRule.deleteMany();
  
  await prisma.casbinRule.createMany({
    data: [
      { ptype: 'p', v0: 'admin', v1: '*', v2: '*' },
      { ptype: 'p', v0: 'user', v1: 'ui:users', v2: 'read' },
      { ptype: 'p', v0: 'user', v1: 'ui:settings', v2: 'read' },
      { ptype: 'g', v0: 'usr_admin_001', v1: 'admin' },
      { ptype: 'g', v0: 'usr_user_002', v1: 'user' },
    ]
  });

  console.log('✅ Seeding complete.');
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
