
import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

async function test() {
  console.log('Testing User creation...');
  
  try {
    const passwordHash = await bcrypt.hash('password123', 10);
    const user = await prisma.user.create({
      data: {
        name: 'Test User',
        email: 'test' + Date.now() + '@example.com',
        passwordHash,
        role: 'user',
        attributes: JSON.stringify({ department: 'test' }),
      }
    });
    console.log('User created:', user);
  } catch (err) {
    console.error('Error creating user:', err);
  } finally {
    await prisma.$disconnect();
  }
}

test();
