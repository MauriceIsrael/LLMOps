/**
 * Shared utility functions and types for shadcn-svelte components.
 *
 * @cn - Class name merger using clsx + tailwind-merge.
 *   Resolves Tailwind class conflicts (e.g. `cn('p-2 p-4')` → `'p-4'`).
 *   Use in component code whenever accepting external `class` props.
 *
 * @example
 *   import { cn } from '$lib/utils';
 *   const classes = cn('px-4 py-2', isActive && 'bg-primary', className);
 *
 * @types — These types are used internally by shadcn-svelte components.
 *   Do not remove them; the ui/ components import from here.
 */

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind CSS class names, resolving conflicts.
 * Accepts any mix of strings, conditionals, arrays, and objects.
 */
export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}

/** Adds an optional `ref` prop for direct DOM element access. Used by shadcn-svelte components. */
export type WithElementRef<T> = T & {
	ref?: any;
};

/** Omit both `children` and `child` snippet props. Used by shadcn-svelte components. */
export type WithoutChildrenOrChild<T> = Omit<T, "children" | "child">;

/** Omit the `child` snippet prop. Used by shadcn-svelte components. */
export type WithoutChild<T> = Omit<T, "child">;

/** Parameters for fly-and-scale transition animations. */
export type FlyAndScaleParams = {
	y?: number;
	x?: number;
	start?: number;
	duration?: number;
};
