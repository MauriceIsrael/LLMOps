/**
 * Demo API schemas — shared between server handler and client code.
 * Import on both sides to keep request/response types in sync.
 *
 * @extension
 *   Add new schemas here as your API grows.
 *   The `z.infer<>` pattern gives you TypeScript types for free.
 */

import { z } from 'zod';

export const CreateItemSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100, 'Name too long'),
});

export type CreateItemInput = z.infer<typeof CreateItemSchema>;

export type Item = {
  id: string;
  name: string;
  createdAt: string;
};
