/**
 * Demo API route — Zod-validated typed CRUD pattern.
 *
 * This file is the canonical example for building new API routes in this template.
 *
 * Pattern:
 *   - Define schemas in schema.ts (shared with client code)
 *   - Use `json()` for success responses and `error()` for failures
 *   - Return typed responses — inferred by `apiFetch<T>` on the client
 *
 * @extension
 *   To add a new resource:
 *   1. Copy this file to src/routes/api/<resource>/+server.ts
 *   2. Create src/routes/api/<resource>/schema.ts with your Zod schemas
 *   3. Replace the in-memory `items` array with your DB calls
 */

import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { CreateItemSchema, type Item } from './schema';

// In-memory store for demo purposes.
// @extension Replace with: import { db } from '$lib/server/db';
let items: Item[] = [
  { id: '1', name: 'Example Item A', createdAt: new Date().toISOString() },
  { id: '2', name: 'Example Item B', createdAt: new Date().toISOString() },
];

/** GET /api/demo — List all items */
export const GET: RequestHandler = async () => {
  return json(items);
};

/** POST /api/demo — Create a new item */
export const POST: RequestHandler = async ({ request }) => {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    error(400, { message: 'Invalid JSON body' });
  }

  const parsed = CreateItemSchema.safeParse(body);
  if (!parsed.success) {
    error(400, 'Validation failed: ' + JSON.stringify(parsed.error.flatten()));
  }

  const newItem: Item = {
    id: crypto.randomUUID(),
    name: parsed.data.name,
    createdAt: new Date().toISOString(),
  };

  items = [...items, newItem];
  return json(newItem, { status: 201 });
};

/** DELETE /api/demo — Clear all items (demo only) */
export const DELETE: RequestHandler = async () => {
  items = [];
  return new Response(null, { status: 204 });
};
